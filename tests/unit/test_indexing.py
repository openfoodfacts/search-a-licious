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
                "product_name_pt_PT": "pt-PT",
            },
            "product_name",
            False,
            {
                "fr": "FR",
                "it": "IT",
                "pt-BR": "pt-BR",
                "PT": "pt-PT",
                "main": "MAIN",
            },
        )
    ],
)
def test_process_text_lang_field(data, input_field, split, expected):
    lang_separator = "_"
    split_separator = ","
    assert (
        process_text_lang_field(
            data,
            input_field,
            split=split,
            lang_separator=lang_separator,
            split_separator=split_separator,
        )
        == expected
    )
