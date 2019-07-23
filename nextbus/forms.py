"""
Forms for searching bus stops.
"""
from flask_wtf import FlaskForm
from wtforms import fields, validators, widgets
import wtforms.fields.html5 as html5_fields


class SearchPlaces(FlaskForm):
    """ Full text search for places, stops and postcodes. """
    search = html5_fields.SearchField(
        "search", validators=[validators.InputRequired()]
    )
    submit = fields.SubmitField("Search")


class FilterResults(FlaskForm):
    """ Search results filtering by stops and areas. """
    class Meta(object):
        """ Disable CSRF as this form uses GET. """
        csrf = False

    group = fields.SelectMultipleField("group")
    area = fields.SelectMultipleField("area")
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
    _start = None
    _end = None

    def set_dates(self, service):
        """ Sets starting and ending dates from a service's patterns for
            validation.
        """
        self._start = min(p.date_start for p in service.patterns)

        if all(p.date_end is not None for p in service.patterns):
            self._end = max(p.date_end for p in service.patterns)
        else:
            self._end = None

    def validate_date(self, field):
        """ Validates date based on starting and ending dates given. """
        if field.data is None:
            return
        if self._start is not None and field.data < self._start:
            raise validators.ValidationError(
                "Timetable data for this service is available from %s." %
                self._start.strftime("%d/%m/%Y")
            )

        if self._end is not None and field.data > self._end:
            raise validators.ValidationError(
                "Timetable data for this service is available up to %s." %
                self._end.strftime("%d/%m/%Y")
            )
