# nextbus

Live service times in the UK.

This is a Flask + SQLAlchemy web application running on a PostgreSQL DB.

## Installation

Clone the repo:

```bash
git clone https://github.com/macph/nextbus.git
```

The server can be set up using Docker or installed locally with pipenv. If you're using Docker Compose, `docker_compose.yml` assumes you've added `nxb_config.py` and `gu_config.py` to the `instance` folder ignored by git.

```bash
mkdir instance

echo 'SQLALCHEMY_DATABASE_URI = "postgresql://prod:hello_world@postgres:5432/nextbus"
SECRET_KEY = b"your secret key"' > instance/nxb_config.py

echo 'bind = ["0.0.0.0:8000"]' > instance/gu_config.py
```

See `default_config.py` for all options.

Use `docker-compose up` or `pipenv install` to set up the application.

## Starting up

PostgreSQL must be at least version 11 to support particular full text search functionality.

With the configuration set up, use `docker exec` or `pipenv run` to access the application. Run the database migrations:

```bash
nxb db upgrade
```

Populate with data:

```bash
nxb populate --all
```

which will download NPTG, NaPTAN and NSPL data and commits them, as well as doing some modifications. If you've added TNDS FTP credentials to the config, TNDS service data will be added as well. Run the server locally in development mode with

```bash
nxb run
```

or run the Docker container.

## App keys

Live bus times are retrieved with [Transport API](transportapi.com) - a account is required to use application ID/key. Sample data is used as backup for testing if no key exists.
