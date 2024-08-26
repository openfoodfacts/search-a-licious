import glob
import sys
import traceback

from typer.testing import CliRunner

from app.cli.main import cli

runner = CliRunner(mix_stderr=False)


def add_exc_info(result):
    if result.exc_code != 0:
        print("".join(traceback.format_exception(*result.exc_info)), file=sys.stderr)


def test_import_taxonomies(test_off_config, es_connection):
    result = runner.invoke(cli, ["import-taxonomies"])
    add_exc_info(result)
    assert result.exit_code == 0
    assert "Import time" in result.stderr
    assert "Synonyms generation time" in result.stderr
    # assert we got the index with the right
    es_connection
    # assert synonyms files gets generated
    assert sorted(glob.glob("/opt/search/synonyms/*/*")) == [
        "/opt/search/synonyms/categories/en.txt",
        "/opt/search/synonyms/categories/fr.txt",
        "/opt/search/synonyms/categories/main.txt",
        "/opt/search/synonyms/labels/en.txt",
        "/opt/search/synonyms/labels/fr.txt",
        "/opt/search/synonyms/labels/main.txt",
    ]
