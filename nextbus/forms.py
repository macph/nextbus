"""
Forms for searching bus stops.
"""
from flask_wtf import FlaskForm
from wtforms.fields import IntegerField, SelectMultipleField, SubmitField
from wtforms.fields.html5 import SearchField
from wtforms.validators import InputRequired
from wtforms.widgets import CheckboxInput, ListWidget


class SearchPlaces(FlaskForm):
    """ Full text search for places, stops and postcodes. """
    search_query = SearchField("search", validators=[InputRequired()])
    submit_query = SubmitField("Search")


class MultipleCheckboxField(SelectMultipleField):
    """ Sets up a list of checkboxes for multiple choices. """
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

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
    page = IntegerField("page", default=1)

    def add_choices(self, groups, areas):
        """ Populate with available choices and selected by arguments passed
            after the form is instantiated.

            :param groups: Dict with groups to select.
            :param areas: Dict with admin areas to select.
        """
        self.group.choices = sorted(groups.items(), key=lambda g: g[1])
        self.area.choices = sorted(areas.items(), key=lambda a: a[1])
