import re

import luqum.check
import luqum.visitor
from luqum import tree

from .config import IndexConfig


class LanguageSuffixTransformer(luqum.visitor.TreeTransformer):
    """This transformer adds a language suffix to lang_fields fields,
    for any languages in langs (the languages we want to query on).

    That is `field1:something` will become
    `field1:en:something OR field1:fr:something`

    Note: we do this only for the query parts that have a search field,
    the text search without specifying a field
    is handled by the ElasticSearch query builder
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
            for node in context.get("parents", ())
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
                (new_node,) = self.generic_visit(node, context)
                # add language prefix
                new_node.name = f"{new_node.name}.{lang}"
                new_nodes.append(new_node)
            if len(new_nodes) > 1:
                yield tree.OrOperation(*new_nodes)
            else:
                yield from new_nodes
        else:
            # default
            yield from self.generic_visit(node, context)


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

    For example if we have `Whole AND Milk AND Cream`
    we will boost items containing `"Whole Milk Cream"`,
    the new expression will look like
    (here with a boost of 2 and proxmity of 3):
    `((Whole AND Milk AND Cream^2) OR "Whole Milk Cream"^2.0~3)`

    We also only apply it to terms that are not for a specified field.

    Note: It won't work on UnknownOperation, so you'd better resolve them before.

    :param boost: how much to boost consecutive terms
    :param proximity: proxmity of the boosted phrase, enable to match with gaps
    :param only_free_text: only apply to text without an explicit search field defined
    """

    def __init__(
        self, boost: float, proximity: int | None = 1, only_free_text=True, **kwargs
    ):
        super().__init__(track_parents=True, track_new_parents=False, **kwargs)
        # we transform float to str,
        # because otherwise decimal.Decimal will make it look weird
        self.boost = str(boost)
        self.proximity = proximity
        self.only_free_text = only_free_text

    def _get_consecutive_words(self, node):
        return get_consecutive_words(node)

    def _phrase_boost_from_words(self, words):
        """Given a group of words, give the new operation"""
        expr = " ".join(word.value for word in words)
        expr = f'"{expr}"'
        phrase = tree.Phrase(expr)
        if self.proximity:
            phrase = tree.Proximity(phrase, degree=self.proximity)
        phrase = tree.Boost(phrase, force=self.boost, head=" ")
        new_expr = tree.Group(
            tree.OrOperation(tree.Group(tree.AndOperation(*words), tail=" "), phrase)
        )
        # tail and head transfer, to have good looking str
        new_expr.head = words[0].head
        words[0].head = ""
        new_expr.tail = words[-1].tail
        words[-1].tail = ""
        return new_expr

    def visit_and_operation(self, node, context):
        """As we find an OR operation try to boost consecutive word terms"""
        # get the or operation with cloned children
        (new_node,) = list(super().generic_visit(node, context))
        do_boost_phrases = True
        if self.only_free_text:
            # we don't do it if a parent is a SearchField
            do_boost_phrases = not any(
                isinstance(p, tree.SearchField) for p in context.get("parents", ())
            )
        if do_boost_phrases:
            # group consecutive terms in AndOperations
            consecutive = self._get_consecutive_words(new_node)
            if consecutive:
                # We have to modify children
                # by replacing consecutive words with our new expressions.
                # We use indexes for that.
                new_children = []
                # change first word by the new operation
                index_to_change = {
                    words[0][0]: self._phrase_boost_from_words(
                        [word[1] for word in words]
                    )
                    for words in consecutive
                }
                # remove other words that are part of the expression
                # (and we will keep the rest)
                index_to_remove = set(
                    word[0] for words in consecutive for word in words[1:]
                )
                for i, child in enumerate(new_node.children):
                    if i in index_to_change:
                        new_children.append(index_to_change[i])
                    elif i not in index_to_remove:
                        new_children.append(child)
                # substitute children of the new node
                new_node.children = new_children
        yield new_node


class QueryCheck(luqum.check.LuceneCheck):
    """Sanity checks on luqum request"""

    # TODO: port to luqum
    SIMPLE_EXPR_FIELDS = luqum.check.LuceneCheck.SIMPLE_EXPR_FIELDS + (
        tree.Range,
        tree.OpenRange,
    )
    FIELD_EXPR_FIELDS = SIMPLE_EXPR_FIELDS + (tree.FieldGroup,)
    # TODO: shan't luqum should support "." in field names
    field_name_re = re.compile(r"^[\w.]+$")

    def __init__(self, index_config: IndexConfig, **kwargs):
        super().__init__(**kwargs)
        self.index_config = index_config

    # TODO: this should be in LuceneCheck !
    def check_phrase(self, item, parents):
        return iter([])

    def check_open_range(self, item, parents):
        return iter([])

    def check_search_field(self, item, parents):
        """Check if the search field is valid"""
        yield from super().check_search_field(item, parents)
        # might be an inner field get all parents fields
        fields = [p.name for p in parents if isinstance(p, tree.SearchField)] + [
            item.name
        ]
        # join and split to normalize and only have one field
        field_names = (".".join(fields)).split(".")
        # remove eventual lang suffix
        has_lang_suffix = field_names[-1] in self.index_config.supported_langs_set
        if has_lang_suffix:
            field_names.pop()
        is_sub_field = len(field_names) > 1
        # check field exists in config, but only for non sub-field
        # (TODO until we implement them in config)
        if not is_sub_field and (field_names[0] not in self.index_config.fields):
            yield f"Search field '{'.'.join(field_names)}' not found in index config"
