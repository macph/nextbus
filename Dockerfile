FROM python:3.7-alpine

ENV PYTHONDONTWRITEBYTECODE 1

RUN pip3 install pipenv
# Need shared libraries for python C extensions
RUN set -ex \
    && apk update \
    && apk add --no-cache \
        postgresql-dev \
        libxml2-dev \
        libxslt-dev
# Required libraries installed in /usr/lib
ENV LD_LIBRARY_PATH /usr/lib

# Copy over app data
RUN mkdir /app
COPY . /app

# Install required packages - need to build lxml and psycopg2 with muslc
WORKDIR /app
RUN set -ex \
    && apk update \
    && apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev \
        python3-dev \
    && pipenv install --deploy --system \
    && apk del --no-cache .build-deps
RUN pip3 uninstall --yes pipenv

# Expose port 8000 to reverse proxy
EXPOSE 8000

ENV FLASK_ENV production

CMD ["gunicorn", "wsgi:app"]
