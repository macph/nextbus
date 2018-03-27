"""
Forms for searching bus stops.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import InputRequired

from nextbus.parser import SET_ALPHANUM


def check_alphanum(query):
    """ Strips out all punctuation and whitespace by using character sets and
        check if the remaining set has enough characters.
    """
    return bool(set(query) & SET_ALPHANUM)


class SearchPlaces(FlaskForm):
    """ Full text search for places, stops and postcodes. """
    search_query = StringField("search", validators=[InputRequired()])
    submit_query = SubmitField("Search")
