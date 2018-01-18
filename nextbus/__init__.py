"""
The nextbus package for live bus times in the UK.
"""
import os.path
import click
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

import default_config
from definitions import ROOT_DIR


db = SQLAlchemy(session_options={'autocommit': True})
migrate = Migrate()


def create_app(config_obj=None, config_file=None):
    """ App factory function for nextbus. """
    app = Flask(__name__)
    if config_obj is None and config_file is None:
        click.echo(" * Loading default configuration")
        app.config.from_object(default_config.DevelopmentConfig)
    elif config_obj is not None:
        click.echo(" * Loading configuration from object %r" % config_obj)
        app.config.from_object(config_obj)
    elif config_file is not None:
        # Load app defaults first
        app.config.from_object(default_config.Config)
        if os.path.isabs(config_file):
            file_path = config_file
        else:
            file_path = os.path.join(ROOT_DIR, config_file)
        click.echo(" * Loading configuration from file '%s'" % file_path)
        app.config.from_pyfile(file_path)
    else:
        raise ValueError("Can't have both config object and config file")

    db.init_app(app)
    migrate.init_app(app, db)
    # Adding app, db and model objects to flask shell
    from nextbus import models
    app.shell_context_processor(
        lambda: {'app': app, 'db': db, 'models': models}
    )

    from nextbus.views import api, page_search, page_no_search
    app.register_blueprint(api)
    app.register_blueprint(page_search)
    app.register_blueprint(page_no_search)

    return app
