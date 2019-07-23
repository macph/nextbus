"""
The nextbus package for live bus times in the UK.
"""
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


from nextbus import logger


db = SQLAlchemy()
migrate = Migrate()


def create_app(config_obj=None, config_file=None):
    """ App factory function for nextbus.

        :param config_obj: A class with configuration parameters as variables,
        or a string pointing to a class within a file.
        :param config_file: Python file file with configuration parameters,
        which is expected to be within an instance folder.
        :returns: The nextbus Flask application.
        :raises ValueError: Raised if either both or none of the two arguments
        are specified.
    """
    # Create app
    app = Flask(__name__, instance_relative_config=True, static_url_path="/")
    app.logger = logger.app_logger
    # Load logging configuration
    logger.load_config(app)

    # Load application configuration
    if not bool(config_obj) ^ bool(config_file):
        raise ValueError("A configuration object or file must be specified.")
    elif config_obj is not None:
        app.config.from_object(config_obj)
        app.logger.info("Configuration loaded from object '%s'" % config_obj)
    else:
        # Load app defaults first
        app.config.from_object("default_config.Config")
        app.config.from_pyfile(config_file)
        app.logger.info("Configuration loaded from file '%s'" % config_file)

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
