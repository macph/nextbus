FROM python:3.9-slim-bullseye AS base

# Set poetry version
ENV POETRY_VERSION 1.1.10
ENV POETRY_VIRTUALENVS_IN_PROJECT 1
ENV PYTHONDONTWRITEBYTECODE 1

# Set up virtualenv for Poetry and install it
RUN python -m venv /poetry
RUN /poetry/bin/pip3 install "poetry==$POETRY_VERSION"

WORKDIR /app
COPY pyproject.toml poetry.lock ./

# Install dependencies for app and remove poetry
RUN /poetry/bin/poetry install --no-interaction --no-ansi && rm -r /poetry

# Copy over app data
COPY . .

# Set starting script as executable
RUN chmod +x ./populate.sh ./start.sh

# Expose app through port 8000
EXPOSE 8000
CMD ["./start.sh"]
