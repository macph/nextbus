"""
The nextbus package for live bus times in the UK.
"""
import os
import click
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from definitions import ROOT_DIR


app = Flask(__name__)
app.config.update(
    SQLALCHEMY_DATABASE_URI=('sqlite:///'
                             + os.path.join(ROOT_DIR, 'nextbus.db')),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    WTF_CSRF_ENABLED=True,
    SECRET_KEY="sup3r sekr3t k3y",
    DEBUG=True
)
app.config.from_envvar('APP_SETTINGS', silent=True)

db = SQLAlchemy(app)
migrate = Migrate(app, db)


from nextbus import views, models
from nextbus.populate import commit_naptan_data, commit_nspl_data


@app.cli.command(help='Populate NaPTAN, NPTG and NSPL data.')
@click.option('--atco', '-a', default=None, type=int, multiple=True,
              help='Restricts data to a specific admin area, eg 370.')
@click.option('--naptan_files', '-n', default=None, nargs=2,
              envvar='NAPTAN_FILES', type=click.Path(exists=True),
              help=('Add NPTG and NaPTAN from the two specified XML files in '
                    'that order.'))
@click.option('--nspl_file', '-p', envvar='NSPL_FILE', default=None,
              type=click.Path(exists=True),
              help='Add NSPL data from specified CSV file.')
def populate(atco, naptan_files, nspl_file):
    """ Calls the populate functions for filling the static database with data.
    """
    if (len(naptan_files) == 2 and nspl_file is not None):
        commit_naptan_data(atco, naptan_file=naptan_files[1],
                           nptg_file=naptan_files[0])
        commit_nspl_data(atco, nspl_file=nspl_file)

    elif len(naptan_files) == 2:
        commit_naptan_data(atco, naptan_file=naptan_files[1],
                           nptg_file=naptan_files[0])

    elif nspl_file is not None:
        commit_nspl_data(atco, nspl_file=nspl_file)

    else:
        click.echo('Must specify either both of the NPTG and NaPTAN files, or '
                   'the NSPL file.')
