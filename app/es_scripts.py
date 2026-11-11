"""Module to manage ES scripts that can be used for personalized sorting"""

import elasticsearch

from app import config
from app.utils import connection, get_logger

logger = get_logger(__name__)


def get_script_prefix(index_id: str):
    """We prefix scripts specific to an index with the index_id."""
    return f"{index_id}__"


def get_script_id(index_id: str, script_id: str):
    """We prefix scripts specific to an index with the index_id."""
    return f"{index_id}__{script_id}"


def _list_stored_scripts(index_config: config.IndexConfig, prefix: str) -> list[str]:
    """List Elasticsearch stored scripts filtered by a prefix."""
    es = connection.current_es_client()
    metadata = es.cluster.state(metric="metadata")["metadata"]
    scripts = metadata.get("stored_scripts") or {}
    # search all stored_scripts starting with this index name
    return [k for k in scripts.keys() if k.startswith(prefix)]


def _remove_scripts(scripts_ids: list[str], index_config: config.IndexConfig):
    """Remove scripts from Elasticsearch."""
    es = connection.current_es_client()
    for script_id in scripts_ids:
        es.delete_script(id=script_id)


def _store_script(
    script_id: str, script: config.ScriptConfig, index_config: config.IndexConfig
):
    """Store a script in Elasticsearch."""
    params = dict((script.params or {}), **(script.static_params or {}))
    payload = {
        "lang": script.lang.value,
        "source": script.source,
        "params": params,
    }
    # hardcode context to scoring for the moment
    context = "score"
    es = connection.current_es_client()
    es.put_script(id=script_id, script=payload, context=context)


def sync_scripts(index_id: str, index_config: config.IndexConfig) -> dict[str, int]:
    """Resync the scripts between configuration and elasticsearch.

    The configured scripts are stored first (a script is created, or replaced
    if it exists), then the scripts of this index that are not configured any
    more are removed. So a configured script is never missing, and one that
    can not be stored keeps its previous version.

    :return: the number of scripts `removed` (the ones no longer configured)
        and `added` (the ones stored)
    """
    # list existing
    current_ids = _list_stored_scripts(index_config, prefix=get_script_prefix(index_id))
    # store scripts
    configured_ids = set()
    stored_scripts = 0
    for script_id, script in (index_config.scripts or {}).items():
        stored_id = get_script_id(index_id, script_id)
        configured_ids.add(stored_id)
        try:
            _store_script(stored_id, script, index_config)
            stored_scripts += 1
        except elasticsearch.ApiError as e:
            logger.error(
                "Unable to store script %s, got exception %s: %s",
                script_id,
                e,
                e.body,
            )
    # remove the scripts that are not configured any more
    removed_ids = [id_ for id_ in current_ids if id_ not in configured_ids]
    _remove_scripts(removed_ids, index_config)
    return {"removed": len(removed_ids), "added": stored_scripts}
