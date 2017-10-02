"""
Forms for searching bus stops.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, ValidationError
from wtforms.validators import DataRequired, Length

from nextbus.models import StopPoint, Postcode


class CheckEntryExists(object):
    """ Checks if row with certain value exists for a table - used for
        validating a form.
    """
    def __init__(self, model, key, message=None):
        self.model = model
        self.key = key
        if not message:
            self.message = "Entry %r with value %r does not exist."
        else:
            self.message = message

    def __call__(self, form, field):
        kwargs = {self.key: field.data}
        query = self.model.query.filter_by(**kwargs).scalar()
        if query is None:
            raise ValidationError(self.message)


def stop_point_exists(form, field):
    """ Checks if stop point with associated NaPTAN code exists. """
    query = StopPoint.query.filter_by(naptan_code=field.data).scalar()
    if query is None:
        raise ValidationError(("Bus/tram stop with NaPTAN code %r does not "
                               "exist.") % field.data)


def postcode_exists(form, field):
    """ Checks if postcode exists. """
    new_postcode = ''.join(field.data.split()).upper() # Remove all whitespace
    query = Postcode.query.filter_by(postcode_2=new_postcode).scalar()
    if query is None:
        raise ValidationError("Postcode %r does not exist." % field.data)


class FindStop(FlaskForm):
    """ Simple search for bus stop with NaPTAN code. """
    _message_length = ("NaPTAN codes should be 5 digits (in London) or 8 "
                       "digits (elsewhere).")
    code = StringField(
        'naptan_code',
        validators=[DataRequired(),
                    Length(min=5, max=8, message=_message_length),
                    stop_point_exists]
    )

class FindPostcode(FlaskForm):
    """ Simple search for bus stops within postcode area. """
    _message_length = "Postcodes should be between 6 and 8 letters long."
    postcode = StringField(
        'postcode',
        validators=[DataRequired(),
                    Length(min=5, max=8, message=_message_length),
                    postcode_exists]
    )
