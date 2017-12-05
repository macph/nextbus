"""
Runs the nextbus app.
"""
import click
from nextbus import create_app

app = create_app()

from nextbus import models, views
from nextbus.populate import modifications, naptan, nspl


@app.cli.command(help='Populate NaPTAN, NPTG and NSPL data.')
@click.option('--naptan', '-n', 'naptan_dl', is_flag=True, help='Download '
              'NPTG and NaPTAN data, adding them to the database.')
@click.option('--naptan-files', '-nf', 'naptan_files', default=None, nargs=2,
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
    no_naptan, no_nspl, no_modify = False, False, False

    if naptan_dl and len(naptan_files) == 2:
        click.echo("Can't specify both downloads and files for NaPTAN data.")
    elif naptan_dl:
        naptan.commit_naptan_data()
    elif len(naptan_files) == 2:
        naptan.commit_naptan_data(naptan_file=naptan_files[1],
                                  nptg_file=naptan_files[0])
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
