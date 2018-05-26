"""
Forms for searching bus stops.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import InputRequired


class SearchPlaces(FlaskForm):
    """ Full text search for places, stops and postcodes. """
    search_query = StringField("search", validators=[InputRequired()])
    submit_query = SubmitField("Search")
