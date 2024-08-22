import pytest

import app.config

BASE_CONFIG = """
indices:
    test:
        index:
            number_of_replicas: 1
            number_of_shards: 1
            name: test_index
            id_field_name: mykey
            last_modified_field_name: last_modified
        fields:
            mykey:
                required: true
                type: keyword
            mybool:
                required: true
                type: bool
            last_modified:
                required: true
                type: date
            mytext:
                full_text_search: true
                type: text_lang
            myagg:
                required: true
                type: keyword
                bucket_agg: true
            # more fields
        supported_langs: ["en", "fr"]
        taxonomy:
            sources: []
            exported_langs: []
            index:
                number_of_replicas: 1
                number_of_shards: 1
                name: test_taxonomy
        document_fetcher: app._import.BaseDocumentFetcher
default_index: test
"""

AGGS_FIELDS = """
            other_agg:
                type: keyword
                bucket_agg: true
            more_agg:
                type: keyword
                bucket_agg: true
            somuch_agg:
                type: keyword
                bucket_agg: true
"""

RESERVED_FIELDS = """
            last_indexed_datetime:
                type: date
            _id:
                type: keyword
"""


def _config_with_aggs(tmpdir, facets=""):
    my_config = tmpdir / "config.yaml"
    conf_content = BASE_CONFIG.replace("        # more fields\n", AGGS_FIELDS)
    conf_content = conf_content.replace("        # facets\n", facets + "\n")
    open(my_config, "w").write(conf_content)
    return my_config


def test_loading_config(tmpdir):
    conf_file = _config_with_aggs(tmpdir)
    # just test it loads for now
    app.config.Config.from_yaml(conf_file)
    # TODO add asserts on config


def test_reserved_field_names(tmpdir):
    """Test we can't use a reserved field name"""
    my_config = tmpdir / "config.yaml"
    conf_content = BASE_CONFIG.replace("        # more fields\n", RESERVED_FIELDS)
    open(my_config, "w").write(conf_content)
    with pytest.raises(ValueError) as excinfo:
        app.config.Config.from_yaml(my_config)
    assert "last_indexed_datetime" in str(excinfo.value)
    assert "_id" in str(excinfo.value)
