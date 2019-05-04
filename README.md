# nextbus

Live service times in the UK.

This is a Flask + SQLAlchemy web application running on a PostgreSQL DB.

## Installation

The easiest way to do this is to use `pipenv`. Clone the repo:

```
git clone https://github.com/macph/nextbus.git
```

Enter the new folder and run

```
pipenv install
```

to setup the virtual environment, install all related package and the application itself. The virtual environment can be started up with `pipenv shell` or a command run with `pipenv run`. The `nxb` command is available for accessing the application.

## Starting up

PostgreSQL must be at least v11 to support particular full text search functionality.

Default config values can be found within `default_config.py` in the root directory. If new values are needed, like a different URI for the DB, a separate config file is required. Create a new Python config file in the `instance` folder:

```
echo 'SQLALCHEMY_DATABASE_URI = "postgresql://scott:tiger@localhost"' > instance/new_config.py
```

and set enviroment variable `APP_CONFIG` to `new_config.py` so the application will load config on start up. With the configuration set up, run the database migrations:

```
nxb db upgrade
```

Populate with data:

```
nxb populate --all
```

which will download NPTG, NaPTAN and NSPL data and commits them, as well as doing some modifications. If you've added TNDS FTP credentials to the config, TNDS service data will be added as well. Run the server in development mode with

```
nxb run
```

## App keys

Live bus times are retrieved with [Transport API](transportapi.com) - a account is required to use application ID/key. Sample data is used as backup for testing if no key exists.
