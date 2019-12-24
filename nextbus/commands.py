"""
CLI commands for the nextbus app.
"""
import os

import click
from flask import current_app
from flask.cli import FlaskGroup

from nextbus import models, populate


def run_cli_app():
    """ Runs app from CLI. """
    from nextbus import create_app

    config = os.environ.get("APP_CONFIG")
    if config:
        app = create_app(config_file=config)
    else:
        app = create_app(config_obj="default_config.DevelopmentConfig")

    return app


@click.group(cls=FlaskGroup, create_app=run_cli_app)
def cli():
    """ Commands for the nextbus package. """
    pass


class MutexOption(click.Option):
    """ Adds parameter for other options this option must be mutually exclusive
        with.

        https://stackoverflow.com/questions/37310718
    """
    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop("exclude", []))
        super().__init__(*args, **kwargs)
        if self.name in self.mutually_exclusive:
            raise ValueError(
                f"Option {self.name!r} cannot be mutually exclusive with "
                f"itself."
            )

    def handle_parse_result(self, ctx, opts, args):
        set_opts = set(opts) - {self.name}
        if self.mutually_exclusive & set_opts and self.name in opts:
            options = [o.opts for o in ctx.command.params if o.name in set_opts]
            if len(options) == 1:
                params = "/".join(options[0])
            else:
                params = (", ".join("/".join(p) for p in options[:-1]) +
                          " and " + "/".join(options[-1]))
            raise click.UsageError(
                f"{'/'.join(self.opts)} is mutually exclusive with arguments "
                f"{params}."
            )

        return super().handle_parse_result(ctx, opts, args)


@cli.command(help="Populate NaPTAN, NPTG and NSPL data. To download and "
             "populate the database with everything use "
             "'nxb populate --all'.")
@click.option("--all", "all_d", cls=MutexOption, is_flag=True,
              exclude=("nptg_d", "nptg_f", "naptan_d", "naptan_f", "nspl_d",
                       "nspl_f", "noc_d", "noc_f", "tnds_d", "tnds_f", "modify",
                       "restore", "restore_f"),
              help="Download all datasets and add to database.")
@click.option("--nptg", "-g", "nptg_d", cls=MutexOption, is_flag=True,
              exclude=("all_d", "nptg_f", "restore", "restore_f"),
              help="Download NPTG locality data and add to database.")
@click.option("--nptg-path", "-G", "nptg_f", cls=MutexOption, default=None,
              type=click.Path(dir_okay=False, exists=True),
              exclude=("all_d", "nptg_d", "restore", "restore_f"),
              help="Add NPTG locality data from specified zip file with XML "
                   "files.")
@click.option("--naptan", "-n", "naptan_d", cls=MutexOption, is_flag=True,
              exclude=("all_d", "naptan_f", "restore", "restore_f"),
              help="Download NaPTAN stop point data and add to database.")
@click.option("--naptan-path", "-N", "naptan_f", cls=MutexOption, default=None,
              type=click.Path(dir_okay=False, exists=True),
              exclude=("all_d", "naptan_d", "restore", "restore_f"),
              help="Add NaPTAN stop point data from specified zip file with "
                   "XML files.")
@click.option("--nspl", "-p", "nspl_d", cls=MutexOption, is_flag=True,
              exclude=("all_d", "nspl_f", "restore", "restore_f"),
              help="Download NSPL postcode data and add to database.")
@click.option("--nspl-path", "-P", "nspl_f", cls=MutexOption, default=None,
              type=click.Path(dir_okay=False, exists=True),
              exclude=("all_d", "nspl_d", "restore", "restore_f"),
              help="Add NSPL postcode data from specified JSON file.")
@click.option("--noc", "-o", "noc_d", cls=MutexOption, is_flag=True,
              exclude=("all_d", "noc_f", "restore", "restore_f"),
              help="Download NOC service operator data and add to database.")
@click.option("--noc-path", "-O", "noc_f", cls=MutexOption, default=None,
              type=click.Path(dir_okay=False, exists=True),
              exclude=("all_d", "noc_d", "restore", "restore_f"),
              help="Add NOC service operator data from specified XML file.")
@click.option("--tnds", "-t", "tnds_d", cls=MutexOption, is_flag=True,
              exclude=("all_d", "tnds_f", "restore", "restore_f"),
              help="Download TNDS data and add to database.")
@click.option("--tnds-dir", "-T", "tnds_f", cls=MutexOption, default=None,
              type=click.Path(file_okay=False, exists=True),
              exclude=("all_d", "tnds_d", "restore", "restore_f"),
              help="Add TNDS services data from zip files in specified "
                   "directory with the same names as NPTG region codes, eg "
                   "'L.zip'.")
@click.option("--keep-tnds", "tnds_keep", is_flag=True,
              help="Don't delete existing TNDS data (eg when adding other "
                   "regions).")
@click.option("--modify", "-m", "modify", cls=MutexOption, is_flag=True,
              exclude=("all_d",),
              help="Modify values in existing data with modify.xml.")
@click.option("--refresh", "-f", "refresh", cls=MutexOption, is_flag=True,
              exclude=("restore", "restore_f"),
              help="Refresh derived models using existing data. Active if any"
                   "population options are selected as well.")
@click.option("--backup", "-b", "backup", cls=MutexOption, is_flag=True,
              exclude=("backup_f",),
              help="Back up database before populating database.")
@click.option("--backup-path", "-B", "backup_f", cls=MutexOption, default=None,
              type=click.Path(), exclude=("backup",),
              help="Back up database to a specified dump file before "
                   "populating database.")
@click.option("--restore", "-r", "restore", cls=MutexOption, is_flag=True,
              exclude=("all_d", "nptg_d", "nptg_f", "naptan_d", "naptan_f",
                       "nspl_d", "nspl_f", "noc_d", "noc_f", "tnds_d", "tnds_f",
                       "modify", "refresh", "backup", "backup_f", "restore_f"),
              help="Restore database before populating database.")
@click.option("--restore-path", "-R", "restore_f", cls=MutexOption,
              default=None, type=click.Path(),
              exclude=("all_d", "nptg_d", "nptg_f", "naptan_d", "naptan_f",
                       "nspl_d", "nspl_f", "noc_d", "noc_f", "tnds_d", "tnds_f",
                       "modify", "refresh", "backup", "backup_f", "restore"),
              help="Restore database from a specified dump file before "
                   "populating database.")
@click.pass_context
def populate(ctx, **kw):
    """ Calls the populate functions for filling the database with data. """
    if kw["all_d"]:
        options = {o: True for o in "gnpotm"}
    else:
        options = {
            "g": kw["nptg_d"] or kw["nptg_f"] is not None,
            "n": kw["naptan_d"] or kw["naptan_f"] is not None,
            "p": kw["nspl_d"] or kw["nspl_f"] is not None,
            "o": kw["noc_d"] or kw["noc_f"] is not None,
            "t": kw["tnds_d"] or kw["tnds_f"] is not None,
            "m": kw["modify"],
            "f": kw["refresh"]
        }

    options["b"] = kw["backup"] or kw["backup_f"] is not None
    options["r"] = kw["restore"] or kw["restore_f"] is not None

    if any(options.values()):
        if options["b"]:
            populate.backup_database(path=kw["backup_f"])
        if options["r"]:
            populate.restore_database(path=kw["restore_f"])
        if options["g"]:
            populate.commit_nptg_data(archive=kw["nptg_f"])
        if options["n"]:
            populate.commit_naptan_data(archive=kw["naptan_f"])
        if options["p"]:
            populate.commit_nspl_data(path=kw["nspl_f"])
        if options["o"]:
            populate.commit_noc_data(path=kw["noc_f"])
        if options["t"]:
            # If using --all and TNDS credentials not loaded just log warning
            populate.commit_tnds_data(directory=kw["tnds_f"],
                                      delete=not kw["tnds_keep"],
                                      warn=kw["all_d"])
        if options["m"]:
            populate.modify_data()
        # Update views after population
        if any(options[o] for o in "gnmtf"):
            current_app.logger.info("Refreshing derived models")
            models.refresh_derived_models()
    else:
        click.echo(ctx.get_help())
