from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    IntegerField,
    SelectField,
    SelectMultipleField,
    StringField,
)
from wtforms.validators import DataRequired, NumberRange, Optional, ValidationError
from wtforms.widgets import CheckboxInput, ListWidget

EQUIPMENT_OPTIONS = [
    "Projetor",
    "TV",
    "Quadro branco",
    "Videoconferência",
    "Ar condicionado",
    "Cabo HDMI",
    "Sistema de som",
    "Flipchart",
]


class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


def half_hour_choices():
    choices = [("", "Sem restrição")]
    for hour in range(0, 24):
        for minute in (0, 30):
            value = f"{hour:02d}:{minute:02d}"
            choices.append((value, value))
    return choices


class RoomForm(FlaskForm):
    name = StringField("Nome", validators=[DataRequired()])
    capacity = IntegerField("Capacidade", validators=[DataRequired(), NumberRange(min=1)])
    location = StringField("Localização", validators=[Optional()])
    equipment_checklist = MultiCheckboxField(
        "Equipamentos disponíveis", choices=[(e, e) for e in EQUIPMENT_OPTIONS]
    )
    equipment_other = StringField(
        "Outros equipamentos (separados por vírgula)", validators=[Optional()]
    )
    min_attendees = SelectField(
        "Mínimo de participantes",
        choices=[("", "Sem mínimo"), ("3", "3"), ("4", "4"), ("5", "5")],
        validators=[Optional()],
    )
    business_hours_start = SelectField(
        "Horário comercial - início", choices=half_hour_choices(), validators=[Optional()]
    )
    business_hours_end = SelectField(
        "Horário comercial - fim", choices=half_hour_choices(), validators=[Optional()]
    )
    is_active = BooleanField("Ativa", default=True)

    def validate_business_hours_end(self, field):
        if self.business_hours_start.data and field.data and field.data <= self.business_hours_start.data:
            raise ValidationError("O horário de fim deve ser depois do início.")
