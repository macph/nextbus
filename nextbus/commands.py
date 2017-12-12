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


@cli.command(help='Populate NaPTAN, NPTG and NSPL data.')
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

    options = {'nptg': True, 'naptan': True, 'nspl': True, 'modify': True}

    if nptg_d and nptg_f:
        click.echo("Can't specify both download and filepath for NPTG data.")
    elif nptg_d or nptg_f:
        naptan.commit_nptg_data(nptg_file=nptg_f)
    else:
        options['nptg'] = False

    if naptan_d and naptan_f:
        click.echo("Can't specify both download and filepath for NaPTAN data.")
    elif naptan_d or naptan_f:
        naptan.commit_naptan_data(naptan_file=naptan_f)
    else:
        options['naptan'] = False

    if nspl_d and nspl_f:
        click.echo("Can't specify both download and filepath for NSPL data.")
    elif nspl_d or nspl_f:
        nspl.commit_nspl_data(nspl_file=nspl_f)
    else:
        options['nspl'] = False

    if modify:
        modifications.modify_data()
    else:
        options['modify'] = False

    if not any(i for i in options.values()):
        click.echo('No option selected.')
