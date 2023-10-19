from pathlib import Path
from typing import Optional

import typer

from app.cli.perform_import import perform_taxonomies_import
from app.config import check_config_is_defined, set_global_config

app = typer.Typer()


@app.command(name="import")
def import_data(
    input_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Path of the JSONL data file",
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
):
    """Import data into Elasticsearch."""
    import time

    from app import config
    from app.cli.perform_import import perform_import
    from app.config import set_global_config
    from app.utils import get_logger

    logger = get_logger()

    if config_path:
        set_global_config(config_path)

    start_time = time.perf_counter()
    check_config_is_defined()
    perform_import(
        input_path,
        num_items,
        num_processes,
        start_time,
        config.CONFIG,
    )
    end_time = time.perf_counter()
    logger.info("Import time: %s seconds", end_time - start_time)


@app.command(name="import-taxonomies")
def import_taxonomies():
    """Import taxonomies into Elasticsearch."""
    import time
    from app.utils import get_logger
    from app import config
    logger = get_logger()
    start_time = time.perf_counter()
    perform_taxonomies_import(
        start_time,
        config.TAXONOMY_CONFIG,
    )
    end_time = time.perf_counter()
    logger.info("Import time: %s seconds", end_time - start_time)


@app.command()
def write_to_redis(doc_id: str):
    import time

    from app.config import settings
    from app.utils import get_logger
    from app.utils.connection import get_redis_client

    logger = get_logger()
    redis = get_redis_client()
    start_time = time.perf_counter()
    redis.rpush(settings.redis_import_queue, doc_id)
    end_time = time.perf_counter()
    logger.info("Time: %s seconds", end_time - start_time)


@app.command()
def import_from_queue(
    config_path: Optional[Path] = typer.Option(
        default=None,
        help="path of the yaml configuration file, it overrides CONFIG_PATH envvar",
        dir_okay=False,
        file_okay=True,
        exists=True,
    ),
):
    from app import config
    from app.config import check_config_is_defined, settings
    from app.queue import run_queue_safe
    from app.utils import connection, get_logger, init_sentry

    # Create root logger
    get_logger()
    # Initialize sentry for bug tracking
    init_sentry(settings.sentry_dns)

    if config_path:
        set_global_config(config_path)

    # create elasticsearch connection
    connection.get_es_client()

    check_config_is_defined()

    # run queue
    run_queue_safe(config.CONFIG)


def main() -> None:
    app()
