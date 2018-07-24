"""
WSGI application for use by Gunicorn.
"""
import logging
import os

from definitions import CONFIG_ENV
from nextbus import create_app

app = create_app(config_file=os.environ.get(CONFIG_ENV))

if __name__ == "__main__":
    app.run()
else:
    # Set app to use gunicorn logging
    g_error = logging.getLogger("gunicorn.error")
    app.logger.handlers = g_error.handlers
    app.logger.setLevel(g_error.level)
