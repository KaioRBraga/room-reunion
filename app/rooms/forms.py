from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, StringField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, Optional


class RoomForm(FlaskForm):
    name = StringField("Nome", validators=[DataRequired()])
    capacity = IntegerField("Capacidade", validators=[DataRequired(), NumberRange(min=1)])
    location = StringField("Localização", validators=[Optional()])
    equipment_notes = TextAreaField(
        "Equipamentos e o que a sala oferece", validators=[Optional()]
    )
    is_active = BooleanField("Ativa", default=True)
