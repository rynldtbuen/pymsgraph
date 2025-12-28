from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from pymsgraph.fields import CharField, DateTimeField, Field
from pymsgraph.models.base import Model
from pymsgraph.query import Capabilities, QuerySet

__all__ = ["Drive", "DriveQuerySet", "DriveItem", "DriveItemQuerySet"]


class Drive(Model):
    """
    Graph drive resource.

    https://learn.microsoft.com/en-us/graph/api/resources/drive?view=graph-rest-1.0
    """

    drive_type = CharField(read_only=True)
    name = CharField(read_only=True)
    web_url = CharField(read_only=True)
    description = CharField(read_only=True)
    owner = Field(read_only=True)
    quota = Field(read_only=True)
    last_modified_date_time = DateTimeField(read_only=True)
    created_date_time = DateTimeField(read_only=True)
    system = Field(read_only=True)
    # root = Field(read_only=True)

    is_read_only = True
    endpoint = "/drives"

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Drive: {self.name or self.id}>"

    @property
    def items(self) -> "DriveItemQuerySet":
        return DriveItemQuerySet(parent=self)


class DriveQuerySet(QuerySet[Drive]):
    model_class = Drive
    capabilities = Capabilities.read_only(get=True)


class DriveItem(Model):
    """
    Graph driveItem resource.

    https://learn.microsoft.com/en-us/graph/api/resources/driveitem?view=graph-rest-1.0
    """

    name = CharField(read_only=True)
    web_url = CharField(read_only=True)
    size = Field(read_only=True)
    file = Field(read_only=True)
    folder = Field(read_only=True)
    parent_reference = Field(read_only=True)
    last_modified_date_time = DateTimeField(read_only=True)
    created_date_time = DateTimeField(read_only=True)

    is_read_only = True
    endpoint = "/items"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DriveItem: {self.name or self.id}>"

    @property
    def children(self) -> DriveItemChildrenQuerySet:
        return DriveItemChildrenQuerySet(parent=self)

    def upload(
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

        path = f"{self.endpoint}:/{name}:/content"
        data = self._client.put(
            path,
            content=content,
            headers={"Content-Type": content_type},
        )
        return self.__class__(graph_data=data, parent=self)

    def download(self, dest_path: str | Path | None = None) -> bytes:
        """
        Download this drive item content. If `dest_path` is provided, write to disk.
        """
        data = self._client.get_content(f"{self.endpoint}/content", headers={})
        if dest_path is not None:
            p = Path(dest_path)
            p.write_bytes(data)
        return data

    def copy(
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

        data = self._client.post(f"{self.endpoint}/copy", json_body=body)
        return self.__class__(graph_data=data, parent=self)

    def move(
        self,
        *,
        name: str | None = None,
        parent_id: str | None = None,
        drive_id: str | None = None,
        parent_item: "DriveItem | None" = None,
    ) -> "DriveItem":
        """
        Move this drive item to another parent (and optionally rename).

        Graph uses PATCH on the item endpoint with a parentReference payload.
        """
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

        data = self._client.patch(self.endpoint, json_body=body)
        return self.__class__(graph_data=data, parent=self)


class DriveItemQuerySet(QuerySet[DriveItem]):
    model_class = DriveItem
    capabilities = Capabilities.read_only(get=True)

    def get(
        self, *, id: str | None = None, path: str | None = None, **lookups: Any
    ) -> DriveItem:
        if id:
            data = self._client.get(
                f"{self.endpoint}/{id}", params=self._params, headers=self._headers
            )
            if data:
                return self.model_class(graph_data=data, parent=self)
            raise RuntimeError(f"No resource ({self.model_class.__name__}) found, {id}")
        if path:
            p = (path or "").strip()
            if not p.startswith("/"):
                p = "/" + p
            p_encoded = quote(p, safe="/")
            parent = self._parent
            assert parent is not None
            parent_ep = parent.endpoint
            data = self._client.get(
                f"{parent_ep}/root:{p_encoded}",
                params=self._params,
                headers=self._headers,
            )
            return self.model_class(graph_data=data, parent=self)
        if not lookups:
            raise ValueError(f"{type(self)}.get requires id= or filters")
        objs = list(self.filter(**lookups).top(2))
        if not objs:
            raise RuntimeError(f"No resource ({self.model_class.__name__}) found, {id}")
        if len(objs) > 1:
            raise RuntimeError(
                f"Multiple resources found. Use filter method instead, {lookups} "
            )
        return objs[0]


class DriveItemChildrenQuerySet(DriveItemQuerySet):
    endpoint = "/children"

    def create_folder(
        self, name: str, *, conflict_behavior: str | None = None
    ) -> DriveItem:
        """
        Create a child folder under the parent DriveItem (which must be a folder).
        Uses POST {parent}/children with a folder facet.
        """
        parent = getattr(self, "_parent", None)
        if parent is None:
            raise ValueError("DriveItemChildrenQuerySet requires a parent DriveItem")
        if not getattr(parent, "folder", None):
            raise ValueError("Parent drive item is not a folder")

        body: dict[str, Any] = {"name": name, "folder": {}}
        if conflict_behavior:
            body["@microsoft.graph.conflictBehavior"] = conflict_behavior

        data = self._client.post(self.endpoint, json_body=body)
        return self.model_class(graph_data=data, parent=self)
