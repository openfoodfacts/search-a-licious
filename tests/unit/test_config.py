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
        # facets
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


def _config_with_aggs(tmpdir, facets=""):
    my_config = tmpdir / "config.yaml"
    conf_content = BASE_CONFIG.replace("        # more fields\n", AGGS_FIELDS)
    conf_content = conf_content.replace("        # facets\n", facets + "\n")
    open(my_config, "w").write(conf_content)
    return my_config


def test_facets_default_created(tmpdir):
    conf_file = _config_with_aggs(tmpdir)
    conf = app.config.Config.from_yaml(conf_file)
    assert conf.indices["test"].facets == {
        "default": app.config.FacetsConfig(
            name="default", include=None, exclude=None, order=None
        )
    }


def test_facets_with_include(tmpdir):
    facets = """
        facets:
            default:
                include: ["somuch_agg", "myagg", "more_agg"]
    """
    conf_file = _config_with_aggs(tmpdir, facets)
    conf = app.config.Config.from_yaml(conf_file)
    # only included, alpha sort
    assert conf.indices["test"].get_facets_order() == [
        "more_agg",
        "myagg",
        "somuch_agg",
    ]


def test_facets_with_exclude(tmpdir):
    facets = """
        facets:
            default:
                exclude: ["myagg", "more_agg"]
    """
    conf_file = _config_with_aggs(tmpdir, facets)
    conf = app.config.Config.from_yaml(conf_file)
    # without excluded, alpha sort
    assert conf.indices["test"].get_facets_order() == ["other_agg", "somuch_agg"]


def test_facets_order_no_ellipsis(tmpdir):
    facets = """
        facets:
            default:
                order: ["myagg", "somuch_agg"]
    """
    conf_file = _config_with_aggs(tmpdir, facets)
    conf = app.config.Config.from_yaml(conf_file)
    # at end
    assert conf.indices["test"].get_facets_order() == [
        "myagg",
        "somuch_agg",
        "more_agg",
        "other_agg",
    ]


def test_facets_order_with_end_ellipsis(tmpdir):
    facets = """
        facets:
            default:
                order: ["myagg", "somuch_agg", "..."]
    """
    conf_file = _config_with_aggs(tmpdir, facets)
    conf = app.config.Config.from_yaml(conf_file)
    # at end
    assert conf.indices["test"].get_facets_order() == [
        "myagg",
        "somuch_agg",
        "more_agg",
        "other_agg",
    ]


def test_facets_order_with_ellipsis(tmpdir):
    facets = """
        facets:
            default:
                order: ["myagg", "...", "more_agg"]
    """
    conf_file = _config_with_aggs(tmpdir, facets)
    conf = app.config.Config.from_yaml(conf_file)
    assert conf.indices["test"].get_facets_order() == [
        "myagg",
        "other_agg",
        "somuch_agg",
        "more_agg",
    ]


def test_facets_order_with_start_ellipsis(tmpdir):
    facets = """
        facets:
            default:
                order: ["...", "myagg", "more_agg"]
    """
    conf_file = _config_with_aggs(tmpdir, facets)
    conf = app.config.Config.from_yaml(conf_file)
    assert conf.indices["test"].get_facets_order() == [
        "other_agg",
        "somuch_agg",
        "myagg",
        "more_agg",
    ]
