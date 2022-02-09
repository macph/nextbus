"""
File operations for opening datasets.
"""
import os
import re
import subprocess
import zipfile
import urllib.parse

import requests
import sqlalchemy as sa
from flask import current_app

from nextbus.populate import utils


def _file_name(response):
    """ Gets the file name from the response header or the URL name. """
    content = response.headers.get("content-disposition")
    if content and "filename" in content:
        file_name = re.search(r"filename=(.+)", content).group(1)
    else:
        # Get the path and split it to get the rightmost part
        path = urllib.parse.urlparse(response.url)[2]
        file_name = path.split("/")[-1]

    return file_name


def download(url, file_name=None, directory=None, **kw):
    """ Downloads files with requests.

        :param url: URL to download from.
        :param file_name: Name of file to be saved. Use 'directory' to specify
        a path. If None, the name is derived from the URL or the header.
        :param directory: Path for directory. If directory is None, the root
        directory is used instead.
        :param kw: Keyword arguments for requests.get().
    """
    response = requests.get(url, stream=True, **kw)
    name = _file_name(response) if file_name is None else file_name
    full_path = os.path.join(directory, name)

    utils.logger.info(f"Downloading {name!r} from {url!r}")
    with open(full_path, 'wb') as out:
        for chunk in response.iter_content(chunk_size=1024):
            out.write(chunk)

    return full_path


def iter_archive(archive):
    """ Generator function iterating over all files in a zipped archive file.

        The generator will open each file, yielding its file-like object. This
        file will be closed before opening the next file. When the iteration
        is finished the archive is closed.

        :param archive: Path to the archive file.
        :returns: File-like object for current archived file.
    """
    zip_ = zipfile.ZipFile(archive)
    for name in zip_.namelist():
        with zip_.open(name) as current:
            yield current
    zip_.close()


def _database_url():
    config_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    if config_uri is not None:
        return sa.engine.url.make_url(config_uri)
    else:
        raise ValueError("The SQLALCHEMY_DATABASE_URI option is not defined.")


def _database_path():
    config_path = current_app.config.get("DATABASE_DUMP_PATH")
    if config_path is not None:
        return config_path
    else:
        raise ValueError("The DATABASE_DUMP_PATH option is not defined.")


def backup_database(path=None):
    """ Calls the `pgdump` command and pipe the contents to a file for backup
        during database population.

        :param path: File path to back up to, or from config if None
    """
    url = _database_url()
    file_path = _database_path() if path is None else path

    with open(file_path, 'wb') as dump:
        process = subprocess.Popen(['pg_dump', '-Fc', str(url)], stdout=dump)
        utils.logger.info(f"Backing up database {repr(url)!r} to {file_path!r}")
        # Wait for process to finish
        process.communicate()


def restore_database(path=None):
    """ Calls the `pg_restore` command to restore data from a file.

        :param path: File path to restore from, or from config if None
    """
    url = _database_url()
    file_path = _database_path() if path is None else path

    process = subprocess.Popen(['pg_restore', '-c', '-Fc', '-d', str(url),
                                file_path])
    utils.logger.info(f"Restoring database {repr(url)!r} from {file_path!r}")
    # Wait for process to finish
    process.communicate()
