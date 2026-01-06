from typing import Any

from pymsgraph.models import fields
from pymsgraph.models.base import Model


class PasswordProfile(Model):
    password = fields.CharField()
    force_change_password_next_sign_in = fields.BooleanField(default=True)
    force_change_password_next_sign_in_with_mfa = fields.BooleanField(default=False)
