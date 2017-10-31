"""
The nextbus package for live bus times in the UK.
"""
import os
import click
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from definitions import ROOT_DIR


db = SQLAlchemy()
migrate = Migrate()

def create_app(obj_config=None):
    """ App factory function for nextbus. """
    app = Flask(__name__)
    if obj_config is None:
        app.config.update(
            DEBUG=True,
            SQLALCHEMY_DATABASE_URI=('sqlite:///'
                                     + os.path.join(ROOT_DIR, 'nextbus.db')),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            WTF_CSRF_ENABLED=True,
            SECRET_KEY="sup3r sekr3t k3y"
        )
        app.config.from_envvar('FLASK_CONFIG', silent=True)
    else:
        app.config.from_object(obj_config)

    db.init_app(app)
    migrate.init_app(app, db)

    from nextbus.views import page
    app.register_blueprint(page)

    return app
