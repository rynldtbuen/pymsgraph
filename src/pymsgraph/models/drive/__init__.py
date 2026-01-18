from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from pymsgraph.models.common import BaseItem, IdentitySet, SharePointIds
from pymsgraph.models.fields import (
    CharField,
    Field,
    IntegerField,
    ListField,
    ModelField,
)
from pymsgraph.models.query import QuerySet


class Drive(BaseItem):
    """
    Graph drive resource.

    https://learn.microsoft.com/en-us/graph/api/resources/drive?view=graph-rest-1.0
    """

    PATH = "/drives"

    drive_type = CharField()
    owner = ModelField(IdentitySet)
    quota = Field()
    system = Field()
    root = ModelField("DriveItem", read_only=True)

    def __repr__(self) -> str:
        return f"<Drive: {self.name or self.id}>"

    @property
    def path(self) -> str:
        if e := self._args[1]:
            if e.endswith("drive"):
                return e
            if id := self.id:
                return f"{e}/{id}"
        raise AttributeError(f"{type(self).__name__} object has no attribute 'path'")

    @property
    def items(self) -> "DriveItemsQueryset":
        return DriveItemsQueryset(self._args[0], path=f"{self.path}/root/children")


class DriveItem(BaseItem):
    """
    Graph driveItem resource.

    https://learn.microsoft.com/en-us/graph/api/resources/driveitem?view=graph-rest-1.0
    """

    PATH = "/items"

    # Properties
    audio = Field()
    bundle = Field()
    c_tag = CharField(graph_attr_name="cTag")
    content = Field()
    deleted = Field()
    file = Field()
    file_system_info = Field()
    folder = Field()
    image = Field()
    location = Field()
    malware = Field()
    package = Field()
    pending_operations = Field()
    photo = Field()
    publication = Field()
    remote_item = Field()
    root = Field()
    search_result = Field()
    shared = Field()
    sharepoint_ids = ModelField(
        SharePointIds,
    )
    size = IntegerField()
    special_folder = Field()
    video = Field()
    web_dav_url = CharField()

    # Navigation properties
    analytics = Field()
    list_item = Field()
    permissions = ListField()
    retention_label = Field()
    subscriptions = ListField()
    thumbnails = ListField()
    versions = ListField()
    workbook = Field()

    def __repr__(self) -> str:
        return f"<DriveItem: {self.name or self.id}>"

    @property
    def path(self) -> str:
        if self.id is None:
            if self._args[1] is None:
                raise AttributeError(
                    f"{type(self).__name__} object has no attribute 'path'"
                )
            return self._args[1]
        return super().path

    @property
    def items(self) -> DriveItemsQueryset:
        base_path = self.path
        if ":" not in base_path:
            path = f"{self.path}/children"
        else:
            path = f"{self.path}:/children"
        return DriveItemsQueryset(self._args[0], path=path)

    def with_path(self, path: str) -> DriveItem:
        if self.id is None:
            raise ValueError("id is required when accessing known path on this object.")
        p = (path or "").strip()
        if not p.startswith("/"):
            p = "/" + p
        p_encoded = quote(p, safe="/")
        return DriveItem(client=self._args[0], path=f"{self.path}:{p_encoded}")

    async def upload(
        self,
        name: str | None = None,
        content: bytes | str | None = None,
        *,
        file_path: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> "DriveItem":
        """
        Upload a new file into this folder DriveItem using simple upload.

        You can supply raw `content` or a `file_path`. If `file_path` is provided,
        it will be read from disk and the filename will be used when `name` is not
        supplied.
        """
        if not getattr(self, "folder", None):
            raise ValueError("Parent drive item is not a folder")

        if file_path is not None:
            path_obj = Path(file_path)
            if not path_obj.is_file():
                raise FileNotFoundError(f"No such file: {file_path}")
            if name is None:
                name = path_obj.name
            content = path_obj.read_bytes()

        if content is None:
            raise ValueError("upload requires either content= or file_path=")
        if name is None:
            raise ValueError("name is required when using raw content")

        path = f"{self.path}:/{name}:/content"
        data = await self._client.put(
            path,
            content=content,
            headers={"Content-Type": content_type},
        )
        return self.__class__(graph_data=data, parent=self)

    async def download(self, dest_path: str | Path | None = None) -> bytes:
        """
        Download this drive item content. If `dest_path` is provided, write to disk.
        """
        data = await self._client.get_content(f"{self.path}/content", headers={})
        if dest_path is not None:
            p = Path(dest_path)
            p.write_bytes(data)
        return data

    async def copy(
        self,
        *,
        name: str | None = None,
        parent_id: str | None = None,
        drive_id: str | None = None,
        parent_item: "DriveItem | None" = None,
    ) -> "DriveItem":
        """
        Copy this drive item. Optionally supply a target parent folder (by id/drive)
        or a DriveItem instance whose id/drive will be used.
        """
        body: dict[str, Any] = {}
        if name:
            body["name"] = name

        if parent_item:
            parent_id = parent_id or getattr(parent_item, "id", None)
            # best-effort: parent_reference may contain driveId
            pr = getattr(parent_item, "parent_reference", {}) or {}
            drive_id = drive_id or pr.get("driveId")

        if parent_id or drive_id:
            ref: dict[str, Any] = {}
            if parent_id:
                ref["id"] = parent_id
            if drive_id:
                ref["driveId"] = drive_id
            body["parentReference"] = ref

        data = await self._client.post(f"{self.path}/copy", body=body)
        return self.__class__(graph_data=data, client=self._client)

    async def move(
        self,
        *,
        name: str | None = None,
        parent_id: str | None = None,
        drive_id: str | None = None,
        parent_item: "DriveItem | None" = None,
    ) -> "DriveItem":
        body: dict[str, Any] = {}
        if name:
            body["name"] = name

        if parent_item:
            parent_id = parent_id or getattr(parent_item, "id", None)
            pr = getattr(parent_item, "parent_reference", {}) or {}
            drive_id = drive_id or pr.get("driveId")

        if parent_id or drive_id:
            ref: dict[str, Any] = {}
            if parent_id:
                ref["id"] = parent_id
            if drive_id:
                ref["driveId"] = drive_id
            body["parentReference"] = ref

        data = await self._client.patch(self.path, body=body)
        return self.__class__(graph_data=data, client=self._client)


class DriveItemsQueryset(QuerySet[DriveItem]):
    model_class = DriveItem

    def with_path(self, path: str) -> DriveItem:
        base_path = self.path
        if base_path.endswith(":/children"):
            raise ValueError("Can't no longer build a path by chaining known paths.")
        if "/children" in base_path:
            base_path = "/".join(base_path.split("/")[:-1])
        p = (path or "").strip()
        if not p.startswith("/"):
            p = "/" + p
        p_encoded = quote(p, safe="/")
        return DriveItem(client=self._args[0], path=f"{base_path}:{p_encoded}")

    def with_id(self, id: str) -> DriveItem:
        base_path = self.path
        if base_path.endswith(":/children"):
            raise ValueError("Can't no longer build a path by chaining known paths.")
        if ":" in base_path:
            raise ValueError("Can't no longer build a path by chaining known paths.")
        if "/children" in base_path:
            base_path = "/".join(base_path.split("/")[:-2])
        if "items" not in base_path:
            path = f"{base_path}/items"
        else:
            path = base_path
        return DriveItem(client=self._args[0], path=path, id=id)
