from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Union

import requests

from app.types import JSONType
from app.utils import get_logger
from app.utils.download import (
    download_file,
    fetch_etag,
    get_file_etag,
    http_session,
    should_download_file,
)
from app.utils.io import load_json

DEFAULT_CACHE_DIR = Path("~/.cache/search-a-licious/taxonomy").expanduser()


logger = get_logger(__name__)


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


class TaxonomyNode:
    """A taxonomy element.

    Each node has 0+ parents and 0+ children. Each node has the following
    attributes:

    - `id`: the node identifier, it starts with a language prefix (ex: `en:`)
    - `names`: a dict mapping language 2-letter code to the node name for this
      language
    - `parents`: the list of the node parents
    - `children`: the list of the node children
    - `properties`: additional properties of the node (taxonomy-dependent)
    - `synonyms`: a dict mapping language 2-letter code to a list of synonyms
      for this language
    """

    __slots__ = ("id", "names", "parents", "children", "synonyms", "properties")

    def __init__(
        self,
        identifier: str,
        names: Dict[str, str],
        synonyms: Optional[Dict[str, List[str]]],
        properties: Optional[Dict[str, Any]] = None,
    ):
        self.id: str = identifier
        self.names: Dict[str, str] = names
        self.parents: List["TaxonomyNode"] = []
        self.children: List["TaxonomyNode"] = []
        self.properties = properties or {}

        if synonyms:
            self.synonyms = synonyms
        else:
            self.synonyms = {}

    def is_child_of(self, item: "TaxonomyNode") -> bool:
        """Return True if `item` is a child of `self` in the taxonomy."""
        if not self.parents:
            return False

        if item in self.parents:
            return True

        for parent in self.parents:
            is_parent = parent.is_child_of(item)

            if is_parent:
                return True

        return False

    def is_parent_of(self, candidate: "TaxonomyNode") -> bool:
        """Return True if `self` is parent of `candidate`, False otherwise.

        :param candidate: a TaxonomyNode of the same Taxonomy
        """
        return candidate.is_child_of(self)

    def is_parent_of_any(self, candidates: Iterable["TaxonomyNode"]) -> bool:
        """Return True if `self` is a parent of any of `candidates`, False
        otherwise.

        :param candidates: an iterable of TaxonomyNodes of the same Taxonomy
        """
        for candidate in candidates:
            if candidate.is_child_of(self):
                return True

        return False

    def get_parents_hierarchy(self) -> List["TaxonomyNode"]:
        """Return the list of all parent nodes (direct and indirect)."""
        all_parents = []
        seen: Set[str] = set()

        if not self.parents:
            return []

        for self_parent in self.parents:
            if self_parent.id not in seen:
                all_parents.append(self_parent)
                seen.add(self_parent.id)

            for parent_parent in self_parent.get_parents_hierarchy():
                if parent_parent.id not in seen:
                    all_parents.append(parent_parent)
                    seen.add(parent_parent.id)

        return all_parents

    def get_localized_name(self, lang: str, add_xx: bool = False) -> str | None:
        """Return the localized name of the node.

        We first check if there is an entry in `names` under the provided
        `lang`. Otherwise, we check the existence of an international name
        (`xx`) if `add_xx=True`. We return None if both checks failed.

        :param lang: the language code
        """
        if lang in self.names:
            return self.names[lang]

        if add_xx and "xx" in self.names:
            # Return international name if it exists
            return self.names["xx"]

        return None

    def get_synonyms(self, lang: str) -> List[str]:
        return self.synonyms.get(lang, [])

    def add_parents(self, parents: Iterable["TaxonomyNode"]):
        for parent in parents:
            if parent not in self.parents:
                self.parents.append(parent)
                parent.children.append(self)

    def to_dict(self) -> JSONType:
        return {"name": self.names, "parents": [p.id for p in self.parents]}

    def __repr__(self):
        return "<TaxonomyNode %s>" % self.id


class Taxonomy:
    """A class representing a taxonomy.

    For more information about taxonomy, see
    https://wiki.openfoodfacts.org/Global_taxonomies.

    A Taxonomy instance has only a single `nodes` attribute, that maps the
    node identifier to a `TaxonomyNode`.
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, TaxonomyNode] = {}

    def add(self, key: str, node: TaxonomyNode) -> None:
        """Add a node to the taxonomy under the id `key`.

        :param key: The node id
        :param node: the TaxonomyNode
        """
        self.nodes[key] = node

    def __contains__(self, item: str):
        """Return True if `item` (a taxonomy id) is in the taxonomy, False
        otherwise."""
        return item in self.nodes

    def __getitem__(self, item: str):
        return self.nodes.get(item)

    def __len__(self) -> int:
        """Return the number of items in the taxonomy."""
        return len(self.nodes)

    def iter_nodes(self) -> Iterable[TaxonomyNode]:
        """Iterate over the nodes of the taxonomy."""
        return iter(self.nodes.values())

    def keys(self) -> Iterable[str]:
        """Return all node IDs from the taxonomy."""
        return self.nodes.keys()

    def find_deepest_nodes(self, nodes: List[TaxonomyNode]) -> List[TaxonomyNode]:
        """Given a list of nodes, returns the list of nodes where all the
        parents within the list have been removed.

        For example, for a taxonomy, 'fish' -> 'salmon' -> 'smoked-salmon':

        ['fish', 'salmon'] -> ['salmon'] ['fish', 'smoked-salmon'] ->
        [smoked-salmon']
        """
        excluded: Set[str] = set()

        for node in nodes:
            for second_node in (
                n for n in nodes if n.id not in excluded and n.id != node.id
            ):
                if node.is_child_of(second_node):
                    excluded.add(second_node.id)

        return [node for node in nodes if node.id not in excluded]

    def is_parent_of_any(
        self, item: str, candidates: Iterable[str], raises: bool = True
    ) -> bool:
        """Return True if `item` is parent of any candidate, False otherwise.

        If the item is not in the taxonomy and raises is False, return False.

        :param item: The item to compare
        :param candidates: A list of candidates
        :param raises: if True, raises a ValueError if item is not in the
        taxonomy, defaults to True.
        """
        node: TaxonomyNode = self[item]

        if node is None:
            if raises:
                raise ValueError("unknown id in taxonomy: %s", node)
            else:
                return False

        to_check_nodes: Set[TaxonomyNode] = set()

        for candidate in candidates:
            candidate_node = self[candidate]

            if candidate_node is not None:
                to_check_nodes.add(candidate_node)

        return node.is_parent_of_any(to_check_nodes)

    def get_localized_name(self, key: str, lang: str) -> str | None:
        """Return the name of a taxonomy element in a given language.

        If `key` is not in the taxonomy or if no name is available for the
        requested language, return None.

        :param key: the taxonomy element id
        :param lang: the 2-letter language code
        :return: the localized name or None
        """
        if key not in self.nodes:
            return None

        return self.nodes[key].get_localized_name(lang)

    def to_dict(self) -> JSONType:
        """Generate a dict from the Taxonomy."""
        export = {}

        for key, node in self.nodes.items():
            export[key] = node.to_dict()

        return export

    @classmethod
    def from_dict(cls, data: JSONType) -> "Taxonomy":
        """Create a Taxonomy from `data`.

        :param data: the taxonomy as a dict
        :return: a Taxonomy
        """
        taxonomy = Taxonomy()

        for key, key_data in data.items():
            if key not in taxonomy:
                node = TaxonomyNode(
                    identifier=key,
                    names=key_data.get("name", {}),
                    synonyms=key_data.get("synonyms", None),
                    properties={
                        k: v
                        for k, v in key_data.items()
                        if k not in {"parents", "name", "synonyms", "children"}
                    },
                )
                taxonomy.add(key, node)

        for key, key_data in data.items():
            node = taxonomy[key]
            parents = [taxonomy[ref] for ref in key_data.get("parents", [])]
            node.add_parents(parents)

        return taxonomy

    @classmethod
    def from_path(cls, file_path: Union[str, Path]) -> "Taxonomy":
        """Create a Taxonomy from a JSON file.

        :param file_path: a JSON file, gzipped (.json.gz) files are supported
        :return: a Taxonomy
        """
        return cls.from_dict(load_json(file_path))  # type: ignore

    @classmethod
    def from_url(
        cls, url: str, session: Optional[requests.Session] = None, timeout: int = 120
    ) -> "Taxonomy":
        """Create a Taxonomy from a taxonomy file hosted at `url`.

        :param url: the URL of the taxonomy
        :param session: the requests session, use a default session if None
        :param timeout: the request timeout, defaults to 120
        :return: a Taxonomy
        """
        session = http_session if session is None else session
        r = session.get(url, timeout=timeout)
        data = r.json()
        return cls.from_dict(data)


def get_taxonomy(
    taxonomy_name: str,
    taxonomy_url: str,
    force_download: bool = False,
    download_newer: bool = False,
    cache_dir: Optional[Path] = None,
) -> Taxonomy:
    """Return the taxonomy of the provided name.

    The taxonomy file is downloaded and cached locally.

    :param taxonomy_name: the requested taxonomy name
    :param taxonomy_url: the URL of the taxonomy
    :param force_download: if True, (re)download the taxonomy even if it was
        cached, defaults to False
    :param download_newer: if True, download the taxonomy if a more recent
        version is available (based on file Etag)
    :param cache_dir: the cache directory to use, defaults to
        ~/.cache/openfoodfacts/taxonomy
    :return: a Taxonomy
    """
    filename = f"{taxonomy_name}.json"

    cache_dir = DEFAULT_CACHE_DIR if cache_dir is None else cache_dir
    taxonomy_path = cache_dir / filename

    if not should_download_file(
        taxonomy_url, taxonomy_path, force_download, download_newer
    ):
        return Taxonomy.from_path(taxonomy_path)

    cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading taxonomy, saving it in %s", taxonomy_path)
    download_file(taxonomy_url, taxonomy_path)
    return Taxonomy.from_path(taxonomy_path)
