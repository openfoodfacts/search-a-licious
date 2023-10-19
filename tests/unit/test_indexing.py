import pytest

from app.indexing import process_text_lang_field


@pytest.mark.parametrize(
    "data,input_field,split,expected",
    [
        (
            {
                "product_name": "MAIN",
                "product_name_fr": "FR",
                "product_name_it": "IT",
                "product_name_pt-BR": "pt-BR",
                "product_name_pt": "pt-PT",
                "product_name_vn": "VN",
                "product_name_id": "ID",
            },
            "product_name",
            False,
            {
                "fr": "FR",
                "it": "IT",
                "pt-BR": "pt-BR",
                "pt": "pt-PT",
                "main": "MAIN",
                "other": ["VN", "ID"],
            },
        )
    ],
)
def test_process_text_lang_field(data, input_field, split, expected):
    lang_separator = "_"
    split_separator = ","
    supported_langs = {"fr", "it", "pt-BR", "pt"}
    assert (
        process_text_lang_field(
            data=data,
            input_field=input_field,
            split=split,
            lang_separator=lang_separator,
            split_separator=split_separator,
            supported_langs=supported_langs,
        )
        == expected
    )
