"""
Forms for searching bus stops.
"""
from flask_wtf import FlaskForm
from wtforms.fields import SubmitField
from wtforms.fields.html5 import SearchField
from wtforms.validators import InputRequired


class SearchPlaces(FlaskForm):
    """ Full text search for places, stops and postcodes. """
    search_query = SearchField("search", validators=[InputRequired()])
    submit_query = SubmitField("Search")
