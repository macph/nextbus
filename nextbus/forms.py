"""
Forms for searching bus stops.
"""
import string
from flask import current_app
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, ValidationError
from wtforms.validators import DataRequired, InputRequired

from nextbus import search
from nextbus.parser import SET_ALPHANUM


def check_alphanum(query):
    """ Strips out all punctuation and whitespace by using character sets and
        check if the remaining set has enough characters.
    """
    return bool(set(query) & SET_ALPHANUM)


def _validate_length(form, field):
    """ Validator to check search query after stripping out punctuation
        characters.
    """
    if not check_alphanum(field.data):
        raise ValidationError("Not enough letters or numbers; try a longer "
                              "phrase.")


def _search_results(form, field):
    """ Does a search and check if any results pop up. """
    try:
        result = search.search_exists(field.data)
    except ValueError as err:
        current_app.logger.error("Query %r resulted in an parsing error: %s"
                                 % (field.data, err), exc_info=True)
        raise ValidationError("There was a problem with your search. Try "
                              "again.")
    except search.PostcodeException as err:
        current_app.logger.debug(str(err))
        raise ValidationError("Postcode '%s' was not found; it may not exist "
                              "or lies outside the area this website covers"
                              % err.postcode)
    if result:
        form.query = field.data
        form.result = result
        return
    else:
        raise ValidationError("No stops or places matching your search can be "
                              "found.")


class SearchPlaces(FlaskForm):
    """ Full text search for places, stops and postcodes. """
    search_query = StringField("search", validators=[InputRequired()])
    submit_query = SubmitField("Search")


class SearchPlacesValidate(FlaskForm):
    """ Full text search for places, stops and postcodes, with a quick FTS
        search to check if results do exist before redirecting to the results
        page.
    """
    validators = [DataRequired("Can't search without any words!"),
                  _validate_length, _search_results]
    search_query = StringField("search", validators=validators)
    submit_query = SubmitField("Search")

    def __init__(self, *args, **kwargs):
        super(SearchPlacesValidate, self).__init__(*args, **kwargs)
        self.query = None
        self.result = None
