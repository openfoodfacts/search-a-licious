"""This module creates a specific ESQueryBuilder,
that will be able to handle the full text search correctly
"""

import luqum
from elasticsearch_dsl import Q
from luqum.elasticsearch.tree import EPhrase, EWord
from luqum.elasticsearch.visitor import ElasticsearchQueryBuilder

from ._types import JSONType
from .config import IndexConfig

DEFAULT_FIELD_MARKER = "_searchalicious_text"


def build_full_text_query(query: str, config: IndexConfig, query_langs: list[str]):
    fields = []
    lang_fields = set(config.lang_fields)
    boost_langs = set(config.supported_langs) & set(query_langs)

    # sanity check
    # TODO: move it to a pre sanity check instead using luqum tree,
    # to be able to tell exactly where it happens
    if query == "*":
        raise ValueError("You can't use a wildcard query alone '*'")

    # we will try to boost query for matching on taxonomies
    match_phrase_boost_queries = []

    for fname, field in config.full_text_fields.items():
        if fname in lang_fields:
            # handle sub languages
            field_match_phrase_boost_queries = []
            for lang in boost_langs:
                subfield_name = f"{field.name}.{lang}"
                fields.append(subfield_name)
                # FIXME: why a simple match phrase
                # if we want to boost exact match ?
                field_match_phrase_boost_queries.append(
                    Q(
                        "match_phrase",
                        **{
                            subfield_name: {
                                "query": query,
                                "boost": config.match_phrase_boost,
                            }
                        },
                    )
                )
            if len(field_match_phrase_boost_queries) == 1:
                match_phrase_boost_queries.append(field_match_phrase_boost_queries[0])
            elif len(field_match_phrase_boost_queries) > 1:
                match_phrase_boost_queries.append(
                    Q("bool", should=field_match_phrase_boost_queries)
                )
        else:
            fields.append(field.name)
            match_phrase_boost_queries.append(
                Q(
                    "match_phrase",
                    **{
                        field.name: {
                            "query": query,
                            "boost": config.match_phrase_boost,
                        }
                    },
                )
            )

    multi_match_query = Q("multi_match", query=query, fields=fields)

    if match_phrase_boost_queries:
        multi_match_query |= Q("bool", should=match_phrase_boost_queries)

    return multi_match_query.to_dict()


class EFullTextWord(EWord):
    """Item that generates a full text query"""

    def __init__(self, index_config: IndexConfig, query_langs=list[str], **kwargs):
        super().__init__(**kwargs)
        self.index_config = index_config
        self.query_langs = query_langs

    @property
    def json(self):
        """Generate the JSON specific to our requests"""
        return build_full_text_query(self.q, self.index_config, self.query_langs)


class EFullTextPhrase(EPhrase):
    """Item that generates a full text query"""

    def __init__(self, index_config: IndexConfig, query_langs=list[str], **kwargs):
        super().__init__(**kwargs)
        self.index_config = index_config
        self.query_langs = query_langs

    @property
    def json(self):
        """Generate the JSON specific to our requests"""
        return build_full_text_query(self.phrase, self.index_config, self.query_langs)


class FullTextQueryBuilder(ElasticsearchQueryBuilder):
    """We have our own ESQueryBuilder,
    just to be able to use our FullTextItemFactory,
    instead of the default ElasticSearchItemFactory
    """

    def __init__(self, **kwargs):
        # sanity check, before overriding below
        if "default_field" in kwargs:
            raise ValueError("You should not override default_field")
        super().__init__(
            # we put a specific marker on default_field
            # because we want to be sure we recognize them
            default_field=DEFAULT_FIELD_MARKER,
            **kwargs,
        )

    def _is_searchalicious_full_text_item(self, item):
        is_match = isinstance(item, (EWord, EPhrase))
        is_default_field = item.field == DEFAULT_FIELD_MARKER
        return is_match and is_default_field

    def visit_word(self, node, context):
        for item in super().visit_word(node, context):
            if self._is_searchalicious_full_text_item(item):
                # change for our specific term builder
                item = EFullTextWord(
                    q=item.q,
                    method=item._method,
                    fields=item._fields,
                    index_config=context["index_config"],
                    query_langs=context["query_langs"],
                )
            yield item

    def visit_phrase(self, node, context):
        for item in super().visit_phrase(node, context):
            if self._is_searchalicious_full_text_item(item):
                # change for our specific term builder
                item = EFullTextPhrase(
                    # we have to take node.value
                    # for item.phrase is already processed
                    phrase=node.value,
                    method=item._method,
                    name=item._name,
                    fields=item._fields,
                    index_config=context["index_config"],
                    query_langs=context["query_langs"],
                )
            yield item

    def __call__(
        self, tree: luqum.tree.Item, index_config: IndexConfig, query_langs: list[str]
    ) -> JSONType:
        """We add two parameters:

        :param index_config: the index config we are working on
        :param query_langs: the target languages of current query
        """
        self.nesting_checker(tree)
        # we add our parameters to the context
        context = {"index_config": index_config, "query_langs": query_langs}
        elastic_tree = self.visit(tree, context)
        return elastic_tree[0].json
