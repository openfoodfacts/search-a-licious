import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config.settings import Settings

REPO_ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("value", ["", " ", "  \t"])
def test_empty_config_path_is_not_set(value):
    assert Settings(config_path=value).config_path is None


@pytest.mark.parametrize("value", ["", " "])
def test_empty_config_path_envvar_is_not_set(monkeypatch, value):
    """What `CONFIG_PATH=` in the .env file gives"""
    monkeypatch.setenv("CONFIG_PATH", value)
    assert Settings().config_path is None


def test_config_path_is_kept(monkeypatch):
    monkeypatch.setenv("CONFIG_PATH", "data/config/openfoodfacts.yml")
    assert Settings().config_path == Path("data/config/openfoodfacts.yml")


def test_config_path_default_is_not_set(monkeypatch):
    monkeypatch.delenv("CONFIG_PATH", raising=False)
    assert Settings().config_path is None


def _python(code: str, config_path: str) -> subprocess.CompletedProcess:
    """Run python in a new process (`app.config` reads its settings on import)"""
    env = {**os.environ, "CONFIG_PATH": config_path}
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize("value", ["", " "])
def test_import_with_empty_config_path(value):
    """It used to fail with "config file does not exist: ." """
    result = _python("import app.config", value)
    assert result.returncode == 0, result.stderr


def test_get_config_without_config_path_explains_what_to_do():
    result = _python("from app.config import get_config; get_config()", "")
    assert result.returncode != 0
    assert "No configuration is configured" in result.stderr


def test_import_with_missing_config_file_still_fails():
    result = _python("import app.config", "data/config/does-not-exist.yml")
    assert result.returncode != 0
    assert "config file does not exist" in result.stderr
