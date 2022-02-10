#!/bin/bash

set -ex

# Run any migrations before populating
.venv/bin/python -m nextbus db upgrade
.venv/bin/python -m nextbus populate --all
