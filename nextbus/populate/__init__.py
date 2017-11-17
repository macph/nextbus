"""
Populating database with data from NPTG, NaPTAN and NSPL.
"""
import os
import itertools
import json
import re
import click
from definitions import ROOT_DIR
from nextbus import db, models


def progress_bar(iterable, **kwargs):
    """ Returns click.progressbar with specific options. """
    return click.progressbar(
        iterable=iterable,
        bar_template="%(label)-32s [%(bar)s] %(info)s",
        show_pos=True,
        width=50,
        **kwargs
    )


class XPath(object):
    """ Helper class for XPath queries in a dataset, with the assumption that
        all sub elements have the same namespace. Adds prefixes to each XPath
        query automatically.
    """
    # Ignores all words enclosed in quotes, spaces or prefixed with ':' or '@'.
    re_prefix = re.compile(r"(?<![:\"'@\s])(\b\w+\b)(?![:\"'\s])")

    def __init__(self, element, prefix='a'):
        self.element = element
        self.prefix = prefix
        namespace = self.element.xpath("namespace-uri(.)")
        self.namespace = {self.prefix: namespace} if namespace else None

    def __call__(self, path, element=None):
        """ Calls XPath query for a path, adding prefixes if necessary """
        new_path = self.re_prefix.sub(lambda s: "%s:%s" % (self.prefix, s.group()), path)
        element = self.element if element is None else element
        return element.xpath(new_path, namespaces=self.namespace)

    def text(self, path, element=None):
        """ Calls a XPath query and returns the text contained within the first
            element if it is the only matching result.
        """
        nodes = self(path, element)
        if len(nodes) == 1:
            return getattr(nodes[0], 'text', nodes[0])
        elif len(nodes) > 1:
            element = self.element if element is None else element
            raise ValueError("Multiple elements matching XPath query %r for "
                             "element %r." % (path, element))
        else:
            raise ValueError("No elements match XPath query %r for element "
                             "%r." % (path, element))

    def iter_text(self, path, elements):
        """ Iterates over a list of elements with the same XPath query,
            returning a list of text values.
        """
        return [self.text(path, element=node) for node in elements]

    def dict_text(self, dict_paths, element=None):
        """ Returns a dict of text values obtained from processing a dict with
            XPath queries as values for a single element. If a query returns no
            elements, the key is assigned value None.
        """
        result = {}
        for arg, path in dict_paths.items():
            try:
                text = self.text(path, element)
            except ValueError as err:
                if "No elements" in str(err):
                    text = None
                else:
                    raise ValueError from err
            result[arg] = text

        return result


class IterChunk(object):
    """ Generator for an iterator object returning lists at a time. """
    def __init__(self, iterator, chunk_size):
        self.iter = iterator
        self.chunk = chunk_size

    def __next__(self):
        chunk = list(itertools.islice(self.iter, self.chunk))
        if chunk:
            return chunk
        else:
            raise StopIteration

    def __iter__(self):
        return self


def modify_data(file_name=None):
    """ Modifies data after populating. Reads a JSON file with 'modify' and
        'delete' keys, each a list of entries, and modifies each entry.
    """
    count_m, count_d = 0, 0
    if file_name is None:
        path = os.path.join(ROOT_DIR, 'nextbus/populate/modifications.json')
    else:
        path = file_name
    with open(path, 'r') as json_file:
        data = json.load(json_file)

    click.echo("Making modifications...")
    for entry in data.get('modify', []):
        try:
            model = getattr(models, entry['model'], None)
            if model is None:
                raise ValueError("Model name %r does not exist. Use the "
                                 "Python class name, not the DB table name."
                                 % entry['model'])
            old_values = {entry['attr']: entry['old']}
            new_values = {entry['attr']: entry['new']}
            entry = model.query.filter_by(**old_values).update(new_values)
            if entry > 0:
                count_m += 1
        except KeyError as err:
            raise ValueError("Each modification entry must be a dict with "
                             "keys {model, attr, old, new}.") from err

    for entry in data.get('delete', []):
        try:
            model = getattr(models, entry['model'], None)
            if model is None:
                raise ValueError("Model name %r does not exist. Use the "
                                 "Python class name, not the DB table name."
                                 % entry['model'])
            values = {entry['attr']: entry['value']}
            entry = model.query.filter_by(**values).delete()
            if entry > 0:
                count_d += 1
        except KeyError as err:
            raise ValueError("Each delete entry must be a dict with "
                             "keys {model, attr, value}.") from err

    if count_m + count_d > 0:
        try:
            db.session.commit()
        except:
            db.session.rollback()
    click.echo("%s record%s modified and %s record%s deleted." %
               (count_m, '' if count_m == 1 else 's',
                count_d, '' if count_d == 1 else 's'))
