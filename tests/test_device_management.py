import json
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from pymsgraph import Client

import pytest

from pymsgraph.device_management import DeviceManagement, ManagedDevices


@pytest.fixture
def device_management(client: "Client") -> DeviceManagement:
    return client.device_management


@pytest.fixture
def managed_devices_data() -> dict[str, Any]:
    data = """
    {
       	"value": [
       		{
       			"@odata.type": "#microsoft.graph.managedDevice",
       			"id": "705c034c-034c-705c-4c03-5c704c035c70",
       			"userId": "User Id value",
       			"deviceName": "Device Name value",
       			"managedDeviceOwnerType": "company",
       			"deviceActionResults": [
       				{
       					"@odata.type": "microsoft.graph.deviceActionResult",
       					"actionName": "Action Name value",
       					"actionState": "pending",
       					"startDateTime": "2016-12-31T23:58:46.7156189-08:00",
       					"lastUpdatedDateTime": "2017-01-01T00:00:56.8321556-08:00"
       				}
       			],
       			"enrolledDateTime": "2016-12-31T23:59:43.797191-08:00",
       			"lastSyncDateTime": "2017-01-01T00:02:49.3205976-08:00",
       			"operatingSystem": "Operating System value",
       			"complianceState": "compliant",
       			"jailBroken": "Jail Broken value",
       			"managementAgent": "mdm",
       			"osVersion": "Os Version value",
       			"easActivated": true,
       			"easDeviceId": "Eas Device Id value",
       			"easActivationDateTime": "2016-12-31T23:59:43.4878784-08:00",
       			"azureADRegistered": true,
       			"deviceEnrollmentType": "userEnrollment",
       			"activationLockBypassCode": "Activation Lock Bypass Code value",
       			"emailAddress": "Email Address value",
       			"azureADDeviceId": "Azure ADDevice Id value",
       			"deviceRegistrationState": "registered",
       			"deviceCategoryDisplayName": "Device Category Display Name value",
       			"isSupervised": true,
       			"exchangeLastSuccessfulSyncDateTime": "2017-01-01T00:00:45.8803083-08:00",
       			"exchangeAccessState": "unknown",
       			"exchangeAccessStateReason": "unknown",
       			"remoteAssistanceSessionUrl": "https://example.com/remoteAssistanceSessionUrl/",
       			"remoteAssistanceSessionErrorDetails": "Remote Assistance Session Error Details value",
       			"isEncrypted": true,
       			"userPrincipalName": "User Principal Name value",
       			"model": "Model value",
       			"manufacturer": "Manufacturer value",
       			"imei": "Imei value",
       			"complianceGracePeriodExpirationDateTime": "2016-12-31T23:56:44.951111-08:00",
       			"serialNumber": "Serial Number value",
       			"phoneNumber": "Phone Number value",
       			"androidSecurityPatchLevel": "Android Security Patch Level value",
       			"userDisplayName": "User Display Name value",
       			"configurationManagerClientEnabledFeatures": {
       				"@odata.type": "microsoft.graph.configurationManagerClientEnabledFeatures",
       				"inventory": true,
       				"modernApps": true,
       				"resourceAccess": true,
       				"deviceConfiguration": true,
       				"compliancePolicy": true,
       				"windowsUpdateForBusiness": true
       			},
       			"wiFiMacAddress": "Wi Fi Mac Address value",
       			"deviceHealthAttestationState": {
       				"@odata.type": "microsoft.graph.deviceHealthAttestationState",
       				"lastUpdateDateTime": "Last Update Date Time value",
       				"contentNamespaceUrl": "https://example.com/contentNamespaceUrl/",
       				"deviceHealthAttestationStatus": "Device Health Attestation Status value",
       				"contentVersion": "Content Version value",
       				"issuedDateTime": "2016-12-31T23:58:22.1231038-08:00",
       				"attestationIdentityKey": "Attestation Identity Key value",
       				"resetCount": 10,
       				"restartCount": 12,
       				"dataExcutionPolicy": "Data Excution Policy value",
       				"bitLockerStatus": "Bit Locker Status value",
       				"bootManagerVersion": "Boot Manager Version value",
       				"codeIntegrityCheckVersion": "Code Integrity Check Version value",
       				"secureBoot": "Secure Boot value",
       				"bootDebugging": "Boot Debugging value",
       				"operatingSystemKernelDebugging": "Operating System Kernel Debugging value",
       				"codeIntegrity": "Code Integrity value",
       				"testSigning": "Test Signing value",
       				"safeMode": "Safe Mode value",
       				"windowsPE": "Windows PE value",
       				"earlyLaunchAntiMalwareDriverProtection": "Early Launch Anti Malware Driver Protection value",
       				"virtualSecureMode": "Virtual Secure Mode value",
       				"pcrHashAlgorithm": "Pcr Hash Algorithm value",
       				"bootAppSecurityVersion": "Boot App Security Version value",
       				"bootManagerSecurityVersion": "Boot Manager Security Version value",
       				"tpmVersion": "Tpm Version value",
       				"pcr0": "Pcr0 value",
       				"secureBootConfigurationPolicyFingerPrint": "Secure Boot Configuration Policy Finger Print value",
       				"codeIntegrityPolicy": "Code Integrity Policy value",
       				"bootRevisionListInfo": "Boot Revision List Info value",
       				"operatingSystemRevListInfo": "Operating System Rev List Info value",
       				"healthStatusMismatchInfo": "Health Status Mismatch Info value",
       				"healthAttestationSupportedStatus": "Health Attestation Supported Status value"
       			},
       			"subscriberCarrier": "Subscriber Carrier value",
       			"meid": "Meid value",
       			"totalStorageSpaceInBytes": 8,
       			"freeStorageSpaceInBytes": 7,
       			"managedDeviceName": "Managed Device Name value",
       			"partnerReportedThreatState": "activated",
       			"requireUserEnrollmentApproval": true,
       			"managementCertificateExpirationDate": "2016-12-31T23:57:59.9789653-08:00",
       			"iccid": "Iccid value",
       			"udid": "Udid value",
       			"notes": "Notes value",
       			"ethernetMacAddress": "Ethernet Mac Address value",
       			"physicalMemoryInBytes": 5,
       			"enrollmentProfileName": "Enrollment Profile Name value"
       		}
       	]
    }
    """
    return json.loads(data)


@pytest.fixture
def managed_devices(
    device_management: DeviceManagement, managed_devices_data: dict[str, Any]
) -> ManagedDevices:
    # return ManagedDevices(
    #     device_management._client,
    #     ManagedDevice,
    #     data=managed_devices_data,
    #     parent=device_management,
    # )
    managed_devices = device_management.managed_devices
    managed_devices._mdata = {0: managed_devices_data}
    return managed_devices


def test_device_management(
    device_management: DeviceManagement, url: str, check_request_attributes: Callable
) -> None:

    assert device_management.url == f"{url}/deviceManagement"

    check_request_attributes(device_management, _type="query_param")
    check_request_attributes(device_management, _type="method")


def test_managed_devices(
    managed_devices: ManagedDevices,
    url: str,
    managed_devices_data: dict[str, Any],
    check_request_attributes: Callable,
):
    assert managed_devices.url == f"{url}/deviceManagement/managedDevices"

    assert managed_devices.count_fetched_items() == 1
    assert not managed_devices.has_next_items()
    assert managed_devices.current_page == 1
    assert managed_devices._mdata == {0: managed_devices_data}

    check_request_attributes(managed_devices, _type="method", GET=True)
    check_request_attributes(
        managed_devices, _type="query_param", SELECT=True, FILTER=True, ORDERBY=True
    )


def test_managed_device(
    managed_devices: ManagedDevices, url: str, check_request_attributes: Callable
):
    managed_device = managed_devices.by_id("705c034c-034c-705c-4c03-5c704c035c70")
    assert managed_device.id == "705c034c-034c-705c-4c03-5c704c035c70"
    assert managed_device._device_id == "705c034c-034c-705c-4c03-5c704c035c70"
    assert (
        managed_device.url
        == f"{url}/deviceManagement/managedDevices/705c034c-034c-705c-4c03-5c704c035c70"
    )

    managed_device = managed_devices.current_items[0]
    assert managed_device.id == "705c034c-034c-705c-4c03-5c704c035c70"
    assert managed_device._device_id == "705c034c-034c-705c-4c03-5c704c035c70"
    assert (
        managed_device.url
        == f"{url}/deviceManagement/managedDevices/705c034c-034c-705c-4c03-5c704c035c70"
    )

    check_request_attributes(managed_device, _type="method", GET=True)
    check_request_attributes(managed_device, _type="query_param", SELECT=True)
