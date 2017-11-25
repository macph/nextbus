"""
Forms for searching bus stops.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, ValidationError
from wtforms.validators import DataRequired

from nextbus.models import StopPoint, Postcode


def _stop_point_exists(form, field):
    """ Checks if stop point with associated NaPTAN code exists. """
    if len(field.data) != 5 and len(field.data) != 8:
        raise ValidationError("NaPTAN codes should be 5 characters in London "
                              "or 8 characters elsewhere.")
    # Add query object to FlaskForm instance for use by view
    form.query = StopPoint.query.filter(StopPoint.naptan_code
                                        .ilike(field.data)).one_or_none()
    if form.query is None:
        raise ValidationError(("Bus/tram stop with NaPTAN code %r does not "
                               "exist.") % field.data)


def _postcode_exists(form, field):
    """ Checks if postcode exists. """
    new_postcode = ''.join(field.data.split()).upper() # Remove all whitespace
    if not 5 <= len(new_postcode) <= 7:
        raise ValidationError("Postcodes should be between 6 and 8 letters "
                              "long.")
    # Add query object to FlaskForm instance for use by view
    form.query = Postcode.query.filter_by(index=new_postcode).one_or_none()
    if form.query is None:
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
