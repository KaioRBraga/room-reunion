from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, Optional, Regexp, ValidationError

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PIN_REGEX = r"^\d{4,6}$"


class LoginForm(FlaskForm):
    username = StringField("Usuário", validators=[DataRequired()])
    password = PasswordField("Senha", validators=[DataRequired()])


class ProfileForm(FlaskForm):
    email = StringField(
        "E-mail",
        validators=[Optional(), Regexp(EMAIL_REGEX, message="Informe um e-mail válido.")],
    )


class PinForm(FlaskForm):
    pin = PasswordField(
        "Novo PIN (4 a 6 dígitos)",
        validators=[DataRequired(), Regexp(PIN_REGEX, message="O PIN deve ter de 4 a 6 dígitos numéricos.")],
    )
    pin_confirm = PasswordField("Confirme o PIN", validators=[DataRequired()])

    def validate_pin_confirm(self, field):
        if field.data != self.pin.data:
            raise ValidationError("Os PINs não coincidem.")
