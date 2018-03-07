"""
WSGI application for use by Gunicorn
"""
import logging
import os

from definitions import CONFIG_ENV
from nextbus import create_app

application = create_app(config_file=os.environ.get(CONFIG_ENV))

if __name__ == "__main__":
    application.run()
else:
    # Delete Gunicorn logging and propagate to root
    g_access = logging.getLogger("gunicorn.access")
    g_error = logging.getLogger("gunicorn.error")
    del g_access.handlers[:], g_error.handlers[:]
    g_access.propagate = g_error.propagate = True
