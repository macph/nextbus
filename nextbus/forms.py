"""
Forms for searching bus stops.
"""
from flask_wtf import FlaskForm
from wtforms import fields, validators, widgets
import wtforms.fields.html5 as html5_fields


class SearchPlaces(FlaskForm):
    """ Full text search for places, stops and postcodes. """
    search_query = html5_fields.SearchField(
        "search", validators=[validators.InputRequired()]
    )
    submit_query = fields.SubmitField("Search")


class MultipleCheckboxField(fields.SelectMultipleField):
    """ Sets up a list of checkboxes for multiple choices. """
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

    def render_elements(self, **kwargs):
        """ Creates a list of elements with each checkbox input within its
            associated label element.
        """
        list_elements = []
        for item in self:
            label = item.label(str(item) + " " + item.label.text, **kwargs)
            list_elements.append(label)

        return list_elements


class FilterResults(FlaskForm):
    """ Search results filtering by stops and areas. """
    class Meta(object):
        """ Disable CSRF as this form uses GET. """
        csrf = False

    group = MultipleCheckboxField("group")
    area = MultipleCheckboxField("area")
    page = fields.IntegerField("page", default=1)

    def add_choices(self, groups, areas):
        """ Populate with available choices and selected by arguments passed
            after the form is instantiated.

            :param groups: Dict with groups to select.
            :param areas: Dict with admin areas to select.
        """
        self.group.choices = sorted(groups.items(), key=lambda g: g[1])
        self.area.choices = sorted(areas.items(), key=lambda a: a[1])


class SelectDate(FlaskForm):
    """ Pick a date for service timetable. """
    class Meta(object):
        """ Disable CSRF as this form uses GET. """
        csrf = False

    date = html5_fields.DateField("date")
