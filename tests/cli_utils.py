import sys
import traceback

from typer.testing import CliRunner

from app.cli.main import cli

runner = CliRunner(mix_stderr=False)


def add_cli_exc_info(result):
    """Print exception info if there was an error during a CliRunner test

    This is useful to quickly grab the problem
    """
    if result.exit_code != 0:
        print("".join(traceback.format_exception(*result.exc_info)), file=sys.stderr)


def runner_invoke(*args):
    """Run a CLI command and print exception info if there was an error"""
    result = runner.invoke(cli, args)
    add_cli_exc_info(result)
    return result
