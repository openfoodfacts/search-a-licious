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
):
    """Import data into Elasticsearch."""
    import time

    from app.cli.perform_import import perform_import
    from app.config import CONFIG
    from app.utils import get_logger

    logger = get_logger()

    start_time = time.perf_counter()
    perform_import(
        input_path,
        num_items,
        num_processes,
        start_time,
        CONFIG,
    )
    end_time = time.perf_counter()
    logger.info("Import time: %s seconds", end_time - start_time)


@app.command()
def write_to_redis():
    import time

    from redis import Redis

    redis = Redis(
        host="redis",
        port=6379,
        decode_responses=True,
    )
    key_name = "search_import_queue"
    while True:
        code = input("Please enter a product code:\n")
        start_time = time.perf_counter()

        redis.rpush(key_name, code)
        end_time = time.perf_counter()
        print(f"Time: {end_time - start_time} seconds")


def main() -> None:
    app()
