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
                  "populate the database with everything use 'nxb populate "
                  "-gnpm'.")
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
@click.option("--modify", "-m", "modify_d", is_flag=True,
              help="Modify values in existing data with modify.xml.")
@click.option("--backup", "-b", "backup", is_flag=True,
              help="Back up database before populating database.")
@click.option("--backup-path", "-B", "backup_f", default=None,
              type=click.Path(), help="Back up database to a specified dump "
              "file before populating database.")
@click.pass_context
def populate(ctx, nptg_d, nptg_f, naptan_d, naptan_f, nspl_d, nspl_f, modify_d,
             backup, backup_f):
    """ Calls the populate functions for filling the static database with data.
    """
    from nextbus.populate import file_ops, modify, naptan, nptg, nspl, tsvector

    errors = False
    use_backup = False
    options = {"g": False, "n": False, "p": False, "m": False}

    if nptg_d and nptg_f:
        click.echo("Download (-g) and filepath (-G) options for NPTG data are "
                   "mutually exclusive.")
        errors = True
    else:
        options["g"] = nptg_d or nptg_f
        nptg_file = nptg_f if nptg_f else None

    if naptan_d and naptan_f:
        click.echo("Download (-n) and filepath (-N) options for NaPTAN data "
                   "are mutually exclusive.")
        errors = True
    else:
        options["n"] = naptan_d or naptan_f
        naptan_file = naptan_f if naptan_f else None

    if nspl_d and nspl_f:
        click.echo("Download (-p) and filepath (-P) options for NSPL data are "
                   "mutually exclusive.")
        errors = True
    else:
        options["p"] = nspl_d or nspl_f

    options["m"] = modify_d

    if backup and backup_f:
        click.echo("Default (-p) and filepath (-P) options for backing up "
                   "data are mutually exclusive.")
        errors = True
    elif backup or backup_f:
        use_backup = True

    if errors:
        # Messages already printed; return to shell
        return
    elif any(options.values()):
        # Carry out at least one option, back up beforehand if needed
        if use_backup:
            file_ops.backup_database(backup_f)
        try:
            if options["g"]:
                nptg.commit_nptg_data(archive=nptg_file)
            if options["n"]:
                naptan.commit_naptan_data(archive=naptan_file)
            if options["p"]:
                nspl.commit_nspl_data(file_=nspl_f)
            if options["m"]:
                modify.modify_data()
            # Update tsvector columns after population
            if options["g"] or options["m"]:
                tsvector.update_nptg_tsvector()
            if options["n"] or options["m"]:
                tsvector.update_naptan_tsvector()
        except:
            # Restore DB if errors occur and raise
            if use_backup:
                file_ops.restore_database(backup_f, error=True)
            raise
    else:
        click.echo(ctx.get_help())
