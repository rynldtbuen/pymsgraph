from __future__ import annotations

from typing import Any

from pymsgraph.models.base import PropertyModel, ReadOnlyModel
from pymsgraph.models.fields import (
    BooleanField,
    CharField,
    DateTimeField,
    EmailField,
    Field,
    ListField,
    ListProxy,
    ListProxyField,
)
from pymsgraph.models.subscribed_sku import SubscribedSku


class PasswordProfile(PropertyModel):
    password = CharField()
    force_change_password_next_sign_in = BooleanField(default=True)
    force_change_password_next_sign_in_with_mfa = BooleanField(default=False)


class AssignedLicense(PropertyModel, ReadOnlyModel):
    PATH = "/assignLicense"

    sku_id = CharField()
    disabled_plans = Field()

    @property
    def id(self):
        return self.sku_id

    @property
    def product_name(self):
        return SubscribedSku.get_product_name(sku_id=self.sku_id)


class AssignedPlans(PropertyModel, ReadOnlyModel):
    assigned_date_time = DateTimeField()
    capability_status = CharField()
    service = CharField()
    service_plan_id = CharField()


class EmployeeOrgData(PropertyModel):
    cost_center = CharField()
    division = CharField()


class EmailAuthenticationMethod(ReadOnlyModel):
    PATH = "/emailMethods"

    email_address = EmailField()

    @property
    def id(self) -> str:
        return "3ddfcfc8-9383-446f-83cc-3ab9be4be18f"


class EmailAuthenticationMethodProxy(ListProxy):
    model_class = EmailAuthenticationMethod


class Fido2AuthenticationMethod(ReadOnlyModel):
    """
    Graph fido2AuthenticationMethod resource type
    """

    PATH = "/fido2Methods"

    aa_guid = CharField()
    attestation_certificates = ListField()
    attestation_level = CharField()
    created_date_time = DateTimeField()
    display_name = CharField()
    model = CharField()


class MicrosoftAuthenticatorAuthenticationMethod(ReadOnlyModel):
    PATH = "/microsoftAuthenticatorMethods"


class PasswordAuthenticationMethod(ReadOnlyModel):
    PATH = "/passwordMethods"


class PhoneAuthenticationMethod(ReadOnlyModel):
    PATH = "/phoneMethods"


class PlatformCredentialAuthenticationMethod(ReadOnlyModel):
    PATH = "/platformCredentialMethods"


class SoftwareOathAuthenticationMethod(ReadOnlyModel):
    PATH = "/softwareOathMethods"


class TemporaryAccessPassAuthenticationMethod(ReadOnlyModel):
    PATH = "/temporaryAccessPassMethods"


class WindowsHelloForBusinessAuthenticationMethod(ReadOnlyModel):
    PATH = "/windowsHelloForBusinessMethods"


class AuthenticationMethod(ReadOnlyModel):
    """
    Base authenticationMethod that dispatches to concrete types based on @odata.type.
    """

    ODATA_TYPE_MAP: dict[str, type[ReadOnlyModel]] = {
        "#microsoft.graph.emailAuthenticationMethod": EmailAuthenticationMethod,
        "#microsoft.graph.fido2AuthenticationMethod": Fido2AuthenticationMethod,
        "#microsoft.graph.microsoftAuthenticatorAuthenticationMethod": MicrosoftAuthenticatorAuthenticationMethod,
        "#microsoft.graph.passwordAuthenticationMethod": PasswordAuthenticationMethod,
        "#microsoft.graph.phoneAuthenticationMethod": PhoneAuthenticationMethod,
        "#microsoft.graph.platformCredentialAuthenticationMethod": PlatformCredentialAuthenticationMethod,
        "#microsoft.graph.softwareOathAuthenticationMethod": SoftwareOathAuthenticationMethod,
        "#microsoft.graph.temporaryAccessPassAuthenticationMethod": TemporaryAccessPassAuthenticationMethod,
        "#microsoft.graph.windowsHelloForBusinessAuthenticationMethod": WindowsHelloForBusinessAuthenticationMethod,
    }

    @classmethod
    def from_graph(
        cls,
        data: dict[str, Any],
        *,
        client=None,
        path: str | None = None,
    ):
        odata_type: str | None = data.get("@odata.type")
        if odata_type:
            target = cls.ODATA_TYPE_MAP.get(odata_type)
            if target is cls:
                return super().from_graph(data, client=client, path=path)
            if target:
                return target.from_graph(data, client=client, path=path)
        raise RuntimeError("Unknown authentication method type,")


# AuthenticationMethod.ODATA_TYPE_MAP =


class Authentication(PropertyModel, ReadOnlyModel):
    """
    Graph authentication resource type (user).

    https://learn.microsoft.com/en-us/graph/api/resources/authentication
    """

    PATH = "/authentication"

    email_methods = ListProxyField(EmailAuthenticationMethodProxy)
    fido2_methods = ListProxyField(ListProxy, Fido2AuthenticationMethod)
    methods = ListProxyField(ListProxy, AuthenticationMethod)
    microsoft_authenticator_methods = ListProxyField(
        ListProxy, MicrosoftAuthenticatorAuthenticationMethod
    )
    operations = ListProxyField()
    password_methods = ListProxyField(ListProxy, PasswordAuthenticationMethod)
    phone_methods = ListProxyField(ListProxy, PhoneAuthenticationMethod)
    platform_credential_methods = ListProxyField(
        ListProxy, PlatformCredentialAuthenticationMethod
    )
    software_oath_methods = ListProxyField(ListProxy, SoftwareOathAuthenticationMethod)
    temporary_access_pass_methods = ListProxyField(
        ListProxy, TemporaryAccessPassAuthenticationMethod
    )
    windows_hello_for_business_methods = ListProxyField(
        ListProxy, WindowsHelloForBusinessAuthenticationMethod
    )
