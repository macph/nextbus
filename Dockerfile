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
ENV POETRY_VERSION 0.12.17
ENV PYTHONDONTWRITEBYTECODE 1

RUN pip3 install "poetry==$POETRY_VERSION"

WORKDIR /app
COPY pyproject.toml poetry.lock /app/

# Install required packages - need to build lxml and psycopg2 with muslc
RUN set -ex \
    && apk update \
    && apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev \
        python3-dev \
    && poetry config settings.virtualenvs.in-project true \
    && poetry install --no-dev --no-interaction --no-ansi \
    && apk del --no-cache .build-deps

RUN pip3 uninstall --yes poetry

# Copy over app data
COPY . .

# Expose port 8000 to reverse proxy
EXPOSE 8000

ENV FLASK_ENV production

CMD ["/app/.venv/bin/gunicorn", "wsgi:app"]
