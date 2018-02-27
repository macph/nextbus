"""
Modify populated data with list of modify and delete entries, for example to
handle errata in stop point names.
"""
import os

import click
import dateutil.parser as dp
import lxml.etree as et

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import element_as_dict


def _commit_multiple_rows(modify_row_func):
    """ Decorator to iterate over a *list* of XML elements, applying
        modifications with the function and committing changes to the database.
    """
    def modify_rows(instance, model, list_elements):
        try:
            for e in list_elements:
                modify_row_func(instance, model, e)
            db.session.commit()
        except:
            db.session.rollback()
        finally:
            db.session.remove()

    return modify_rows


class _ModifyData(object):
    """ Helper class to modify data after population from creating, deleting
        and replacing rows with a XML file.

        Each subelement must have a model name corresponding to an existing
        table. Each table has a number of ``create``, ``delete`` and
        ``replace`` elements.

        - ``create``: Elements with same names as columns.
        - ``delete``: Attributes used to identify rows to delete.
        - ``replace``: Attributes used to identify rows to modify, with
        elements with same names as columns and optional ``old`` attribute. If
        the old value does not match existing values, a warning is issued.
    """
    MODELS = ["Region", "AdminArea", "District", "Locality", "Postcode",
              "StopArea", "StopPoint"]
    POST_XML_PATH = os.path.join(ROOT_DIR, "nextbus/populate/modify.xml")

    def __init__(self, xml_file):
        try:
            if xml_file is not None and os.path.isabs(xml_file):
                self.xml_data = xml_file
            elif xml_file is not None:
                self.xml_data = os.path.join(ROOT_DIR, xml_file)
            else:
                self.xml_data = self.POST_XML_PATH
        except TypeError as err:
            if "expected str, bytes or os.PathLike object" in str(err):
                # Assume to be a file-like object, for example an opened file
                self.xml_data = xml_file
            else:
                raise

        self.create_count, self.delete_count, self.replace_count = 0, 0, 0
        self.issues = []

    @_commit_multiple_rows
    def _create_row(self, model, element):
        """ Adds new rows to table with data from this element, which should
            have column names as subelements.

            :param model: The database model class.
            :param list_entries: List of ``create`` XML elements.
        """
        # Create each model in a similar way to DBEntries.add()
        data = element_as_dict(element, modified=dp.parse)
        db.session.add(model(**data))
        self.create_count += 1

    @_commit_multiple_rows
    def _delete_row(self, model, element):
        """ Deletes rows from table matching attributes from this element.

            :param model: The database model class.
            :param list_entries: List of ``delete`` XML elements.
        """
        if not element.attrib:
            raise ValueError("Each <delete> element requires at least one "
                                "XML attribute to filter rows.")

        count = model.query.filter_by(**element.attrib).delete()
        if count == 0:
            self.issues.append("No rows matching %r for model %r" %
                                (element.attrib, model.__name__))
        else:
            self.delete_count += count

    @_commit_multiple_rows
    def _replace_row(self, model, element):
        """ Replaces values for rows in tables matching attributes from this
            element.

            :param model: The database model class.
            :param list_entries: List of ``replace`` XML elements.
        """
        if not element.attrib:
            raise ValueError("Each <replace> element requires at least "
                                "one XML attribute to filter rows.")

        matching = model.query.filter_by(**element.attrib)
        matching_entries = matching.all()
        if not matching_entries:
            self.issues.append("No rows matching %r for model %r" %
                                (element.attrib, model.__name__))
            return

        updated_values = {}
        for value in element:
            column = value.tag
            old_value = value.attrib.get("old")
            new_value = value.text
            existing = set(getattr(r, column) for r in matching_entries)
            # Checks if new values already exist
            if existing == {new_value}:
                self.issues.append(
                    "%s.%s: %r for %r already matches %s." %
                    (model.__name__, column, new_value, element.attrib,
                        existing)
                )
                continue
            # Gives a warning if set value does not match the existing
            # value, suggesting it may have been changed in the dataset
            if old_value and any(e != old_value for e in existing):
                self.issues.append(
                    "%s.%s: %r for %r does not match %s." %
                    (model.__name__, column, old_value, element.attrib,
                        existing)
                )
            updated_values[column] = new_value

        if updated_values:
            # Update matched entries
            self.replace_count += matching.update(updated_values)

    def _display_results(self):
        """ Displays number of entries modified and any issues from modifying
            data.
        """
        def entries(count): return count, "s" if count != 1 else ""
        for i in self.issues:
            click.echo(i)
        click.echo("%d row%s created" % entries(self.create_count))
        click.echo("%d row%s deleted" % entries(self.delete_count))
        click.echo("%d row%s replaced" % entries(self.replace_count))

    def process(self):
        """ Parses XML file and carry out insert, delete and update statements.
        """
        data = et.parse(self.xml_data)
        list_tables = data.xpath("table")

        if not all(t.attrib.get("model") in self.MODELS for t in list_tables):
            raise ValueError("Every <table> element in the data must have a "
                             "'model' attribute matching an existing table.")

        click.echo("Processing populated data")
        for table in list_tables:
            model = getattr(models, table.attrib["model"])
            self._create_row(model, table.xpath("create"))
            self._delete_row(model, table.xpath("delete"))
            self._replace_row(model, table.xpath("replace"))

        self._display_results()


def modify_data(xml_file=None):
    """ Calls _ModifyData with a path to an XML file and updates populated
        data.
    """
    m_data = _ModifyData(xml_file)
    m_data.process()


if __name__ == "__main__":
    from nextbus import create_app

    app = create_app(config_obj="default_config.DevelopmentConfig")
    with app.app_context():
        modify_data()
