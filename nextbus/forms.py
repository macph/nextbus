"""
Forms for searching bus stops.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, ValidationError
from wtforms.validators import DataRequired

from nextbus import db, models


def _stop_point_exists(form, field):
    """ Checks if stop point with associated NaPTAN code exists. """
    if not 5 <= len(field.data) <= 8:
        raise ValidationError("SMS codes should be between 5 and 8 "
                              "characters long.")
    # Add real code to FlaskForm instance for use by view
    query = (db.session.query(models.StopPoint.naptan_code)
             .filter_by(naptan_code=field.data.lower())
            ).one_or_none()
    if query is not None:
        form.new = query[0]
    else:
        raise ValidationError(("Bus/tram stop with SMS code %r does not "
                               "exist.") % field.data)


def _postcode_exists(form, field):
    """ Checks if postcode exists. """
    new_postcode = ''.join(field.data.split()).upper() # Remove all whitespace
    if not 5 <= len(new_postcode) <= 7:
        raise ValidationError("Postcodes should be between 6 and 8 letters "
                              "long.")
    # Add real postcode to FlaskForm instance for use by view
    query = (db.session.query(models.Postcode.text)
             .filter_by(index=field.data.upper())
            ).one_or_none()
    query = (db.session.query(models.Postcode.text)
             .filter_by(index=new_postcode)
            ).one_or_none()
    if query is not None:
        form.new = query[0]
    else:
        raise ValidationError("Postcode %r does not exist." % field.data)


class FindStop(FlaskForm):
    """ Simple search for bus stop with NaPTAN code. """
    valid = [DataRequired("Can't have an empty SMS code!"), _stop_point_exists]
    code = StringField('naptan_code', validators=valid)
    submit_code = SubmitField('Search')

    def __init__(self, *args, **kwargs):
        super(FindStop, self).__init__(*args, **kwargs)
        self.query = None


class FindPostcode(FlaskForm):
    """ Simple search for bus stops within postcode area. """
    valid = [DataRequired("Can't have an empty postcode!"), _postcode_exists]
    postcode = StringField('postcode', validators=valid)
    submit_postcode = SubmitField('Search')

    def __init__(self, *args, **kwargs):
        super(FindPostcode, self).__init__(*args, **kwargs)
        self.query = None
