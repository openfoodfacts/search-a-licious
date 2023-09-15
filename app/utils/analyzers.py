from __future__ import annotations

from elasticsearch_dsl import analyzer, tokenizer

autocomplete = analyzer(
    "autocomplete",
    tokenizer=tokenizer(
        "bigram",
        "edge_ngram",
        min_gram=2,
        max_gram=25,
        token_chars=[
            "letter",
            "digit",
            "punctuation",
        ],
    ),
    filter=["lowercase", "asciifolding"],
)

text_like = analyzer(
    "text_like",
    tokenizer="standard",
    filter=["snowball", "lowercase", "asciifolding"],
)


# Mapping from language 2-letter code to Elasticsearch language analyzer names
ANALYZER_LANG_MAPPING = {
    "en": "english",
    "fr": "french",
    "it": "italian",
    "es": "spanish",
    "de": "german",
    "nl": "dutch",
    "ar": "arabic",
    "hy": "armenian",
    "eu": "basque",
    "bn": "bengali",
    "pt-BR": "brazilian",
    "bg": "bulgarian",
    "ca": "catalan",
    "cz": "czech",
    "da": "danish",
    "et": "estonian",
    "fi": "finnish",
    "gl": "galician",
    "el": "greek",
    "hi": "hindi",
    "hu": "hungarian",
    "id": "indonesian",
    "ga": "irish",
    "lv": "latvian",
    "lt": "lithuanian",
    "no": "norwegian",
    "fa": "persian",
    "pt": "portuguese",
    "ro": "romanian",
    "ru": "russian",
    "sv": "swedish",
    "tr": "turkish",
    "th": "thai",
}
