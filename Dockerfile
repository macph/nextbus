FROM python:3.8-slim-buster AS base

# Set poetry version
ENV POETRY_VERSION 1.0.9
ENV POETRY_VIRTUALENVS_IN_PROJECT 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install Poetry
RUN pip3 install "poetry==$POETRY_VERSION"

WORKDIR /app
COPY pyproject.toml poetry.lock /app/

# Install dependencies for app
RUN poetry install --no-dev --no-interaction --no-ansi
RUN pip3 uninstall --yes poetry

# Copy over app data and reinstall
COPY . .

# Expose port 8000 to reverse proxy
EXPOSE 8000

ENV FLASK_ENV production

CMD ["/app/.venv/bin/gunicorn", "wsgi:app"]
