FROM python:3.7-alpine

# Copy app data
RUN set -ex && mkdir /app
COPY . /app
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1

# Install required packages - need build lxml and psycopg2 with muslc
RUN set -ex \
    && pip3 install pipenv \
    && apk update \
    && apk add --no-cache postgresql-dev \
    && apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev \
        python3-dev \
        libxml2-dev \
        libxslt-dev \
    && pipenv install --deploy --system \
    && apk del --no-cache .build-deps \
    && pip3 uninstall --yes pipenv

# psycopg2 requires libpq.so installed in /usr/lib
ENV LD_LIBRARY_PATH /usr/lib

# Expose port 8000 to reverse proxy
EXPOSE 8000

ENV FLASK_ENV production

CMD ["gunicorn", "wsgi:app"]
