import luqum.visitor
from luqum import tree
from luqum.utils import UnknownOperationResolver


class LanguageSuffixTransformer(luqum.visitor.TreeTransformer):
    """This transformer adds a language suffix to lang_fields fields,
    for any languages in langs (the languages we want to query on).

    That is `field1:something` will become
    `field1:en:something OR field1:fr:something`
    """

    def __init__(self, lang_fields=set[str], langs=list[str], **kwargs):
        # we need to track parents to get full field name
        super().__init__(track_parents=True, track_new_parents=False, **kwargs)
        self.langs = langs
        self.lang_fields = lang_fields

    def visit_search_field(self, node, context):
        """As we reach a search_field,
        if it's one that have a lang,
        we replace single expression with a OR on sub-language fields
        """
        # FIXME: verify again the way luqum work on this side !
        field_name = node.name
        # add eventual parents
        prefix = ".".join(
            node.name
            for node in context["parents"]
            if isinstance(node, tree.SearchField)
        )
        if prefix:
            field_name = f"{prefix}.{field_name}"
        # is it a lang dependant field
        if field_name in self.lang_fields:
            # create a new expression for each languages
            new_nodes = []
            for lang in self.langs:
                # note: we don't have to care about having searchfield in children
                # because only complete field_name would match a self.lang_fields
                new_node = self.generic_visit(node)
                # add language prefix
                new_node.name = f"{new_node.name}.{lang}"
                new_nodes.append(new_node)
            if len(new_nodes) > 1:
                yield tree.OrOperation(*new_nodes)
            else:
                yield from new_nodes
        else:
            # default
            yield from self.generic_visit(node)


def get_consecutive_words(
    node: tree.BoolOperation,
) -> list[list[tuple[int, tree.Word]]]:
    """Return a list of list of consecutive words,
    with their index, in a bool operation
    """
    consecutive: list[list[tuple[int, tree.Word]]] = [[]]
    for i, child in enumerate(node.children):
        if isinstance(child, tree.Word):
            # append to last list
            consecutive[-1].append((i, child))
        else:
            # we have discontinuity
            if len(consecutive[-1]) == 1:
                # one term alone is not enough, clear the list
                consecutive[-1] = []
            elif consecutive[-1]:
                # create a new list
                consecutive.append([])
    # remove last list if empty or only one element
    if len(consecutive[-1]) <= 1:
        consecutive.pop()
    return consecutive


class PhraseBoostTransformer(luqum.visitor.TreeTransformer):
    """This transformer boosts terms that are consecutive
    and might be found in a query

    For example if we have `Whole OR Milk OR Cream`
    we will boost items containing "Whole Milk Cream"

    We also only apply it to terms that are not for a specified field
    """

    def __init__(self, boost=float, **kwargs):
        super().__init__(track_parents=True, track_new_parents=False, **kwargs)
        self.boost = boost

    def _get_consecutive_words(self, node):
        return [[word for _, word in words] for words in get_consecutive_words(node)]

    def _phrase_from_words(self, words):
        expr = " ".join(word.value for word in words)
        expr = f'"{expr}"'
        phrase = tree.Phrase(expr)
        return tree.Boost(phrase, force=self.boost, head=" ", tail=" ")

    def visit_or_operation(self, node, context):
        """As we find an OR operation try to boost consecutive word terms"""
        # get the or operation with cloned children
        (new_node,) = list(super().generic_visit(node, context))
        has_search_field = any(
            isinstance(p, tree.SearchField) for p in context.get("parents", [])
        )
        if not has_search_field:
            # we are in an expression with no field specified, transform
            consecutive = self._get_consecutive_words(new_node)
            if consecutive:
                # create new match phrase w terms from consecutive words
                new_terms = [self._phrase_from_words(words) for words in consecutive]
                # head / tail problem
                new_terms[-1].tail = new_node.children[-1].tail
                new_node.children[-1].tail = " "
                # add operands
                new_node.children += tuple(new_terms)
        yield new_node


class SmartUnknownOperationResolver(UnknownOperationResolver):
    """A complex unknown operation resolver that fits what users might intend

    It replace UnknownOperation by a AND operation,
    but if consecutive words are found it will try to group them in a OR operation
    """

    def _get_consecutive_words(self, node):
        return get_consecutive_words(node)

    def _words_or_operation(self, words):
        # transfer head and tail
        head = words[0].head
        tail = words[-1].tail
        words[0].head = ""
        words[-1].tail = ""
        operation = tree.Group(tree.OrOperation(*words), head=head, tail=tail)
        return operation

    def visit_unknown_operation(self, node, context):
        # create the node as intended, this might be AND or OR operation
        (new_node,) = list(super().visit_unknown_operation(node, context))
        # if it's AND operation
        if isinstance(new_node, tree.AndOperation):
            # group consecutive terms in OROperations
            consecutive = self._get_consecutive_words(new_node)
            if consecutive:
                # change first word by the OR operation
                index_to_change = {
                    words[0][0]: self._words_or_operation([word[1] for word in words])
                    for words in consecutive
                }
                # remove other words that are part of the expression
                index_to_remove = set(
                    word[0] for words in consecutive for word in words[1:]
                )
                new_children = []
                for i, child in enumerate(new_node.children):
                    if i in index_to_change:
                        new_children.append(index_to_change[i])
                    elif i not in index_to_remove:
                        new_children.append(child)
                # substitute children
                new_node.children = new_children
        yield new_node
