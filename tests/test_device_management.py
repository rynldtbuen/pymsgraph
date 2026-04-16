from typing import TYPE_CHECKING

import httpx
import pytest

from pymsgraph.models.device_management import (
    ManagedDevice,
    ManagedDeviceQuerySet,
    WindowsAutoPilotDeviceIdentity,
    WindowsAutoPilotDeviceIdentityQuerySet,
)

if TYPE_CHECKING:
    from .conftest import MakeClient


def test_device_management_managed_devices_queryset(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    client, _ = make_client(handler)
    qs = client.device_management.managed_devices

    assert isinstance(qs, ManagedDeviceQuerySet)
    assert qs.path == "/deviceManagement/managedDevices"
    assert qs._model_class is ManagedDevice


@pytest.mark.asyncio
async def test_device_management_managed_devices_list(
    make_client: "MakeClient",
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/deviceManagement/managedDevices":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "d1",
                            "deviceName": "LAPTOP-001",
                            "operatingSystem": "Windows",
                            "osVersion": "11.0.22631",
                            "userPrincipalName": "alice@contoso.com",
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client, _ = make_client(handler)
    items = [obj async for obj in client.device_management.managed_devices]

    assert len(items) == 1
    assert isinstance(items[0], ManagedDevice)
    assert items[0].id == "d1"
    assert items[0].device_name == "LAPTOP-001"
    assert items[0].operating_system == "Windows"
    assert items[0].user_principal_name == "alice@contoso.com"


@pytest.mark.asyncio
async def test_device_management_managed_devices_maps_extended_fields(
    make_client: "MakeClient",
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/deviceManagement/managedDevices":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "d2",
                            "deviceName": "MOBILE-002",
                            "azureADRegistered": True,
                            "isEncrypted": "true",
                            "operatingSystem": "iOS",
                            "osVersion": "17.4",
                            "lastSyncDateTime": "2026-04-15T21:30:00Z",
                            "freeStorageSpaceInBytes": "1024",
                            "totalStorageSpaceInBytes": 2048,
                            "userPrincipalName": "bob@contoso.com",
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client, _ = make_client(handler)
    items = [obj async for obj in client.device_management.managed_devices]

    assert len(items) == 1
    d = items[0]
    assert d.id == "d2"
    assert d.azure_ad_registered is True
    assert d.is_encrypted is True
    assert d.free_storage_space_in_bytes == 1024
    assert d.total_storage_space_in_bytes == 2048
    assert d.last_sync_date_time is not None
    assert d.user_principal_name == "bob@contoso.com"


@pytest.mark.asyncio
async def test_device_management_managed_devices_get(make_client: "MakeClient") -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1.0/deviceManagement/managedDevices/d1":
            return httpx.Response(
                200,
                json={
                    "id": "d1",
                    "deviceName": "LAPTOP-001",
                    "operatingSystem": "Windows",
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client, _ = make_client(handler)
    device = await client.device_management.managed_devices.get(id="d1")

    assert isinstance(device, ManagedDevice)
    assert device.id == "d1"
    assert device.device_name == "LAPTOP-001"
    assert device.operating_system == "Windows"


def test_device_management_windows_autopilot_device_identities_queryset(
    make_client: "MakeClient",
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": []})

    client, _ = make_client(handler)
    qs = client.device_management.windows_autopilot_device_identities

    assert isinstance(qs, WindowsAutoPilotDeviceIdentityQuerySet)
    assert qs.path == "/deviceManagement/windowsAutopilotDeviceIdentities"
    assert qs._model_class is WindowsAutoPilotDeviceIdentity


@pytest.mark.asyncio
async def test_device_management_windows_autopilot_device_identities_list(
    make_client: "MakeClient",
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "GET"
            and request.url.path
            == "/v1.0/deviceManagement/windowsAutopilotDeviceIdentities"
        ):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "ap1",
                            "serialNumber": "SN-001",
                            "displayName": "Autopilot Device 1",
                            "groupTag": "HQ-Laptops",
                            "enrollmentState": "enrolled",
                            "lastContactedDateTime": "2026-04-16T08:30:00Z",
                            "userPrincipalName": "alice@contoso.com",
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client, _ = make_client(handler)
    items = [
        obj
        async for obj in client.device_management.windows_autopilot_device_identities
    ]

    assert len(items) == 1
    assert isinstance(items[0], WindowsAutoPilotDeviceIdentity)
    assert items[0].id == "ap1"
    assert items[0].serial_number == "SN-001"
    assert items[0].group_tag == "HQ-Laptops"
    assert items[0].enrollment_state == "enrolled"
    assert items[0].last_contacted_date_time is not None
    assert items[0].user_principal_name == "alice@contoso.com"
