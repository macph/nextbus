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


db = SQLAlchemy()
migrate = Migrate()


def create_app(config_obj=None, config_file=None):
    """ App factory function for nextbus.

        :param config_obj: A class with configuration parameters as variables,
        or a string pointing to a class within a file.
        :param config_file: Python file file with configuration parameters.
        :returns: The nextbus Flask application.
        :raises ValueError: Raised if either both or none of the two arguments
        are specified.
    """
    app = Flask(__name__)
    if not bool(config_obj) ^ bool(config_file):
        raise ValueError("A configuration object or file must be specified.")
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

    db.init_app(app)
    migrate.init_app(app, db)
    # Adding app, db and model objects to flask shell
    from nextbus import models
    app.shell_context_processor(lambda: {"app": app, "db": db,
                                         "models": models})

    from nextbus.views import api, page_search, page_no_search
    app.register_blueprint(api)
    app.register_blueprint(page_search)
    app.register_blueprint(page_no_search)

    return app
