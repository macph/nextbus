"""
CLI commands for the nextbus app.
"""
import os
import click
from flask.cli import FlaskGroup

# TODO: Fix issue where setting FLASK_DEBUG to 1 breaks the CLI program on Windows:
# SyntaxError: Non-UTF-8 code starting with '\x90' in file C:\Miniconda3\envs\NxB\Scripts\nb.exe on
# line 1, but no encoding declared; see http://python.org/dev/peps/pep-0263/ for details

# See github.com/pallets/werkzeug/issues/1136 - seems to be an issue with setuptools-created exes
# Windows.

def run_cli_app(info):
    """ Runs app from CLI. """
    from nextbus import create_app

    config = os.environ.get('FLASK_CONFIG')
    if config:
        app = create_app(config_file=config)
    else:
        app = create_app(config_obj="default_config:DevelopmentConfig")

    return app


@click.group(cls=FlaskGroup, create_app=run_cli_app)
def cli():
    """ Commands for the nextbus package. """
    pass


@cli.command(help='Populate NaPTAN, NPTG and NSPL data.')
@click.option('--naptan', '-n', 'naptan_dl', is_flag=True, help='Download '
              'NPTG and NaPTAN data, adding them to the database.')
@click.option('--naptan-files', '-nf', 'naptan_files', default=None,
              envvar='NAPTAN_FILES', type=click.Path(exists=True),
              help=('Add NPTG and NaPTAN data from the two specified XML files'
                    ' in that order (ie, NPTG.xml then Naptan.xml).'))
@click.option('--nspl', '-p', 'nspl_dl', is_flag=True, help='Download NSPL '
              'postcode data, adding them to the database.')
@click.option('--nspl-file', '-pf', 'nspl_file', envvar='NSPL_FILE', default=None,
              type=click.Path(exists=True),
              help='Add NSPL data from specified CSV file.')
@click.option('--modify', '-m', 'modify', is_flag=True, help='Modify values '
              'in existing data.')
@click.option('--modify-file', '-mf', 'modify_file', envvar='MODIFY_FILE',
              type=click.Path(exists=True), help='Modify values in existing '
              'data from a specified file.')
def populate(naptan_dl, naptan_files, nspl_dl, nspl_file, modify, modify_file):
    """ Calls the populate functions for filling the static database with data.
    """
    from nextbus.populate import modifications, naptan, nspl

    no_naptan, no_nspl, no_modify = False, False, False

    if naptan_dl and len(naptan_files) == 2:
        click.echo("Can't specify both downloads and files for NaPTAN data.")
    elif naptan_dl:
        naptan.commit_naptan_data()
    elif len(naptan_files) == 2:
        naptan.commit_naptan_data(nptg_file=naptan_files[0],
                                  naptan_file=naptan_files[1])
    else:
        no_naptan = True

    if nspl_dl and nspl_file is not None:
        click.echo("Can't specify both download and file for NSPL.")
    elif nspl_dl:
        nspl.commit_nspl_data()
    elif nspl_file is not None:
        nspl.commit_nspl_data(nspl_file=nspl_file)
    else:
        no_nspl = True

    if modify and modify_file is not None:
        click.echo("Can't use both default and specified file for "
                   "modification.")
    elif modify:
        modifications.modify_data()
    elif modify_file is not None:
        modifications.modify_data(modify_file)
    else:
        no_modify = True

    if no_naptan and no_nspl and no_modify:
        click.echo('Must specify either NaPTAN/NPTG data or NSPL data.')
