"""Defines some analyzers for the elesaticsearch fields."""

from elasticsearch_dsl import Mapping, analyzer, token_filter

from app._types import JSONType

# some normalizers existing in ES that are specific to some languages
SPECIAL_NORMALIZERS = {
    "ar": "arabic_normalization",
    "bn": "bengali_normalization",
    "de": "german_normalization",
    "hi": "hindi_normalization",
    "inc": "indic_normalization",
    "fa": "persian_normalization",
    "sv": "scandinavian_folding",
    "da": "scandinavian_folding",
    "no": "scandinavian_folding",
    "fi": "scandinavian_folding",
    "sr": "serbian_normalization",
    "ckb": "sorani_normalization",
}


def get_taxonomy_synonym_filter(taxonomy: str, lang: str) -> token_filter:
    """Return the synonym filter to use for the taxonomized field analyzer"""
    return token_filter(
        f"synonym_graph_{taxonomy}_{lang}",
        type="synonym_graph",
        synonyms_path=f"synonyms/{taxonomy}/{lang}.txt",
        updateable=True,
    )


def get_taxonomy_analyzer(taxonomy: str, lang: str, with_synonyms: bool) -> analyzer:
    """Return the search analyzer to use for the taxonomized field

    :param taxonomy: the taxonomy name
    :param lang: the language code
    :param with_synonyms: whether to add the synonym filter
    """
    filters: list[str | token_filter] = [
        "lowercase",
        SPECIAL_NORMALIZERS.get(lang, "asciifolding"),
    ]
    if with_synonyms:
        filters.append(
            get_taxonomy_synonym_filter(taxonomy, lang),
        )
    return analyzer(
        f"search_{taxonomy}_{lang}",
        tokenizer="standard",
        filter=filters,
    )


def get_autocomplete_analyzer(lang: str) -> analyzer:
    """Return the search analyzer to use for the autocomplete field"""
    return analyzer(
        f"autocomplete_{lang}",
        tokenizer="standard",
        filter=["lowercase", SPECIAL_NORMALIZERS.get(lang, "asciifolding")],
    )


def number_of_fields(mapping: Mapping | dict[str, JSONType]) -> int:
    """Return the number of fields in the mapping"""
    count = 0
    properties: dict[str, JSONType] = (
        mapping.to_dict().get("properties", {})
        if isinstance(mapping, Mapping)
        else mapping
    )
    for field, value in properties.items():
        if isinstance(value, dict):
            if props := value.get("properties"):
                # object field with properties
                count += number_of_fields(props)
            if fields := value.get("fields"):
                # subfields
                count += number_of_fields(fields)
        count += 1
    return count
