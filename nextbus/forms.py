"""
Forms for searching bus stops.
"""
import string
from flask import current_app
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, ValidationError
from wtforms.validators import DataRequired

from nextbus import parser, search


parse = parser.TSQueryParser(use_logger=True)


def _search_results(form, field):
    """ Does a search and check if any results pop up. """
    # Remove all punctuation, leaving behind alphanumeric characters to test
    translator = field.data.maketrans(dict.fromkeys(string.punctuation))
    alpha_num = field.data.translate(translator)
    if len(alpha_num) < 3:
        raise ValidationError("Too few letters or digits; try using a longer "
                              "phrase.")
    try:
        result = search.search_exists(field.data, parse.parse_query)
    except ValueError as err:
        current_app.logger.error("Query %r resulted in an parsing error: %s"
                                 % (field.data, err))
        raise ValidationError("There was a problem with your search. Try "
                              "again.")
    except search.LimitException as err:
        current_app.logger.debug(str(err))
        raise ValidationError("Too many results found, try narrowing your "
                              "search. If you know the area you can do a "
                              "search of the form 'name @ location'")
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
    valid = [DataRequired("Can't search without any words!"), _search_results]
    search_query = StringField('search', validators=valid)
    submit_query = SubmitField('Search')

    def __init__(self, *args, **kwargs):
        super(SearchPlaces, self).__init__(*args, **kwargs)
        self.query = None
        self.result = None
