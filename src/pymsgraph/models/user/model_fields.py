from typing import Any

from pymsgraph import models


class PasswordProfile(models.Model):
    password = models.CharField()
    force_change_password_next_sign_in = models.BooleanField(default=True)
    force_change_password_next_sign_in_with_mfa = models.BooleanField(default=False)


class AssignedLicenses(models.QuerySet):
    pass
