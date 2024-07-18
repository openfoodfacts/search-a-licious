"""This module provides different commands to help
setting up search-a-licious
or doing maintenance operations.
"""

from pathlib import Path
from typing import Optional

import typer

import app

cli = typer.Typer()


INDEX_ID_HELP = (
    "Each index has its own configuration in the configuration file, "
    "and the ID is used to know which index to use. "
    "If there is only one index, this option is not needed."
)


def _get_index_config(
    config_path: Optional[Path], index_id: Optional[str]
) -> tuple[str, "app.config.IndexConfig"]:
    from typing import cast

    from app import config
    from app.config import check_config_is_defined, set_global_config

    if config_path:
        set_global_config(config_path)

    check_config_is_defined()
    global_config = cast(config.Config, config.CONFIG)
    index_id, index_config = global_config.get_index_config(index_id)
    if index_config is None:
        raise typer.BadParameter(
            "You must specify an index ID when there are multiple indices"
        )
    return index_id, index_config


@cli.command(name="import")
def import_data(
    input_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Path of the JSONL data file",
    ),
    skip_updates: bool = typer.Option(
        default=False,
        help="Skip fetching fresh records from redis",
    ),
    num_processes: int = typer.Option(
        default=2, help="How many import processes to run in parallel"
    ),
    num_items: Optional[int] = typer.Option(
        default=None, help="How many items to import"
    ),
    config_path: Optional[Path] = typer.Option(
        default=None,
        help="path of the yaml configuration file, it overrides CONFIG_PATH envvar",
        dir_okay=False,
        file_okay=True,
        exists=True,
    ),
    index_id: Optional[str] = typer.Option(
        default=None,
        help=INDEX_ID_HELP,
    ),
):
    """Import data into Elasticsearch.

    This command is used to initialize or refresh your index with data.

    File must contains one JSON document per line,
    each document must have same format as a document returned by the API.
    """
    import time

    from app._import import run_full_import
    from app.utils import get_logger

    logger = get_logger()

    start_time = time.perf_counter()
    index_id, index_config = _get_index_config(config_path, index_id)

    run_full_import(
        input_path,
        num_processes,
        index_config,
        num_items=num_items,
        skip_updates=skip_updates,
    )
    end_time = time.perf_counter()
    logger.info("Import time: %s seconds", end_time - start_time)


@cli.command()
def import_taxonomies(
    config_path: Optional[Path] = typer.Option(
        default=None,
        help="path of the yaml configuration file, it overrides CONFIG_PATH envvar",
        dir_okay=False,
        file_okay=True,
        exists=True,
    ),
    index_id: Optional[str] = typer.Option(
        default=None,
        help=INDEX_ID_HELP,
    ),
):
    """Import taxonomies into Elasticsearch.

    It get taxonomies json files as specified in the configuration file.
    """
    import time

    from app._import import perform_taxonomy_import
    from app.utils import get_logger

    logger = get_logger()

    index_id, index_config = _get_index_config(config_path, index_id)

    start_time = time.perf_counter()
    perform_taxonomy_import(index_config)
    end_time = time.perf_counter()
    logger.info("Import time: %s seconds", end_time - start_time)


@cli.command()
def sync_scripts(
    config_path: Optional[Path] = typer.Option(
        default=None,
        help="path of the yaml configuration file, it overrides CONFIG_PATH envvar",
        dir_okay=False,
        file_okay=True,
        exists=True,
    ),
    index_id: Optional[str] = typer.Option(
        default=None,
        help=INDEX_ID_HELP,
    ),
):
    """Synchronize scripts defined in configuration with Elasticsearch.

    This command must be run after adding, modifying or removing scripts.
    """
    from app import es_scripts
    from app.utils import connection, get_logger

    logger = get_logger()
    index_id, index_config = _get_index_config(config_path, index_id)
    connection.get_es_client()
    stats = es_scripts.sync_scripts(index_id, index_config)
    logger.info(
        f"Synced scripts (removed: {stats['removed']}, added: {stats['added']})"
    )


@cli.command()
def run_update_daemon(
    config_path: Optional[Path] = typer.Option(
        default=None,
        help="path of the yaml configuration file, it overrides CONFIG_PATH envvar",
        dir_okay=False,
        file_okay=True,
        exists=True,
    ),
):
    """Run the daemon responsible for listening to document updates from Redis
    Stream and updating the Elasticsearch index.

    This command must be run in a separate process to the api server.

    It is optional but enables having an always up-to-date index,
    for applications where data changes.
    """
    from typing import cast

    from app import config
    from app._import import run_update_daemon
    from app.config import check_config_is_defined, set_global_config, settings
    from app.utils import get_logger, init_sentry

    # Create root logger
    get_logger()
    # Initialize sentry for bug tracking
    init_sentry(settings.sentry_dns)

    if config_path:
        set_global_config(config_path)

    check_config_is_defined()
    global_config = cast(config.Config, config.CONFIG)
    run_update_daemon(global_config)


@cli.command()
def export_openapi(
    target_path: Path = typer.Argument(
        exists=None,
        file_okay=True,
        dir_okay=False,
        help="Path of the YAML or JSON data file",
    )
):
    """Export OpenAPI specification to a file."""
    import json

    import yaml

    from app.api import app as app_api

    openapi = app_api.openapi()
    version = openapi.get("openapi", "unknown version")

    print(f"writing openapi spec v{version}")
    with open(target_path, "w") as f:
        if str(target_path).endswith(".json"):
            json.dump(openapi, f, indent=2)
        else:
            yaml.dump(openapi, f, sort_keys=False)

    print(f"spec written to {target_path}")


@cli.command()
def export_config_schema(
    target_path: Path = typer.Argument(
        exists=None,
        file_okay=True,
        dir_okay=False,
        help="Path of the YAML or JSON data file",
    )
):
    """Export Configuration json schema to a file."""
    import json

    import yaml

    from app.config import Config, ConfigGenerateJsonSchema

    schema = Config.model_json_schema(schema_generator=ConfigGenerateJsonSchema)

    print("writing json schema")
    with open(target_path, "w") as f:
        if str(target_path).endswith(".json"):
            json.dump(schema, f, indent=2)
        else:
            yaml.safe_dump(schema, f, sort_keys=False)

    print(f"schema written to {target_path}")


def main() -> None:
    cli()
