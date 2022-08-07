from __future__ import annotations
AUTOCOMPLETE_FIELDS = ['product_name', 'brands', 'categories']
REQUIRED_FIELDS = ['code', 'last_indexed_datetime']
INDEX_ALIAS = 'openfoodfacts'
INDEX_ALIAS_PATTERN = INDEX_ALIAS + '-*'
MAX_RESULTS = 100
REDIS_EXPIRATION = 60 * 60 * 36  # 36 hours
REDIS_READER_TIMEOUT = 5
