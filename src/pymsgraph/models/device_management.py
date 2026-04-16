from __future__ import annotations

from typing import TYPE_CHECKING

from pymsgraph.models.base import ReadOnlyModel
from pymsgraph.models.fields import (
    BooleanField,
    CharField,
    DateTimeField,
    Field,
    IntegerField,
    ListField,
)
from pymsgraph.models.query import QuerySet

if TYPE_CHECKING:
    from pymsgraph.client import Client


class ManagedDevice(ReadOnlyModel):
    """
    Graph `managedDevice` resource.

    https://learn.microsoft.com/en-us/graph/api/resources/intune-devices-manageddevice?view=graph-rest-1.0
    """

    PATH = "/managedDevices"

    # Identity / enrollment
    activation_lock_bypass_code = CharField()
    android_security_patch_level = CharField()
    azure_ad_device_id = CharField()
    azure_ad_registered = BooleanField()
    compliance_grace_period_expiration_date_time = DateTimeField()
    compliance_state = CharField()
    configuration_manager_client_enabled_features = Field()
    device_enrollment_type = CharField()
    device_name = CharField(select_default=True, order_by=True)
    device_registration_state = CharField()
    enrolled_date_time = DateTimeField(order_by=True)
    enrollment_profile_name = CharField()

    # Device identifiers / connectivity
    eas_activated = BooleanField()
    eas_activation_date_time = DateTimeField()
    eas_device_id = CharField()
    email_address = CharField()
    ethernet_mac_address = CharField()
    exchange_access_state = CharField()
    exchange_access_state_reason = CharField()
    exchange_last_successful_sync_date_time = DateTimeField()
    iccid = CharField()
    imei = CharField()
    meid = CharField()
    serial_number = CharField()
    subscriber_carrier = CharField()
    udid = CharField()
    wi_fi_mac_address = CharField()

    # Security / management state
    is_encrypted = BooleanField()
    is_supervised = BooleanField()
    jail_broken = CharField()
    last_sync_date_time = DateTimeField(order_by=True)
    management_agent = CharField()
    management_certificate_expiration_date = DateTimeField()
    management_state = CharField()
    partner_reported_threat_state = CharField()
    require_user_enrollment_approval = BooleanField()

    # Hardware / OS
    free_storage_space_in_bytes = IntegerField()
    manufacturer = CharField()
    model = CharField()
    operating_system = CharField(select_default=True, order_by=True)
    os_version = CharField()
    physical_memory_in_bytes = IntegerField()
    total_storage_space_in_bytes = IntegerField()

    # Ownership / user affinity
    device_category = Field()
    device_category_display_name = CharField()
    device_action_results = ListField()
    device_compliance_policy_states = ListField()
    device_configuration_states = ListField()
    device_health_attestation_state = Field()
    log_collection_requests = ListField()
    managed_device_name = CharField()
    managed_device_owner_type = CharField()
    notes = CharField()
    phone_number = CharField()
    remote_assistance_session_error_details = CharField()
    remote_assistance_session_url = CharField()
    user_display_name = CharField()
    user_id = CharField()
    user_principal_name = CharField(select_default=True, order_by=True)
    users = ListField(item_type="User")

    # Platform-specific state
    windows_protection_state = Field()

    def __repr__(self) -> str:
        return f"<ManagedDevice: {self.device_name or self.id}>"


class ManagedDeviceQuerySet(QuerySet[ManagedDevice]):
    """
    QuerySet for Graph managed devices (`/deviceManagement/managedDevices`).
    """

    model_class = ManagedDevice


class WindowsAutoPilotDeviceIdentity(ReadOnlyModel):
    """
    Graph `windowsAutopilotDeviceIdentity` resource.

    https://learn.microsoft.com/en-us/graph/api/resources/intune-enrollment-windowsautopilotdeviceidentity?view=graph-rest-1.0
    """

    PATH = "/windowsAutopilotDeviceIdentities"

    addressable_user_name = CharField()
    azure_active_directory_device_id = CharField()
    display_name = CharField(select_default=True, order_by=True)
    enrollment_state = CharField()
    group_tag = CharField()
    last_contacted_date_time = DateTimeField(order_by=True)
    managed_device_id = CharField()
    manufacturer = CharField()
    model = CharField()
    product_key = CharField()
    purchase_order_identifier = CharField()
    resource_name = CharField()
    serial_number = CharField(select_default=True, order_by=True)
    sku_number = CharField()
    system_family = CharField()
    user_principal_name = CharField(select_default=True, order_by=True)

    def __repr__(self) -> str:
        return (
            f"<WindowsAutoPilotDeviceIdentity: "
            f"{self.serial_number or self.display_name or self.id}>"
        )


class WindowsAutoPilotDeviceIdentityQuerySet(
    QuerySet[WindowsAutoPilotDeviceIdentity]
):
    """
    QuerySet for Graph Windows Autopilot device identities
    (`/deviceManagement/windowsAutopilotDeviceIdentities`).
    """

    model_class = WindowsAutoPilotDeviceIdentity


class DeviceManagementProxy:
    """
    Root proxy for Microsoft Graph device management endpoints.
    """

    def __init__(self, client: "Client") -> None:
        self._client = client

    @property
    def managed_devices(self) -> ManagedDeviceQuerySet:
        """
        Return Intune managed devices queryset.

        Returns:
            ManagedDeviceQuerySet:
                QuerySet bound to `/deviceManagement/managedDevices`.
        """
        return ManagedDeviceQuerySet(
            self._client,
            path="/deviceManagement/managedDevices",
        )

    @property
    def windows_autopilot_device_identities(
        self,
    ) -> WindowsAutoPilotDeviceIdentityQuerySet:
        """
        Return Windows Autopilot device identities queryset.

        Returns:
            WindowsAutoPilotDeviceIdentityQuerySet:
                QuerySet bound to `/deviceManagement/windowsAutopilotDeviceIdentities`.
        """
        return WindowsAutoPilotDeviceIdentityQuerySet(
            self._client,
            path="/deviceManagement/windowsAutopilotDeviceIdentities",
        )
