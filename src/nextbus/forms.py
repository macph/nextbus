"""
Forms for searching bus stops.
"""
from flask_wtf import FlaskForm
from wtforms import fields, validators


class SearchPlaces(FlaskForm):
    """ Full text search for places, stops and postcodes. """
    search = fields.SearchField(
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


def _date_long_form(date):
    """ Displays a date in long form, eg 'Monday 29th April 2019'. """
    second_last = (date.day // 10) % 10
    last = date.day % 10
    if second_last != 1 and last == 1:
        ordinal = "st"
    elif second_last != 1 and last == 2:
        ordinal = "nd"
    elif second_last != 1 and last == 3:
        ordinal = "rd"
    else:
        ordinal = "th"

    return f"{date:%A} {date.day}{ordinal} {date:%B} {date.year}"


class SelectDate(FlaskForm):
    """ Pick a date for service timetable. """
    class Meta(object):
        """ Disable CSRF as this form uses GET. """
        csrf = False

    date = fields.DateField("date")
    _start = None
    _end = None

    @property
    def date_long_form(self):
        if self.date.data is not None:
            return _date_long_form(self.date.data)
        else:
            return None

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
                f"Timetable data for this service is available from "
                f"{_date_long_form(self._start)}."
            )
        if self._end is not None and field.data > self._end:
            raise validators.ValidationError(
                f"Timetable data for this service is available up to "
                f"{_date_long_form(self._end)}."
            )
