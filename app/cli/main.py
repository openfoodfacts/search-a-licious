from pathlib import Path
from typing import Optional

import typer

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
    from typing import cast

    from app import config
    from app._import import run_full_import
    from app.config import check_config_is_defined, set_global_config
    from app.utils import get_logger

    logger = get_logger()

    if config_path:
        set_global_config(config_path)

    start_time = time.perf_counter()
    check_config_is_defined()
    global_config = cast(config.Config, config.CONFIG)
    run_full_import(
        input_path,
        num_processes,
        global_config,
        num_items=num_items,
    )
    end_time = time.perf_counter()
    logger.info("Import time: %s seconds", end_time - start_time)


@app.command()
def import_taxonomies(
    config_path: Optional[Path] = typer.Option(
        default=None,
        help="path of the yaml configuration file, it overrides CONFIG_PATH envvar",
        dir_okay=False,
        file_okay=True,
        exists=True,
    ),
):
    """Import taxonomies into Elasticsearch."""
    import time
    from typing import cast

    from app import config
    from app._import import perform_taxonomy_import
    from app.config import check_config_is_defined, set_global_config
    from app.utils import get_logger

    logger = get_logger()

    if config_path:
        set_global_config(config_path)

    check_config_is_defined()
    global_config = cast(config.Config, config.CONFIG)

    start_time = time.perf_counter()
    perform_taxonomy_import(global_config)
    end_time = time.perf_counter()
    logger.info("Import time: %s seconds", end_time - start_time)


@app.command()
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
    app()
