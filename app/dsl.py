from typing import Iterable
from elasticsearch_dsl import Double, Keyword, Object, Text, analyzer

from app.config import FieldConfig, FieldType
from app.utils.analyzers import ANALYZER_LANG_MAPPING


def generate_dsl_field(field: FieldConfig, supported_lang: Iterable[str]):
    if field.type in (FieldType.text_lang, FieldType.taxonomy):
        properties = {
            lang: Text(analyzer=analyzer(ANALYZER_LANG_MAPPING.get(lang, "standard")))
            for lang in supported_lang
        }
        return Object(dynamic=False, properties=properties)
    elif field.type == FieldType.keyword:
        return Keyword(required=field.required, multi=field.multi)
    elif field.type == FieldType.text:
        return Text(required=field.required, multi=field.multi)
    elif field.type == FieldType.double:
        return Double()
    else:
        raise ValueError("unsupported field type: %s" % field.type)
