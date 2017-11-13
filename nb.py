"""
Runs the nextbus app.
"""
import click
from nextbus import create_app

app = create_app()

from nextbus import models, views
from nextbus.populate import naptan, nspl


@app.cli.command(help='Populate NaPTAN, NPTG and NSPL data.')
@click.option('--naptan_files', '-n', default=None, nargs=2,
              envvar='NAPTAN_FILES', type=click.Path(exists=True),
              help=('Add NPTG and NaPTAN data from the two specified XML files'
                    ' in that order (ie, NPTG.xml then Naptan.xml).'))
@click.option('--nspl_file', '-p', envvar='NSPL_FILE', default=None,
              type=click.Path(exists=True),
              help='Add NSPL data from specified CSV file.')
def populate(naptan_files, nspl_file):
    """ Calls the populate functions for filling the static database with data.
    """
    if len(naptan_files) == 2 and nspl_file is not None:
        naptan.commit_naptan_data(naptan_file=naptan_files[1],
                                  nptg_file=naptan_files[0])
        nspl.commit_nspl_data(nspl_file=nspl_file)

    elif len(naptan_files) == 2:
        naptan.commit_naptan_data(naptan_file=naptan_files[1],
                                  nptg_file=naptan_files[0])

    elif nspl_file is not None:
        nspl.commit_nspl_data(nspl_file=nspl_file)

    else:
        click.echo('Must specify either both of the NPTG and NaPTAN files, or '
                   'the NSPL file.')
