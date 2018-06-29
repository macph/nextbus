# nextbus

Live bus times in the UK.

This is a Flask web application running on a PostgreSQL DB via SQLAlchemy.

## Installation

The easiest way to do this is to use `pipenv`. Clone the repo:

```
git clone https://github.com/macph/nextbus.git
```

Enter the new folder and run

```
pipenv install
```

to setup the virtual environment and install the application and all related packages.

Within the virtual enviroment the `nxb` command is available for accessing the application.

## Starting up

Default config values can be found within `default_config.py` in the root directory. If new values are needed, like a different URI for the DB, a separate config file is required. Create a new Python config file in the `instance` folder:

```
touch instance/config.py
```

and set enviroment variable `APP_CONFIG` to `config.py`.

PostgreSQL > 9.6 is required.

By default all areas within Great Britain are loaded, but if you want to restrict the data to a specific area the `ATCO_CODES` parameter needs to be set as a list of codes. See [NaPTAN info](http://naptan.app.dft.gov.uk/datarequest/help) for more on ATCO codes. For example, London has a ATCO code `490`, so in the config file it can be set as

```python
ATCO_CODES = [490]
```

With the configuration set up, upgrade the database migrations:

```python
nxb db upgrade
```

Populate with data:

```
nxb populate -gnpm
```

which will download NPTG, NaPTAN and NSPL data and commits them, as well as doing some modifications.

Run the development server with

```
nxb run
```

## App keys

Live bus times are retrieved with [Transport API](transportapi.com) - a account is required to use application ID/key. Sample data is used as backup for testing if no key exists.

[Mapbox](mapbox.com) is used for map data, which requires an application token.