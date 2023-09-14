from __future__ import annotations

from elasticsearch_dsl import analyzer
from elasticsearch_dsl import tokenizer

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
