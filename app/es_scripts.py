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
    """Resync the scripts between configuration and elasticsearch."""
    # list existing
    current_ids = _list_stored_scripts(index_config, prefix=get_script_prefix(index_id))
    # remove them
    _remove_scripts(current_ids, index_config)
    # store scripts
    stored_scripts = 0
    if index_config.scripts:
        for script_id, script in index_config.scripts.items():
            try:
                _store_script(get_script_id(index_id, script_id), script, index_config)
                stored_scripts += 1
            except elasticsearch.ApiError as e:
                logger.error(
                    "Unable to store script %s, got exception %s: %s",
                    script_id,
                    e,
                    e.body,
                )
    return {"removed": len(current_ids), "added": stored_scripts}
