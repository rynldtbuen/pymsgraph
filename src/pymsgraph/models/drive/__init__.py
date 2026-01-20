from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
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

if TYPE_CHECKING:
    from pymsgraph.client import Client


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
    # root = ModelField("DriveItem", read_only=True)

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
    def root(self):
        return DriveItem(client=self._args[0], path=f"{self.path}/root")

    # @property
    # def items(self) -> "DriveItemsQueryset":
    #     return DriveItemsQueryset(self._args[0], path=f"{self.path}/root/children")

    def by_path(self, path: str):
        p = (path or "").strip()
        if not p.startswith("/"):
            p = "/" + p
        p_encoded = quote(p, safe="/")
        return DriveItem(client=self._args[0], path=f"{self.path}/root:{p_encoded}")


# class DrivePath(ReadOnlyModel, PropertyModel):
#     @property
#     def path(self) -> str:
#         if p := self._args[1]:
#             return p
#         raise AttributeError(f"{type(self).__name__} object has no attribute 'path'")

#     async def get(self) -> Drive:
#         data = await self._client.get(self.path)
#         return Drive.from_graph(data, client=self._client)


async def _get_drive_from_site_known_path(client: "Client", base: str):
    if "HOSTNAME" in base:
        hostname = await client.sites._get_hostname()
        base = base.replace("HOSTNAME", hostname)
    data = await client.get(base)
    drive = Drive.from_graph(data=data, client=client)
    if drive.id is None:
        raise RuntimeError("Unable to resolve drive id from site drive")
    return drive


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
            p = self._args[1]
            if p is None:
                raise AttributeError(
                    f"{type(self).__name__} object has no attribute 'path'"
                )
            return p
        return super().path

    @property
    def items(self) -> DriveItemsQueryset:
        base_path = self.path
        if ":" not in base_path or base_path.endswith("root"):
            path = f"{self.path}/children"
        else:
            path = f"{self.path}:/children"
        return DriveItemsQueryset(self._args[0], path=path)

    def by_path(self, path: str) -> DriveItem:
        p = (path or "").strip()
        if not p.startswith("/"):
            p = "/" + p
        p_encoded = quote(p, safe="/")
        p = self.path
        if "/root:/" in p:
            path = f"{p}{p_encoded}"
        else:
            path = f"{p}:{p_encoded}"
        return DriveItem(client=self._args[0], path=path)

    def by_id(self, id: str) -> DriveItem:
        p = self.path
        if p.endswith("/root"):
            p = f"{p.split('/root')[0]}/items"
        return DriveItem(client=self._args[0], path=p, id=id)

    async def get(self) -> DriveItem:

        p = self.path
        di_p: str | None = None
        if p.startswith("/sites/"):
            if "/root:" in p:
                base, _, tail = p.partition("/root:")
                d = await _get_drive_from_site_known_path(self._client, base)
                di_p = f"{d.path}/items"
                p = f"{d.path}/root:{tail}"
            else:
                raise RuntimeError(f"Unknown path, {p}")
        data = await self._client.get(p)

        return DriveItem.from_graph(data, client=self._client, path=di_p or p)

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

    def make_from_graph(self, data: dict[str, Any]):
        p = self.path
        if p.startswith("/drives"):
            if "/root" in p:
                p = f"{'/'.join(self.path.split("/")[:3])}/items"
            elif "/items" in p:
                p = "/".join(self.path.split("/")[:4])
            else:
                raise RuntimeError(f"Unknown path, {p}")
        elif p.startswith("/users"):
            if "drive/root:" in p:
                p = f"{p.split("/root:")[0]}/items"
            elif "/items" in p:
                p = f"{p.split("/items")[0]}/items"
            elif p.endswith("/root/children"):
                p = f"{p.split("/root/children")[0]}/items"
            else:
                raise RuntimeError(f"Unknown path, {p}")
        else:
            raise RuntimeError(f"Unknown path, {p}")

        return self._model_class.from_graph(data, client=self._client, path=p)

    async def _get_path(self):

        p = self.path
        if p.startswith("/sites/"):
            if p.endswith("/root/children"):
                base = p.split("/root/children")[0]
                d = await _get_drive_from_site_known_path(self._client, base)
                p = d.root.items.path
            elif "/root:" in p:
                base, _, tail = p.partition("/root:")
                d = await _get_drive_from_site_known_path(self._client, base)
                p = f"{d.path}/root:{tail}"
            else:
                raise RuntimeError(f"Unknown path, {p}")
            self._args = self._args[0], p, self._args[2]
        return p
