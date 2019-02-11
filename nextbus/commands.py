"""
CLI commands for the nextbus app.
"""
import os

import click
from flask.cli import FlaskGroup

from definitions import CONFIG_ENV


def run_cli_app():
    """ Runs app from CLI. """
    from nextbus import create_app

    config = os.environ.get(CONFIG_ENV)
    if config:
        app = create_app(config_file=config)
    else:
        app = create_app(config_obj="default_config.DevelopmentConfig")

    return app


@click.group(cls=FlaskGroup, create_app=run_cli_app)
def cli():
    """ Commands for the nextbus package. """
    pass


@cli.command(help="Populate NaPTAN, NPTG and NSPL data. To download and "
             "populate the database with everything use "
             "'nxb populate -gnpotm'.")
@click.option("--nptg", "-g", "nptg_d", is_flag=True,
              help="Download NPTG locality data and add to database.")
@click.option("--nptg-path", "-G", "nptg_f", default=None,
              type=click.Path(exists=True),
              help="Add NPTG locality data from specified zip file with XML "
              "files.")
@click.option("--naptan", "-n", "naptan_d", is_flag=True,
              help="Download NaPTAN stop point data and add to database.")
@click.option("--naptan-path", "-N", "naptan_f", default=None,
              type=click.Path(exists=True),
              help="Add NaPTAN stop point data from specified zip file with "
              "XML files.")
@click.option("--nspl", "-p", "nspl_d", is_flag=True,
              help="Download NSPL postcode data and add to database.")
@click.option("--nspl-path", "-P", "nspl_f", default=None,
              type=click.Path(exists=True),
              help="Add NSPL postcode data from specified JSON file.")
@click.option("--noc", "-o", "noc_d", is_flag=True,
              help="Download NOC service operator data and add to database.")
@click.option("--noc-path", "-O", "noc_f", default=None,
              type=click.Path(exists=True),
              help="Add NOC service operator data from specified XML file.")
@click.option("--tnds", "-t", "tnds_d", is_flag=True,
              help="Download TNDS data and add to database.")
@click.option("--tnds-path", "-T", "tnds_f", default=(), nargs=2,
              type=click.Tuple([click.Path(exists=True), str]), multiple=True,
              help="Add TNDS services data from specified zip file with XML "
              "files and a region code.")
@click.option("--keep-tnds", "tnds_keep", is_flag=True,
              help="Don't delete existing TNDS data (eg when adding other "
              "regions).")
@click.option("--modify", "-m", "modify_d", is_flag=True,
              help="Modify values in existing data with modify.xml.")
@click.option("--backup", "-b", "backup", is_flag=True,
              help="Back up database before populating database.")
@click.option("--backup-path", "-B", "backup_f", default=None,
              type=click.Path(), help="Back up database to a specified dump "
              "file before populating database.")
@click.option("--restore", "-r", "restore", is_flag=True,
              help="Restore database before populating database.")
@click.option("--restore-path", "-R", "restore_f", default=None,
              type=click.Path(), help="Restore database from a specified dump "
              "file before populating database.")
@click.pass_context
def populate(ctx, **kw):
    """ Calls the populate functions for filling the database with data. """
    from flask import current_app
    from nextbus import models, populate
    from nextbus.populate import file_ops, utils

    errors = False
    options = {o: False for o in "brgnpotm"}

    if kw["nptg_d"] and kw["nptg_f"]:
        click.echo("Download (-g) and filepath (-G) options for NPTG data are "
                   "mutually exclusive.")
        errors = True
    else:
        options["g"] = kw["nptg_d"] or kw["nptg_f"]

    if kw["naptan_d"] and kw["naptan_f"]:
        click.echo("Download (-n) and filepath (-N) options for NaPTAN data "
                   "are mutually exclusive.")
        errors = True
    else:
        options["n"] = kw["naptan_d"] or kw["naptan_f"]

    if kw["nspl_d"] and kw["nspl_f"]:
        click.echo("Download (-p) and filepath (-P) options for NSPL data are "
                   "mutually exclusive.")
        errors = True
    else:
        options["p"] = kw["nspl_d"] or kw["nspl_f"]

    if kw["noc_d"] and kw["noc_f"]:
        click.echo("Download (-o) and filepath (-O) options for NOC data are "
                   "mutually exclusive.")
        errors = True
    else:
        options["o"] = kw["noc_d"] or kw["noc_f"]

    if kw["tnds_d"] and kw["tnds_f"] and kw["tnds_f"][0][0]:
        click.echo("Download (-t) and filepath (-T) options for TNDS data are "
                   "mutually exclusive.")
        errors = True
    else:
        options["t"] = kw["tnds_d"] or kw["tnds_f"]

    options["m"] = kw["modify_d"]

    backup = kw["backup"] or kw["backup_f"]
    restore = kw["restore"] or kw["restore_f"]

    if backup and restore:
        click.echo("Can't backup and restore database at the same time!")
        errors = True

    if kw["backup"] and kw["backup_f"]:
        click.echo("Default (-b) and filepath (-B) options for backing up "
                   "data are mutually exclusive.")
        errors = True
    else:
        options["b"] = backup

    if kw["restore"] and kw["restore_f"]:
        click.echo("Default (-r) and filepath (-R) options for restoring "
                   "data are mutually exclusive.")
        errors = True
    else:
        options["r"] = restore

    if errors:
        # Messages already printed; return to shell
        return
    elif any(options.values()):
        if options["b"]:
            # Carry out at least one option, back up beforehand if needed
            file_ops.backup_database(kw["backup_f"])
        if options["r"]:
            # Carry out at least one option, back up beforehand if needed
            file_ops.restore_database(kw["restore_f"])
        if options["g"]:
            populate.commit_nptg_data(archive=kw["nptg_f"])
        if options["n"]:
            populate.commit_naptan_data(archive=kw["naptan_f"])
        if options["p"]:
            populate.commit_nspl_data(file_=kw["nspl_f"])
        if options["o"]:
            populate.commit_noc_data(kw["noc_f"])
        if options["t"]:
            if kw["tnds_f"]:
                tnds_files = {t[1]: t[0] for t in kw["tnds_f"]}
            else:
                tnds_files = None
            populate.commit_tnds_data(archives=tnds_files,
                                      delete=not kw["tnds_keep"])
        if options["m"]:
            populate.modify_data()
        # Update views after population
        if options["g"] or options["n"] or options["m"] or options["t"]:
            with utils.database_session():
                current_app.logger.info("Refreshing materialized views")
                models.FTS.refresh(concurrently=False)
                models.NaturalSort.refresh(concurrently=False)
    else:
        click.echo(ctx.get_help())
