#!/bin/bash

# Run any migrations before starting up web application
./.venv/bin/python manage.py db upgrade

./.venv/bin/gunicorn --bind=:8000 wsgi:app
