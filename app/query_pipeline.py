import luqum.exceptions
from luqum import tree
from luqum.parser import parser
from luqum.utils import OpenRangeTransformer, UnknownOperationResolver

from ._types import QueryAnalysis, SearchParameters
from .config import IndexConfig
from .exceptions import InvalidLuceneQueryError, QueryCheckError
from .query_transformers import (
    LanguageSuffixTransformer,
    PhraseBoostTransformer,
    QueryCheck,
)


def parse_query(q: str | None) -> QueryAnalysis:
    """Begin query analysis by parsing the query."""
    analysis = QueryAnalysis(text_query=q)
    if q is None or not q.strip():
        return analysis
    try:
        analysis.luqum_tree = parser.parse(q)
        # FIXME: resolve UnknownFilter (to AND)
    except (
        luqum.exceptions.ParseError,
        luqum.exceptions.InconsistentQueryException,
    ) as e:
        raise InvalidLuceneQueryError("Request could not be analyzed by luqum") from e
    return analysis


def compute_facets_filters(q: QueryAnalysis) -> QueryAnalysis:
    """Extract facets filters from the query

    For now it only handles SearchField under a top AND operation,
    which expression is a bare term or a OR operation of bare terms.

    We do not verify if the field is an aggregation field or not,
    that can be done at a later stage

    :return: a new QueryAnalysis with facets_filters attribute
       as a dictionary of field names and list of values to filter on
    """
    if q.luqum_tree is None:
        return q

    filters = {}

    def _process_search_field(expr, field_name):
        facet_filter = None
        if isinstance(expr, tree.Term):
            # simple term
            facet_filter = [str(expr)]
        elif isinstance(expr, tree.FieldGroup):
            # use recursion
            _process_search_field(expr.expr, field_name)
        elif isinstance(expr, tree.OrOperation) and all(
            isinstance(item, tree.Term) for item in expr.children
        ):
            # OR operation of simple terms
            facet_filter = [str(item) for item in expr.children]
        if facet_filter:
            if field_name not in filters:
                filters[field_name] = facet_filter
            else:
                # avoid the case of double expression, we don't handle it
                filters.pop(field_name)

    if isinstance(q.luqum_tree, (tree.AndOperation, tree.UnknownOperation)):
        for child in q.luqum_tree.children:
            if isinstance(child, tree.SearchField):
                _process_search_field(child.expr, child.name)
    # case of a single search field
    elif isinstance(q.luqum_tree, tree.SearchField):
        _process_search_field(q.luqum_tree.expr, q.luqum_tree.name)
    # remove quotes around values
    filters = {
        field_name: [value.strip('"') for value in values]
        for field_name, values in filters.items()
    }
    return q.clone(facets_filters=filters)


def add_languages_suffix(
    analysis: QueryAnalysis, langs: list[str], config: IndexConfig
) -> QueryAnalysis:
    """Add correct languages suffixes to fields of type text_lang or taxonomy

    This match in a langage OR another
    """
    if analysis.luqum_tree is None:
        return analysis
    transformer = LanguageSuffixTransformer(
        lang_fields=set(config.lang_fields), langs=langs
    )
    analysis.luqum_tree = transformer.visit(analysis.luqum_tree)
    return analysis


def resolve_unknown_operation(analysis: QueryAnalysis) -> QueryAnalysis:
    """Resolve unknown operations in the query to a AND"""
    if analysis.luqum_tree is None:
        return analysis
    transformer = UnknownOperationResolver(resolve_to=tree.AndOperation)
    analysis.luqum_tree = transformer.visit(analysis.luqum_tree)
    return analysis


def boost_phrases(
    analysis: QueryAnalysis, boost: float, proximity: int | None
) -> QueryAnalysis:
    """Boost all phrases in the query"""
    if analysis.luqum_tree is None:
        return analysis
    transformer = PhraseBoostTransformer(boost=boost, proximity=proximity)
    analysis.luqum_tree = transformer.visit(analysis.luqum_tree)
    return analysis


def check_query(params: SearchParameters, analysis: QueryAnalysis) -> None:
    """Run some sanity checks on the luqum query"""
    if analysis.luqum_tree is None:
        return
    checker = QueryCheck(index_config=params.index_config, zeal=1)
    errors = checker.errors(analysis.luqum_tree)
    if errors:
        raise QueryCheckError("Found errors while checking query", errors=errors)


def resolve_open_ranges(analysis: QueryAnalysis) -> QueryAnalysis:
    """We need to resolve open ranges to closed ranges
    before using elasticsearch query builder"""
    if analysis.luqum_tree is None:
        return analysis
    transformer = OpenRangeTransformer()
    analysis.luqum_tree = transformer.visit(analysis.luqum_tree)
    return analysis
