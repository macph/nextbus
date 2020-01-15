FROM python:3.8-alpine as base

# Need shared libraries for python C extensions
RUN set -ex \
    && apk update \
    && apk add --no-cache \
        postgresql-dev \
        libxml2-dev \
        libxslt-dev

# Required libraries installed in /usr/lib
ENV LD_LIBRARY_PATH /usr/lib
# Set poetry version
ENV POETRY_VERSION 1.0.0
ENV PYTHONDONTWRITEBYTECODE 1

# Install Poetry - cffi is a dependency and needs to be built using libffi
RUN set -ex \
    && apk update \
    && apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev \
        python3-dev \
        libffi-dev \
    && pip3 install "poetry==$POETRY_VERSION" \
    && apk del --no-cache .build-deps

WORKDIR /app
COPY pyproject.toml poetry.lock /app/

# Install dependencies for app - lxml and psycopg2 needs to be built
RUN set -ex \
    && apk update \
    && apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev \
        python3-dev \
    && poetry config virtualenvs.in-project true \
    && poetry install --no-dev --no-interaction --no-ansi \
    && apk del --no-cache .build-deps

RUN pip3 uninstall --yes poetry

# Copy over app data
COPY . .

# Expose port 8000 to reverse proxy
EXPOSE 8000

ENV FLASK_ENV production

CMD ["/app/.venv/bin/gunicorn", "wsgi:app"]
