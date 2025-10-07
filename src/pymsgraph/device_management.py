from typing import Any

from .fields import CharField
from .resources import MultiValuedResource, Resource, SingleValuedResource, R


# https://learn.microsoft.com/en-us/graph/api/intune-devices-manageddevice-list?view=graph-rest-1.0


class DeviceManagement(Resource):
    @property
    def relative_url(self) -> str:
        return "/deviceManagement"

    @property
    def managed_devices(self) -> "ManagedDevices":
        return ManagedDevices(self._client, parent=self)


class ManagedDevices(MultiValuedResource["ManagedDevice"]):

    ITEM_CLASS = "ManagedDevice"

    @property
    def relative_url(self):
        return "/managedDevices"

    def by_id(self, device_id: str) -> "ManagedDevice":
        return ManagedDevice(self._client, parent=self, device_id=device_id)


class ManagedDevice(SingleValuedResource):

    id = CharField(fallback="device_id")

    @property
    def relative_url(self) -> str:
        return f"/{self._device_id}"

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        _device_id = kwargs.get("device_id") or self.id
        if _device_id is None:
            raise ValueError(
                "device_id is required by either setting the device_id or data argument"
            )
        self._device_id = _device_id
