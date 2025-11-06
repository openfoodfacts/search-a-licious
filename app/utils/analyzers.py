"""Defines some analyzers for the elesaticsearch fields."""

from typing import Optional

from elasticsearch_dsl import Mapping
from elasticsearch_dsl import analysis as dsl_analysis
from elasticsearch_dsl import analyzer, char_filter, token_filter

from app._types import JSONType
from app.config import IndexConfig
from app.taxonomy_es import expected_synonyms_sets_ids

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


# TODO: this could be provided by the taxonomy / per language
STOP_WORDS = {
    "ar": "_arabic_",
    "hy": "_armenian_",
    "eu": "_basque_",
    "bn": "_bengali_",
    # "pt_BR": _brazilian_
    "bg": "_bulgarian_",
    "ca": "_catalan_",
    "ja": "_cjk_",
    "zh": "_cjk_",
    "ko": "_cjk_",
    "cs": "_czech_",
    "da": "_danish_",
    "nl": "_dutch_",
    "en": "_english_",
    "et": "_estonian_",
    "fi": "_finnish_",
    "fr": "_french_",
    "gl": "_galician_",
    "de": "_german_",
    "el": "_greek_",
    "hi": "_hindi_",
    "hu": "_hungarian_",
    "id": "_indonesian_",
    "ga": "_irish_",
    "it": "_italian_",
    "lv": "_latvian_",
    "lt": "_lithuanian_",
    "no": "_norwegian_",
    "fa": "_persian_",
    "pt": "_portuguese_",
    "ro": "_romanian_",
    "ru": "_russian_",
    "sr": "_serbian_",
    # "": "_sorani_",
    "es": "_spanish_",
    "sv": "_swedish_",
    "th": "_thai_",
    "tr": "_turkish_ ",
}


def iter_taxonomy_synonyms_filters(
    config: IndexConfig, taxonomy: str, lang: str
) -> dsl_analysis.TokenFilter:
    """Return the synonyms filters to use for the taxonomized field analyzer"""
    for set_id in expected_synonyms_sets_ids(config, taxonomy, lang):
        yield token_filter(
            f"synonym_graph_{set_id}",
            type="synonym_graph",
            synonyms_set=set_id,
            updateable=True,
        )


def get_taxonomy_stop_words_filter(
    taxonomy: str, lang: str
) -> Optional[dsl_analysis.TokenFilter]:
    """Return the stop words filter to use for the taxonomized field analyzer

    IMPORTANT: de-activated for now !
    If we want to handle them, we have to remove them in synonyms, so we need the list.
    """
    stop_words = STOP_WORDS.get(lang)
    # deactivate for now
    if False and stop_words:
        return token_filter(
            f"taxonomy_stop_words_{lang}",
            type="stop",
            stopwords=stop_words,
            remove_trailing=True,
        )
    return None


TAXONOMIES_CHAR_FILTER = char_filter(
    "taxonomies_char_filter",
    type="mapping",
    mappings=[
        # hyphen to underscore
        "- => _",
        # and escape quotes, so that ES cut words on them
        r"' => \\'",
        r"’ => \\'",
    ],
)


def get_taxonomy_indexing_analyzer(
    taxonomy: str, lang: str
) -> dsl_analysis.CustomAnalysis:
    """We want to index taxonomies terms as keywords (as we only store the id),
    but with a specific tweak: transform hyphens into underscores,
    """
    # does not really depends on taxonomy and lang
    return analyzer(
        "taxonomy_indexing",
        tokenizer="keyword",
        char_filter=[TAXONOMIES_CHAR_FILTER],
    )


def get_taxonomy_search_analyzer(
    config: IndexConfig, taxonomy: str, lang: str, with_synonyms: bool
) -> dsl_analysis.CustomAnalysis:
    """Return the search analyzer to use for the taxonomized field

    :param taxonomy: the taxonomy name
    :param lang: the language code
    :param with_synonyms: whether to add the synonym filter
    """
    # we replace hyphen with  underscore
    filters: list[str | token_filter] = [
        "lowercase",
    ]
    stop_words = get_taxonomy_stop_words_filter(taxonomy, lang)
    if stop_words:
        filters.append(stop_words)
    filters.append(SPECIAL_NORMALIZERS.get(lang, "asciifolding"))
    if with_synonyms:
        filters.extend(
            iter_taxonomy_synonyms_filters(config, taxonomy, lang),
        )
    return analyzer(
        f"search_{taxonomy}_{lang}",
        char_filter=[TAXONOMIES_CHAR_FILTER],
        tokenizer="standard",
        filter=filters,
    )


def get_autocomplete_analyzer(lang: str) -> dsl_analysis.CustomAnalysis:
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
