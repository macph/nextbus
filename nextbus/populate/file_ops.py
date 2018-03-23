"""
File operations for opening datasets.
"""
import itertools
import os
import re
import subprocess
import zipfile
import urllib

import requests
from flask import current_app

from definitions import ROOT_DIR
from nextbus.populate import logger


CHUNK_SIZE = 1024
DUMP_FILE_PATH = r"temp/nextbus.db.dump"


def _get_full_path(path):
    """ Use the project directory for relative paths, or the absolute path. """
    return path if os.path.isabs(path) else os.path.join(ROOT_DIR, path)


def _get_file_name(url, response):
    """ Gets the file name from the response header or the URL name. """
    content = response.headers.get("content-disposition")
    if content and "filename" in content:
        file_name = re.search(r"filename=(.+)", content).group(1)
    else:
        # Get the path and split it to get the rightmost part
        path = urllib.parse.urlparse(url)[2]
        file_name = path.split("/")[-1]

    return file_name


def download(url, file_name=None, directory=None, **kwargs):
    """ Downloads files with requests.

        :param url: URL to download from.
        :param file_name: Name of file to be saved. Use 'directory' to specify
        a path. If None, the name is derived from the URL or the header.
        :param directory: Path for directory. If directory is None, the root
        directory is used instead.
        :param kwargs: Keyword arguments for requests.get().
    """
    response = requests.get(url, stream=True, **kwargs)

    dir_path = ROOT_DIR if directory is None else _get_full_path(directory)
    name = _get_file_name(url, response) if file_name is None else file_name
    full_path = os.path.join(dir_path, name)

    logger.info("Downloading %r from %r" % (name, url))
    with open(full_path, 'wb') as out_file:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                out_file.write(chunk)

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


def iter_archive_chunks(archive, chunk=100):
    """ Generator function returning iterables for subsets of files in a
        zipped archive.

        :param archive: Path to the archive file.
        :param chunk: Limit on number of objects from each iterable.
        :returns: Shorter version of ``iter_archive``, limited by chunk size.
    """
    zip_ = zipfile.ZipFile(archive)
    names = iter(zip_.namelist())

    def iter_sub_list(list_files):
        for name in list_files:
            with zip_.open(name) as current:
                yield current

    sub_list = list(itertools.islice(names, chunk))
    while sub_list:
        yield iter_sub_list(sub_list)
        sub_list = list(itertools.islice(names, chunk))
    zip_.close()


def backup_database(dump_file=None):
    """ Calls the ``pgdump`` command and pipe the contents to a file for backup
        during database population.

        :param dump_file: Name of file to back up to
    """
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if db_uri is None:
        raise ValueError("The SQLALCHEMY_DATABASE_URI option is not defined.")
    file_path = DUMP_FILE_PATH if dump_file is None else dump_file
    full_path = _get_full_path(file_path)

    with open(full_path, 'wb') as dump:
        process = subprocess.Popen(['pg_dump', '-Fc', db_uri], stdout=dump)
        logger.info("Backing up database %r to %r" % (db_uri, file_path))
        # Wait for process to finish
        process.communicate()


def restore_database(dump_file=None, error=False):
    """ Calls the ``pg_restore`` command to restore data in case the
        populate command fails. Cleans the database beforehand.

        :param dump_file: Name of file to restore from
    """
    if error:
        logger.warn("Errors occured; restoring database to previous state")
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if db_uri is None:
        raise ValueError("The SQLALCHEMY_DATABASE_URI option is not defined.")
    file_path = DUMP_FILE_PATH if dump_file is None else dump_file
    full_path = _get_full_path(file_path)

    process = subprocess.Popen(['pg_restore', '-c', '-Fc', '-d', db_uri,
                                full_path])
    logger.info("Restoring database %r from %r" % (db_uri, file_path))
    # Wait for process to finish
    process.communicate()
