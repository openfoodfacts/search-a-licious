"""This module creates a specific ESQueryBuilder,
that will be able to handle the full text search correctly
"""

from elasticsearch_dsl import Q
from luqum.elasticsearch.tree import ElasticSearchItemFactory, EPhrase, EWord
from luqum.elasticsearch.visitor import ElasticsearchQueryBuilder

from app.config import IndexConfig

DEFAULT_FIELD_MARKER = "_searchalicious_text"


class EFullText(EPhrase):
    """Item that generates a full text query

    We will intercept the QueryBuilder
    as it process a default full text query
    to substitute our own json generator.
    """

    def __init__(self, index_config: IndexConfig, query_langs=list[str], **kwargs):
        super().__init__(**kwargs)
        self.index_config = index_config
        self.boost_langs = set(self.index_config.supported_langs) & set(query_langs)

    def json(self):
        """Generate the JSON specific to our requests"""
        fields = []
        config = self.index_config
        lang_fields = set(config.lang_fields)
        query = self.q

        # we will try to boost query for matching on taxonomies
        match_phrase_boost_queries = []

        for field in config.fields.values():
            # We don't include all fields in the multi-match clause,
            # only a subset of them
            if field.full_text_fields:
                if field in lang_fields:
                    # handle sub languages
                    field_match_phrase_boost_queries = []
                    for lang in self.boost_langs:
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
                        match_phrase_boost_queries.append(
                            field_match_phrase_boost_queries[0]
                        )
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


class FullTextItemFactory(ElasticSearchItemFactory):
    """A specific item builder that will tweak
    the request being constructed for default text search
    by using EFullText instead of default EWord / EPhrase from luqum.
    This in turn will generate the right JSON to build that part of the request
    """

    def __init__(self, index_config: IndexConfig, query_langs: list[str], **kwargs):
        super().__init__(**kwargs)
        self.index_config = index_config
        self.query_langs = query_langs

    def build(self, cls, *args, **kwargs):
        # if its a fulltext term on default field
        is_match = issubclass(cls, (EWord, EPhrase))
        is_default_field = kwargs.get("fields", None) == [DEFAULT_FIELD_MARKER]
        # sanity check
        # TODO: move it to a pre sanity check instead using luqum tree,
        # to be able to tell exactly where it happens
        if kwargs.get("q") == "*":
            raise ValueError("You can't use a wildcard query alone '*'")
        if is_match and is_default_field:
            # change for our specific term builder
            cls = EFullText
            kwargs.update(index_config=self.index_config, query_langs=self.query_langs)
        # let the rest continue as before
        return super().build(cls, *args, **kwargs)


class FullTextQueryBuilder(ElasticsearchQueryBuilder):
    """We have our own ESQueryBuilder,
    just to be able to use our FullTextItemFactory,
    instead of the default ElasticSearchItemFactory
    """

    def __init__(self, index_config: IndexConfig, query_langs: list[str], **kwargs):
        """We add two parameters:

        :param index_config: the index config we are working on
        :param query_langs: the target languages of current query
        """
        # sanity check, before overriding below
        if "default_field" in kwargs:
            raise ValueError("You should not override default_field")
        super().__init__(
            # we put a specific marker on default_field
            # because we want to be sure we recognize them
            default_field=DEFAULT_FIELD_MARKER,
            **kwargs,
        )
        # substitute the es_item_factory by our own
        self.es_item_factory = FullTextItemFactory(
            no_analyze=self._not_analyzed_fields,
            nested_fields=self.nested_fields,
            field_options=self.field_options,
            index_config=index_config,
            query_langs=query_langs,
        )
