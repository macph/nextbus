"""
Forms for searching bus stops.
"""
import string
from flask import current_app
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, ValidationError
from wtforms.validators import DataRequired, InputRequired

from nextbus import parser, search

MIN_CHAR = 3
parse = parser.TSQueryParser(use_logger=True)


def strip_punctuation(query):
    """ Strips out all punctuation by using str.translate(). """
    # Remove all punctuation, leaving behind alphanumeric characters to test
    try:
        translator = query.maketrans(dict.fromkeys(string.punctuation))
        alphanumeric = query.translate(translator)
    except AttributeError as err:
        raise TypeError("query %r is not a valid string." % query) from err

    return alphanumeric


def _check_length(form, field):
    """ Validator to check search query after stripping out punctuation
        characters.
    """
    alpha_num = strip_punctuation(field.data)
    if len(alpha_num) < MIN_CHAR:
        raise ValidationError("Too few letters or digits; try using a longer "
                              "phrase.")


def _search_results(form, field):
    """ Does a search and check if any results pop up. """
    try:
        result = search.search_exists(field.data, parse)
    except ValueError as err:
        current_app.logger.error("Query %r resulted in an parsing error: %s"
                                 % (field.data, err))
        raise ValidationError("There was a problem with your search. Try "
                              "again.")
    except search.PostcodeException as err:
        current_app.logger.debug(str(err))
        raise ValidationError("Postcode '%s' was not found." % err.postcode)

    if result:
        form.query = field.data
        form.result = result
        return
    else:
        raise ValidationError("No stops or places matching your search can be "
                              "found.")


class SearchPlaces(FlaskForm):
    """ Full text search for places, stops and postcodes. """
    search_query = StringField('search', validators=[InputRequired()])
    submit_query = SubmitField('Search')


class SearchPlacesValidate(FlaskForm):
    """ Full text search for places, stops and postcodes, with a quick FTS
        search to check if results do exist before redirecting to the results
        page.
    """
    validators = [DataRequired("Can't search without any words!"),
                  _check_length, _search_results]
    search_query = StringField('search', validators=validators)
    submit_query = SubmitField('Search')

    def __init__(self, *args, **kwargs):
        super(SearchPlacesValidate, self).__init__(*args, **kwargs)
        self.query = None
        self.result = None
