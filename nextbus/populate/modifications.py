"""
Modify existing data with list of modify and delete entries.
"""
import os
import json
import click

from definitions import ROOT_DIR
from nextbus import db, models


def _find_modify(entry):
    """ Helper function to find required data and modify them. """
    try:
        model = getattr(models, entry['model'], None)
        if model is None:
            raise ValueError("Model name %r does not exist. Use the Python "
                             "class name, not the DB table name."
                             % entry['model'])

        modify_col = getattr(model, entry['modify_attr'])
        if modify_col is None:
            raise ValueError("Column %r does not exist for model %r."
                             % (entry['modify_attr'], entry['model']))
        new_values = {entry['modify_attr']: entry['new_value']}

        if (entry.get('find_attr') and entry.get('find_values') and
                not entry.get('old_value')):
            query_col = getattr(model, entry['find_attr'])
            query = model.query.filter(query_col.in_(entry['find_values']))
            # Use 'fetch' when querying with in_ filter
            entry = query.update(new_values, synchronize_session='fetch')

        elif (entry.get('old_value') and not entry.get('find_attr') and
                not entry.get('find_values')):
            query_values = {entry['modify_attr']: entry['old_value']}
            entry = model.query.filter_by(**query_values).update(new_values)

        else:
            raise ValueError("Each modification entry must have either an old "
                             "value to find and modify, or a separate column "
                             "with list of values to filter rows by.")

    except KeyError as err:
        raise ValueError("Each modification entry must be a dict with "
                         "the correct keys.") from err

    return entry


def _find_delete(entry):
    """ Helper function to find required data and delete them. """
    try:
        model = getattr(models, entry['model'], None)
        if model is None:
            raise ValueError("Model name %r does not exist. Use the "
                             "Python class name, not the DB table name."
                             % entry['model'])
        values = {entry['attr']: entry['value']}
        entry = model.query.filter_by(**values).delete()
    except KeyError as err:
        raise ValueError("Each delete entry must be a dict with "
                         "keys {model, attr, value}.") from err

    return entry


def modify_data(file_name=None):
    """ Modifies data after populating. Reads a JSON file with 'modify' and
        'delete' keys, each a list of entries, and modifies each entry. Either
        find old value, or use separate column with list of values to filter
        rows to be modified.

        Each 'modify' entry has the keys
        - 'model': class name for data model
        - 'modify_attr': column to modify
        - 'old_value': find old value to modify (optional)
        - 'find_attr': another column to search by (optional)
        - 'find_values': list of values to filter rows (optional)
        - 'new_value': new value

        Each 'delete' entry has keys
        - 'model': class name for data model
        - 'attr': column to match value with
        - 'value': rows with this value in column 'attr' are deleted

    """
    count_m, count_d = 0, 0
    if file_name is None:
        path = os.path.join(ROOT_DIR, 'nextbus/populate/modifications.json')
    else:
        path = file_name
    with open(path, 'r') as jf:
        data = json.load(jf)

    click.echo("Making modifications...")
    for entry in data.get('modify', []):
        count_m += _find_modify(entry)

    for entry in data.get('delete', []):
        count_d += _find_delete(entry)

    click.echo("Committing changes...")
    if count_m + count_d > 0:
        try:
            db.session.commit()
        except:
            db.session.rollback()
    click.echo("%s record%s modified and %s record%s deleted." %
               (count_m, '' if count_m == 1 else 's',
                count_d, '' if count_d == 1 else 's'))
