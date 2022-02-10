#!/bin/bash

set -ex

# Run any migrations before starting up web application
/app/.venv/bin/python -m nextbus db upgrade
/app/.venv/bin/gunicorn --bind=:8000 wsgi:app
