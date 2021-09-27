FROM python:3.9-slim-bullseye AS base

# Set poetry version
ENV POETRY_VERSION 1.1.10
ENV POETRY_VIRTUALENVS_IN_PROJECT 1
ENV PYTHONDONTWRITEBYTECODE 1

# Set up virtualenv for Poetry and install it
RUN python -m venv /poetry
RUN /poetry/bin/pip3 install "poetry==$POETRY_VERSION"

WORKDIR /app
COPY pyproject.toml poetry.lock /app/

# Install dependencies for app
RUN /poetry/bin/poetry install --no-dev --no-interaction --no-ansi

# Remove Poetry venv
RUN rm -r /poetry

# Copy over app data and reinstall
COPY . .

# Expose port 8000 to reverse proxy
EXPOSE 8000

ENV FLASK_ENV production

CMD ["/app/.venv/bin/gunicorn", "wsgi:app"]
