# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
#
import logging
from pathlib import Path
import sys

import click
from c7n.config import Config

from .entry import initialize_iac
from .output import get_reporter, report_outputs
from .core import CollectionRunner


log = logging.getLogger("c7n.iac")


@click.group()
def cli():
    """Shift Left Policy"""
    logging.basicConfig(level=logging.DEBUG)
    initialize_iac()


@cli.command()
@click.option("--format", default="terraform")
@click.option("-p", "--policy-dir", type=click.Path())
@click.option("-d", "--directory", type=click.Path())
@click.option("-o", "--output", default="cli", type=click.Choice(report_outputs.keys()))
@click.option("--output-file", type=click.File("w"), default="-")
@click.option("--output-query", default=None)
def run(format, policy_dir, directory, output, output_file, output_query):
    """evaluate policies against IaC sources.

    WARNING - CLI interface subject to change.
    """
    config = Config.empty(
        source_dir=Path(directory),
        policy_dir=Path(policy_dir),
        output=output,
        output_file=output_file,
        output_query=output_query,
        provider=format,
    )
    reporter = get_reporter(config)
    runner = CollectionRunner(policy_dir, config, reporter)
    sys.exit(int(runner.run()))


if __name__ == "__main__":  # pragma: no cover
    try:
        cli()
    except Exception:
        import pdb, traceback

        traceback.print_exc()
        pdb.post_mortem(sys.exc_info()[-1])
