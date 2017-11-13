"""
File operations for opening datasets.
"""
import datetime
import os
import zipfile
import requests


CHUNK_SIZE = 1024


def download(url, file_name, directory='.', *args, **kwargs):
    """ Downloads files with requests.

        :param url: URL to download from.
        :param file_name: Name of file to be saved. Use 'directory' to specify
        a path.
        :param directory: Path for where to put the file.
        :param args: Arguments to be passed on to requests.get().
        :param kwargs: Keyword arguments for requests.get().
    """
    req = requests.get(url, *args, stream=True, **kwargs)

    dir_path = os.path.abspath('.') if directory == '.' else directory
    full_path = os.path.join(dir_path, file_name)

    with open(full_path, 'wb') as out_file:
        for chunk in req.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                out_file.write(chunk)

    return full_path, req.headers


def download_zip(url, files=None, directory='.', *args, **kwargs):
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
    temp_path, headers = download(url, temp_file, directory, *args, **kwargs)
    dir_path = os.path.abspath('.') if directory == '.' else directory

    try:
        z_file = zipfile.ZipFile(temp_path)
    except zipfile.BadZipFile as err:
        raise ValueError("File downloaded is not a valid zip archive.") from err
    try:
        list_paths = []
        list_files = files if files is not None else z_file.namelist()
        for file_name in list_files:
            new = z_file.extract(file_name, path=dir_path)
            list_paths.append(new)
    finally:
        z_file.close()
        os.remove(temp_path)

    return list_paths, headers


if __name__ == "__main__":
    NSPL_URL = r'https://opendata.camden.gov.uk/resource/ry6e-hbqy.json'
    NAPTAN_URL = r'http://naptan.app.dft.gov.uk/DataRequest/Naptan.ashx'
    NSPL_PARAMS = {
        '$select': "postcode_3, easting, northing, local_authority_code, longitude, latitude",
        '$where': ("local_authority_code='E08000016' OR local_authority_code='E08000017' "
                   "OR local_authority_code='E08000018' OR local_authority_code='E08000019'"),
        '$limit': 50000
    }
    NAPTAN_PARAMS = {
        'format': 'xml',
        'LA': '|'.join(['370', '940'])
    }

    download(NSPL_URL, file_name='nspl.json', params=NSPL_PARAMS)
    download_zip(NAPTAN_URL, ['NaPTAN370.xml'], params=NAPTAN_PARAMS)
