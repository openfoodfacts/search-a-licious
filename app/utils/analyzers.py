"""Defines some analyzers for the elesaticsearch fields."""

from elasticsearch_dsl import analyzer

#: An analyzer for the autocomplete field
AUTOCOMPLETE_ANALYZERS = {
    "fr": analyzer(
        "autocomplete_fr", tokenizer="standard", filter=["lowercase", "asciifolding"]
    ),
    "de": analyzer(
        "autocomplete_de",
        tokenizer="standard",
        filter=["lowercase", "german_normalization"],
    ),
}
