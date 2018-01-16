"""
CLI commands for the nextbus app.
"""
import os
import click
from flask.cli import FlaskGroup


def run_cli_app(info):
    """ Runs app from CLI. """
    from nextbus import create_app

    config = os.environ.get('FLASK_CONFIG')
    if config:
        app = create_app(config_file=config)
    else:
        app = create_app()

    return app


@click.group(cls=FlaskGroup, create_app=run_cli_app)
def cli():
    """ Commands for the nextbus package. """
    pass


@cli.command(help="Populate NaPTAN, NPTG and NSPL data. To download and "
                  "populate the database with everything use 'nxb populate "
                  "-gnpm'.")
@click.option('--nptg', '-g', 'nptg_d', is_flag=True,
              help="Download NPTG locality data and add to database.")
@click.option('--nptg-path', '-G', 'nptg_f', default=None,
              type=click.Path(exists=True),
              help="Add NPTG locality data from specified XML file.")
@click.option('--naptan', '-n', 'naptan_d', is_flag=True,
              help="Download NaPTAN stop point data and add to database.")
@click.option('--naptan-path', '-N', 'naptan_f', default=None,
              type=click.Path(exists=True),
              help="Add NaPTAN stop point data from specified XML file.")
@click.option('--nspl', '-p', 'nspl_d', is_flag=True,
              help="Download NSPL postcode data and add to database.")
@click.option('--nspl-path', '-P', 'nspl_f', default=None,
              type=click.Path(exists=True),
              help="Add NSPL postcode data from specified JSON file.")
@click.option('--modify', '-m', 'modify', is_flag=True,
              help="Modify values in existing data with modifications.json.")
def populate(nptg_d, nptg_f, naptan_d, naptan_f, nspl_d, nspl_f, modify):
    """ Calls the populate functions for filling the static database with data.
    """
    from nextbus.populate import modifications, naptan, nspl

    errors = False
    options = {'g': False, 'n': False, 'p': False, 'm': False}

    if nptg_d and nptg_f:
        click.echo("Can't specify both download option (-g) and filepath (-G) "
                   "for NPTG data.")
        errors = True
    else:
        options['g'] = nptg_d or nptg_f

    if naptan_d and naptan_f:
        click.echo("Can't specify both download option (-n) and filepath (-N) "
                   "for NaPTAN data.")
        errors = True
    else:
        options['n'] = naptan_d or naptan_f

    if nspl_d and nspl_f:
        click.echo("Can't specify both download option (-p) and filepath (-P) "
                   "for NSPL data.")
        errors = True
    else:
        options['p'] = nspl_d or nspl_f
    options['m'] = modify

    if errors:
        return
    if options['g']:
        naptan.commit_nptg_data(nptg_file=nptg_f)
    if options['n']:
        naptan.commit_naptan_data(naptan_file=naptan_f)
    if options['p']:
        nspl.commit_nspl_data(nspl_file=nspl_f)
    if options['m']:
        modifications.modify_data()

    if not any(i for i in options.values()):
        click.echo('No option selected.')
