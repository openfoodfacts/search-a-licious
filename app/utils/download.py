import json
import shutil
import time
from pathlib import Path
from typing import Optional

import requests
import tqdm

from ..config import settings

http_session = requests.Session()
http_session.headers.update({"User-Agent": settings.user_agent})


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


def download_file(url: str, output_path: Path):
    """Download a dataset file and store it in `output_path`.

    The file metadata (`etag`, `url`, `created_at`) are stored in a JSON
        file whose name is derived from `output_path`
    :param url: the file URL
    :param output_path: the file output path
    """
    r = http_session.get(url, stream=True)
    etag = r.headers.get("ETag", "").strip("'\"")

    tmp_output_path = output_path.with_name(output_path.name + ".part")
    with tmp_output_path.open("wb") as f, tqdm.tqdm(
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        miniters=1,
        desc=str(output_path),
        total=int(r.headers.get("content-length", 0)),
    ) as pbar:
        for chunk in r.iter_content(chunk_size=4096):
            f.write(chunk)
            pbar.update(len(chunk))

    shutil.move(tmp_output_path, output_path)

    _sanitize_file_path(output_path, ".json").write_text(
        json.dumps(
            {
                "etag": etag,
                "created_at": int(time.time()),
                "url": url,
            }
        )
    )
