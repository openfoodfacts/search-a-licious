import io
import json
from pathlib import Path

import pytest
import requests

from app.taxonomy import get_taxonomy
from app.utils import download
from app.utils.download import (
    DOWNLOAD_MAX_ATTEMPTS,
    DOWNLOAD_MAX_RETRY_DELAY,
    download_file,
)

URL = "https://example.org/data/origins.full.json"
BODY = b'{"en:france": {"name": {"en": "France"}}}'


def _response(
    status: int = 200,
    body: bytes = BODY,
    headers: dict | None = None,
    cls: type[requests.Response] = requests.Response,
) -> requests.Response:
    """A response like the one of a real server: the body is read from `raw`"""
    response = cls()
    response.status_code = status
    response.reason = {429: "Too Many Requests", 404: "Not Found"}.get(status, "")
    response.url = URL
    response.raw = io.BytesIO(body)
    response.headers.update(headers or {})
    return response


class _BrokenBody(requests.Response):
    """A response whose body fails after the first chunk"""

    def iter_content(self, chunk_size=1, decode_unicode=False):
        yield b'{"en:fra'
        raise requests.exceptions.ChunkedEncodingError("connection broken")


@pytest.fixture
def server(monkeypatch):
    """Replace the HTTP session: answers are taken in turn from `server.answers`
    (an exception is raised instead of returned), pauses are recorded"""

    class Server:
        def __init__(self):
            self.answers: list = []
            self.calls = 0
            self.sleeps: list[float] = []

    srv = Server()

    def get(url, **kwargs):
        assert kwargs["timeout"] == download.DOWNLOAD_TIMEOUT
        answer = srv.answers[min(srv.calls, len(srv.answers) - 1)]
        srv.calls += 1
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(download.http_session, "get", get)
    monkeypatch.setattr(download.time, "sleep", srv.sleeps.append)
    return srv


def _nothing_left(path: Path):
    """No file, no partial file and no metadata next to `path`"""
    assert list(path.parent.iterdir()) == []


def test_download_file_success(server, tmp_path):
    server.answers = [_response(headers={"ETag": '"abc"'})]
    output = tmp_path / "origins.json"
    download_file(URL, output)
    assert output.read_bytes() == BODY
    metadata = json.loads((tmp_path / "origins_json.json").read_text())
    assert metadata["etag"] == "abc"
    assert metadata["url"] == URL
    assert not (tmp_path / "origins.json.part").exists()
    assert server.sleeps == []


def test_download_file_rate_limit_then_success(server, tmp_path):
    server.answers = [
        _response(429, b"<html>429</html>", {"Retry-After": "7"}),
        _response(),
    ]
    output = tmp_path / "origins.json"
    download_file(URL, output)
    assert output.read_bytes() == BODY
    assert server.calls == 2
    assert server.sleeps == [7.0]


def test_download_file_backoff_without_retry_after(server, tmp_path):
    server.answers = [_response(503), _response(502), _response()]
    download_file(URL, tmp_path / "origins.json")
    assert server.calls == 3
    assert server.sleeps == [2.0, 4.0]


def test_download_file_retry_after_is_capped(server, tmp_path):
    server.answers = [_response(429, headers={"Retry-After": "86400"}), _response()]
    download_file(URL, tmp_path / "origins.json")
    assert server.sleeps == [float(DOWNLOAD_MAX_RETRY_DELAY)]


@pytest.mark.parametrize("status", [429, 500, 503])
def test_download_file_gives_up_and_stores_nothing(server, tmp_path, status):
    """The error page of the last try must never end up as the file"""
    output = tmp_path / "cache" / "origins.json"
    output.parent.mkdir()
    server.answers = [_response(status, b"<html>error page</html>")]
    with pytest.raises(requests.HTTPError):
        download_file(URL, output)
    assert server.calls == DOWNLOAD_MAX_ATTEMPTS
    assert len(server.sleeps) == DOWNLOAD_MAX_ATTEMPTS - 1
    _nothing_left(output)


def test_download_file_does_not_retry_not_found(server, tmp_path):
    output = tmp_path / "cache" / "origins.json"
    output.parent.mkdir()
    server.answers = [_response(404, b"not found")]
    with pytest.raises(requests.HTTPError):
        download_file(URL, output)
    assert server.calls == 1
    assert server.sleeps == []
    _nothing_left(output)


def test_download_file_retries_connection_errors(server, tmp_path):
    server.answers = [
        requests.ConnectionError("reset"),
        requests.Timeout("slow"),
        _response(),
    ]
    output = tmp_path / "origins.json"
    download_file(URL, output)
    assert output.read_bytes() == BODY
    assert server.sleeps == [2.0, 4.0]


def test_download_file_connection_error_is_raised_in_the_end(server, tmp_path):
    output = tmp_path / "cache" / "origins.json"
    output.parent.mkdir()
    server.answers = [requests.Timeout("slow")]
    with pytest.raises(requests.Timeout):
        download_file(URL, output)
    assert server.calls == DOWNLOAD_MAX_ATTEMPTS
    _nothing_left(output)


def test_download_file_body_failure_leaves_no_file(server, tmp_path):
    output = tmp_path / "cache" / "origins.json"
    output.parent.mkdir()
    server.answers = [_response(cls=_BrokenBody)]
    with pytest.raises(requests.exceptions.ChunkedEncodingError):
        download_file(URL, output)
    _nothing_left(output)


def test_get_taxonomy_does_not_cache_an_error_page(server, tmp_path):
    """A 429 used to be saved as the taxonomy: the next runs failed on it too"""
    server.answers = [_response(429, b"<html>429 Too Many Requests</html>")]
    with pytest.raises(requests.HTTPError):
        get_taxonomy("origins", URL, cache_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []

    # the host recovers: the next run downloads and parses the taxonomy
    server.calls = 0
    server.answers = [_response(body=json.dumps({}).encode())]
    taxonomy = get_taxonomy("origins", URL, cache_dir=tmp_path)
    assert (tmp_path / "origins.json").exists()
    assert taxonomy.name == "origins"
