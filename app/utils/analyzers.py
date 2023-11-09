from elasticsearch_dsl import analyzer

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
