"""
File operations for opening datasets.
"""
import datetime
import os
import subprocess
import zipfile
import requests
import click
from flask import current_app
from definitions import ROOT_DIR


CHUNK_SIZE = 1024
DUMP_FILE_PATH = r"temp/nextbus.db.dump"


def _get_full_path(path):
    """ Find the absolute path, using the project directory for relative paths.
    """
    if not os.path.isabs(path):
        full_path = os.path.join(ROOT_DIR, path)
    else:
        full_path = path

    return full_path


def download(url, file_name, directory=None, **kwargs):
    """ Downloads files with requests.

        :param url: URL to download from.
        :param file_name: Name of file to be saved. Use 'directory' to specify
        a path.
        :param directory: Path for where to put the file.
        :param args: Arguments to be passed on to requests.get().
        :param kwargs: Keyword arguments for requests.get().
    """
    dir_path = ROOT_DIR if directory is None else _get_full_path(directory)
    full_path = os.path.join(dir_path, file_name)

    click.echo("Downloading %r from %r" % (file_name, url))
    req = requests.get(url, stream=True, **kwargs)
    with open(full_path, 'wb') as out_file:
        for chunk in req.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                out_file.write(chunk)

    return full_path


def download_zip(url, files=None, directory=None, **kwargs):
    """ Downloads zip file from an URL and extracts specified files from it.

        :param url: URL to download from.
        :param files: List of files to extract from archive. If None, all files
        are extracted.
        :param directory: Path for where to put the files in. The temporary zip
        archive is also stored here.
        :param args: Arguments to be passed on to requests.get().
        :param kwargs: Keyword arguments for requests.get().
    """
    temp_file = 'TEMP_%d.zip' % int(datetime.datetime.now().timestamp())
    temp_path = download(url, temp_file, directory, **kwargs)
    dir_path = ROOT_DIR if directory is None else _get_full_path(directory)

    try:
        z_file = zipfile.ZipFile(temp_path)
    except zipfile.BadZipFile as err:
        raise ValueError("File downloaded is not a valid archive.") from err
    try:
        list_paths = []
        list_files = files if files is not None else z_file.namelist()
        for file_name in list_files:
            new = z_file.extract(file_name, path=dir_path)
            list_paths.append(new)
    finally:
        z_file.close()
        os.remove(temp_path)

    return list_paths


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
        click.echo("Backing up database %r to %r" % (db_uri, file_path))
        # Wait for process to finish
        process.communicate()


def restore_database(dump_file=None):
    """ Calls the ``pg_restore`` command to restore data in case the
        populate command fails. Cleans the database beforehand.

        :param dump_file: Name of file to restore from
    """
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if db_uri is None:
        raise ValueError("The SQLALCHEMY_DATABASE_URI option is not defined.")
    file_path = DUMP_FILE_PATH if dump_file is None else dump_file
    full_path = _get_full_path(file_path)

    process = subprocess.Popen(['pg_restore', '-c', '-Fc', '-d', db_uri,
                                full_path])
    click.echo("Restorting database %r from %r" % (db_uri, file_path))
    # Wait for process to finish
    process.communicate()
