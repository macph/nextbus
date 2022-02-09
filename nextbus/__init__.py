"""
The nextbus package for live bus times in the UK.
"""
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from nextbus import logger


db = SQLAlchemy()
migrate = Migrate()


def create_app():
    """ App factory function for nextbus. """

    # Create app
    app = Flask(__name__)
    app.config.from_object("nextbus.config.Config")

    app.logger = logger.app_logger
    # Load logging configuration and log initial configuration
    logger.load_config(app)

    # Initialise SQLAlchemy and Migrate in app
    db.init_app(app)
    migrate.init_app(app, db)

    # Adding app, db and model objects to flask shell
    from nextbus import models
    app.shell_context_processor(
        lambda: {"app": app, "db": db, "models": models}
    )

    from nextbus.converters import add_converters
    add_converters(app)

    from nextbus.views import page
    from nextbus.resources import api
    app.register_blueprint(page)
    app.register_blueprint(api)

    return app
