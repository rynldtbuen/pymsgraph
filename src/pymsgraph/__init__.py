from typing import Any

from msal import ConfidentialClientApplication

from .device_management import DeviceManagement
from .directory_objects import DirectoryObjects
from .drives import Drives
from .groups import Groups
from .sites import Sites
from .users import Users


class Client:

    device_management = DeviceManagement.as_descriptor()
    directory_objects = DirectoryObjects.as_descriptor()
    drives = Drives.as_descriptor()
    groups = Groups.as_descriptor()
    sites = Sites.as_descriptor()
    users = Users.as_descriptor()

    def __init__(
        self,
        client_id: str,
        tenant_id: str,
        client_secret: str,
        scopes: list[str] | None = None,
        _test: bool = False,
    ):
        app: ConfidentialClientApplication | None = None
        if not _test:
            app = ConfidentialClientApplication(
                client_id=client_id,
                client_credential=client_secret,
                authority=f"https://login.microsoftonline.com/{tenant_id}",
            )

        if scopes is None:
            scopes = ["https://graph.microsoft.com/.default"]

        self._scopes = scopes
        self._app = app

    @property
    def _access_token(self) -> str | None:
        if self._app:
            result: dict[str, Any] = (
                self._app.acquire_token_for_client(scopes=self._scopes) or {}
            )
            access_token = result.get("access_token")
            if access_token is None:
                raise ValueError(f"Failed to acquire token, {result}")
            return access_token
        return None

    @property
    def _headers(self) -> dict[str, str]:
        if self._access_token is None:
            return {}
        return {"Authorization": f"Bearer {self._access_token}"}

    @classmethod
    def from_file(cls: type["Client"], fpath: str | None = None, ftype: str = "toml"):
        import tomllib

        if fpath is None:
            fpath = "appcfg.toml"

        with open(fpath, "rb") as f:
            return cls(**tomllib.load(f))
