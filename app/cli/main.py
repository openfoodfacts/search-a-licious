from pathlib import Path
from typing import Optional

import typer

import app

cli = typer.Typer()


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
        help="Each index has its own configuration in the configuration file, "
        "and the ID is used to know which index to use. "
        "If there is only one index, this option is not needed.",
    ),
):
    """Import data into Elasticsearch."""
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
        help="Each index has its own configuration in the configuration file, "
        "and the ID is used to know which index to use. "
        "If there is only one index, this option is not needed.",
    ),
):
    """Import taxonomies into Elasticsearch."""
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
        help="Each index has its own configuration in the configuration file, "
        "and the ID is used to know which index to use. "
        "If there is only one index, this option is not needed.",
    ),
):
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
    Stream and updating the Elasticsearch index."""
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


def main() -> None:
    cli()
