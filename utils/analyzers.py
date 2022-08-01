from elasticsearch_dsl import analyzer
from elasticsearch_dsl import tokenizer

autocomplete = analyzer(
    'autocomplete',
    tokenizer=tokenizer('bigram', 'edge_ngram', min_gram=2, max_gram=25, token_chars=['letter', 'digit', 'punctuation']),
    filter=['lowercase', 'asciifolding']
)