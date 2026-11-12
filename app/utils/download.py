"""Various utilities for downloading files

Used for example for downloading taxonomies
"""

import json
import shutil
import time
from pathlib import Path
from typing import Optional

import requests
import tqdm

from ..config import settings
from .log import get_logger

logger = get_logger(__name__)

http_session = requests.Session()
http_session.headers.update({"User-Agent": settings.user_agent})

# Timeouts of a download, in seconds: (connect, wait for the next bytes)
DOWNLOAD_TIMEOUT = (10, 60)
# Statuses for which trying again may work: rate limiting, temporary errors
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
# Number of tries for a download, and maximum wait between two tries (seconds)
DOWNLOAD_MAX_ATTEMPTS = 4
DOWNLOAD_MAX_RETRY_DELAY = 60


def _sanitize_file_path(file_path: Path, suffix: str = "") -> Path:
    """A internal function to normalize cached filenames.

    :param file_path: the cached file path
    :param suffix: a optional filename suffix to add
    :return: a sanitized filepath
    """
    return file_path.with_name(file_path.name.replace(".", "_") + suffix)


def get_file_etag(dataset_path: Path) -> Optional[str]:
    """Return a dataset Etag.

    :param dataset_path: the path of the dataset
    :return: the file Etag
    """
    metadata_path = _sanitize_file_path(dataset_path, ".json")

    if metadata_path.is_file():
        return json.loads(metadata_path.read_text())["etag"]

    return None


def fetch_etag(url: str) -> str:
    """Get the Etag of a remote file.

    :param url: the file URL
    :return: the Etag
    """
    r = http_session.head(url)
    return r.headers.get("ETag", "").strip("'\"")


def should_download_file(
    url: str, filepath: Path, force_download: bool, download_newer: bool
) -> bool:
    """Return True if the file located at `url` should be downloaded again
    based on file Etag.

    :param url: the file URL
    :param filepath: the file cached location
    :param force_download: if True, (re)download the file even if it was
        cached, defaults to False
    :param download_newer: if True, download the file if a more recent
        version is available (based on file Etag)
    :return: True if the file should be downloaded again, False otherwise
    """
    if filepath.is_file():
        if not force_download:
            return False

        if download_newer:
            cached_etag = get_file_etag(filepath)
            current_etag = fetch_etag(url)

            if cached_etag == current_etag:
                # The file is up to date, return cached file path
                return False

    return True


def _retry_delay(response: requests.Response | None, attempt: int) -> float:
    """Seconds to wait before the next try.

    This is the `Retry-After` of the server if it gave one (in seconds),
    otherwise 2, 4, 8... seconds, never more than `DOWNLOAD_MAX_RETRY_DELAY`.

    :param response: the response that made us retry, if we got one
    :param attempt: the number of the try that just failed (starting at 1)
    """
    delay = float(2**attempt)
    if response is not None:
        retry_after = response.headers.get("Retry-After", "").strip()
        if retry_after.isdigit():
            delay = float(retry_after)
    return min(delay, DOWNLOAD_MAX_RETRY_DELAY)


def _get_stream(url: str) -> requests.Response:
    """Start downloading `url`, and return the response if it is successful.

    Rate limiting (429), temporary server errors and connection problems are
    tried again a few times, with a pause. Any other error status (like 404)
    is not.

    :raises requests.HTTPError: if the server did not answer with a success
    :raises requests.ConnectionError: if the server can not be reached
    """
    for attempt in range(1, DOWNLOAD_MAX_ATTEMPTS + 1):
        response = None
        try:
            response = http_session.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt == DOWNLOAD_MAX_ATTEMPTS:
                raise
            reason = type(exc).__name__
        else:
            if (
                response.status_code in RETRY_STATUSES
                and attempt < DOWNLOAD_MAX_ATTEMPTS
            ):
                reason = f"HTTP {response.status_code}"
            else:
                # success, an error that waiting will not fix,
                # or the last try: raises for an error status
                try:
                    response.raise_for_status()
                except requests.HTTPError:
                    response.close()
                    raise
                return response
        delay = _retry_delay(response, attempt)
        if response is not None:
            response.close()
        logger.warning(
            "Download of %s failed (%s), trying again in %.0f s (try %d of %d)",
            url,
            reason,
            delay,
            attempt,
            DOWNLOAD_MAX_ATTEMPTS,
        )
        time.sleep(delay)
    raise RuntimeError("unreachable: the last try returns or raises")


def download_file(url: str, output_path: Path):
    """Download a dataset file and store it in `output_path`.

    Nothing is written to `output_path` unless the whole file was downloaded
    from a successful response: an error page is never stored as the file.

    The file metadata (`etag`, `url`, `created_at`) are stored in a JSON
        file whose name is derived from `output_path`
    :param url: the file URL
    :param output_path: the file output path
    :raises requests.HTTPError: if the server did not answer with a success
        (after a few tries for rate limiting and temporary errors)
    """
    r = _get_stream(url)
    etag = r.headers.get("ETag", "").strip("'\"")

    tmp_output_path = output_path.with_name(output_path.name + ".part")
    try:
        with (
            tmp_output_path.open("wb") as f,
            tqdm.tqdm(
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                miniters=1,
                desc=str(output_path),
                total=int(r.headers.get("content-length", 0)),
            ) as pbar,
        ):
            for chunk in r.iter_content(chunk_size=4096):
                f.write(chunk)
                pbar.update(len(chunk))

        shutil.move(tmp_output_path, output_path)
    finally:
        r.close()
        # does nothing once moved; removes a partial file if the download failed
        tmp_output_path.unlink(missing_ok=True)

    _sanitize_file_path(output_path, ".json").write_text(
        json.dumps(
            {
                "etag": etag,
                "created_at": int(time.time()),
                "url": url,
            }
        )
    )
