# Copyright Ewan Macpherson; see LICENSE
# File operations functionality.

import math
import os
import re
import requests
import zipfile


def print_bytes(x, prefix=None, binary=False, dp=1):
    """ Returns bytes as a readable string, eg 10000 bytes is returned as
        '9.76 KB'.
        :type x: int
        :type prefix: str
        :type binary: bool
        :type dp: str
        :param prefix: Forces a prefix to be used.
        :param binary: Uses binary prefixes (eg '9.76 KiB').
        :param dp: Decimal places for representations with prefixes.
    """
    ls_prefixes = ('', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')

    if prefix is None:
        e = int(math.log2(x) / 10)
        try:
            p = ls_prefixes[e]
        except IndexError:
            p = ls_prefixes[-1]
    else:
        p = prefix.upper()
        e = ls_prefixes.index(p)

    if e == 0:
        dp, i = 0, ''
    else:
        x /= 1024 ** e
        i = 'i' if binary else ''

    return '{0:,.{1}f} {2}{3}B'.format(x, dp, p, i)


def download_file(url, directory='.', *args, **kwargs):
    """ Uses requests to stream and download a file from the Internet.
        See stackoverflow.com/questions/16694907/.
    """
    r = requests.get(url, stream=True)
    find_fn = re.search(r'filename=(.+)',
                        r.headers['content-disposition'])
    if find_fn is not None:
        file_name = find_fn.group(1)
    else:
        raise ValueError(f'No file is available to download from the URL {url!r}.')
    file_size = int(r.headers.get('Content-Length', 0))

    full_name = os.path.join(os.path.abspath(directory), file_name)
    f = open(full_name, 'wb')
    count = 0
    for chunk in r.iter_content(chunk_size=1024):
        if chunk:
            f.write(chunk)
        count += 1
        print(f'\r{1024 * count}', end='')
    f.close()
    print('')
    return full_name


def extract_zipfile(archive, filename, outfile=None):
    """ Extracts a file from a nested ZIP archive. Use standard folder notation
        to find the file, eg in 'archive.zip' the path 'nested.zip/filename'
        will extract 'filename' from 'nested.zip' within 'archive.zip'. To
        give the output file a different name, specify the argument 'outfile'.
    """
    # Replace all '\' with '/' and make all lower
    file_path = filename.replace('\\', '/')
    dir_list = file_path.split('/')
    base_name = dir_list[-1]

    try:
        zp = zipfile.ZipFile(archive)
    except zipfile.BadZipFile as err:
        raise TypeError(f'Archive {archive} is not a valid .zip file.') \
            from err

    extracted_archives = []
    try:
        while True:
            if file_path in zp.namelist():
                break
            elif dir_list[0] in zp.namelist():
                # Extract internal archive as 'TEMP_archive.zip'
                new_zip = 'TEMP_' + dir_list.pop(0)
                zp.extract(new_zip)
                zp.close()
                extracted_archives.append(new_zip)
                file_path = '/'.join(dir_list)
                # Switch opened zip file over to newly extracted archive
                zp = zipfile.ZipFile(new_zip)
            else:
                raise TypeError(f'Cannot find {filename} in archive {archive}')

        new_file = base_name if outfile is None else outfile
        with open(new_file, 'wb') as nf:
            nf.write(zp.read(file_path))
        zp.close()
        return filename

    except zipfile.BadZipFile as err:
        raise TypeError('Nested archive is not a valid .zip file.') from err

    finally:
        for exa in extracted_archives:
            os.remove(exa)

if __name__ == "__main__":
    download_file('http://naptan.app.dft.gov.uk/DataRequest/Naptan.ashx?format=xml&LA=040|210|910',
                  verbose=True)
