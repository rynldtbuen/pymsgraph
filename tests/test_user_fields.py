from __future__ import annotations

from pymsgraph.models.user import User
from pymsgraph.models.user.model_fields import PasswordProfile


def test_user_fields_registered() -> None:
    expected = {
        "id",
        "display_name",
        "account_enabled",
        "mail_nickname",
        "user_principal_name",
        "password_profile",
    }
    print(User.FIELDS)
    assert expected.issubset(set(User.FIELDS))


def test_user_required_fields() -> None:
    assert User.REQUIRED_FIELDS == {
        "account_enabled",
        "display_name",
        "mail_nickname",
        "user_principal_name",
    }


def test_password_profile_fields_registered() -> None:
    expected = {
        "password",
        "force_change_password_next_sign_in",
        "force_change_password_next_sign_in_with_mfa",
    }
    assert expected.issubset(set(PasswordProfile.FIELDS))


def test_user_password_profile_model_field_dict_input() -> None:
    u = User(
        password_profile={
            "password": "  a  b  ",
            "force_change_password_next_sign_in": True,
        }
    )
    assert isinstance(u.password_profile, PasswordProfile)

    payload = u.serialize()
    print(payload)
    assert "passwordProfile" in payload
    inner = payload["passwordProfile"]
    assert inner["password"] == "a b"
    assert inner["forceChangePasswordNextSignIn"] is True
