#!/bin/bash

# Run any migrations before populating
./.venv/bin/python manage.py db upgrade
./.venv/bin/python manage.py populate --all
