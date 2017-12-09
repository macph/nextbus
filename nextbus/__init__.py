"""
The nextbus package for live bus times in the UK.
"""
import os
import click
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

import default_config
from definitions import ROOT_DIR


db = SQLAlchemy()
migrate = Migrate()


def create_app(config_obj=None, config_file=None):
    """ App factory function for nextbus. """
    app = Flask(__name__)
    if config_obj is None and config_file is None:
        app.config.from_object(default_config.DevelopmentConfig)
    elif config_obj is not None and config_file is not None:
        raise ValueError("Can't have both config object and config file!")
    elif config_file is not None:
        app.config.from_pyfile(config_file)
    else:
        app.config.from_object(config_obj)

    db.init_app(app)
    migrate.init_app(app, db)
    # Adding db and app objects to flask shell
    from nextbus import models
    app.shell_context_processor(
        lambda: {'app': app, 'db': db, 'models': models}
    )

    from nextbus.views import page
    app.register_blueprint(page)

    return app
