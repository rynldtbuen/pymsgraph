from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from pymsgraph.models.common import BaseItem, IdentitySet, SharePointIds
from pymsgraph.models.fields import (
    CharField,
    DateTimeField,
    Field,
    IntegerField,
    ListField,
    ModelField,
    QuerySetField,
)
from pymsgraph.models.query import QuerySet
from .workbook import Workbook, WorkbookTable, Worksheet

if TYPE_CHECKING:
    from pymsgraph.client import Client

_logger = logging.getLogger(__name__)


class Drive(BaseItem):
    """
    Graph `drive` resource.

    This model represents a OneDrive/SharePoint document library drive and
    provides helpers for reading the drive and navigating to its root item.

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
        """
        Return the request path for this drive.

        Returns:
                str:
                        `/drives/{id}` for id-bound instances, or the bound constructor path
                        when created from an endpoint like `/users/{id}/drive` or
                        `/sites/{id}/drive`.

        Example:
                ```python
                user = await client.users.get(id="user-id")
                assert user.drive.path == "/users/user-id/drive"
                ```
        """
        if self.id is None and (p := self._args[1]):
            if p.endswith("drive"):
                return p
        return super().path

    # if e := self._args[1]:
    #     if e.endswith("drive"):
    #         return e
    #     if id := self.id:
    #         return f"{e}/{id}"
    # raise AttributeError(f"{type(self).__name__} object has no attribute 'path'")

    @property
    def root(self):
        """
        Return the drive root as a lazy `DriveItem` handle.

        Returns:
                DriveItem:
                        A `DriveItem` bound to `{drive_path}/root`.

        Example:
                ```python
                user = await client.users.get(id="user-id")
                root = user.drive.root
                assert root.path == "/users/user-id/drive/root"
                ```
        """
        return DriveItem(client=self._args[0], path=f"{self.path}/root")

    async def get(self):
        """
        Fetch this drive from Microsoft Graph.

        Returns:
                Drive:
                        A hydrated drive model.

        Notes:
                If `HOSTNAME` is present in the bound path, it is resolved through
                `client.sites._get_hostname()` before sending the request.

        Example:
                ```python
                user = await client.users.get(id="user-id")
                drive = await user.drive.get()
                print(drive.id, drive.name)
                ```
        """
        p = self.path
        c = self._client
        if "HOSTNAME" in p:
            hostname = await c.sites._get_hostname()
            p = p.replace("HOSTNAME", hostname)
        _logger.debug("Drive.get path=%s", p)
        data = await c.get(p)
        return Drive.from_graph(data=data, client=c)

    @classmethod
    async def from_path(cls, client: Client, path: str) -> Drive:
        """
        Resolve and fetch a drive from an arbitrary drive endpoint path.

        Args:
                client:
                        Bound Graph client.
                path:
                        Drive endpoint path, such as `/users/{id}/drive` or
                        `/sites/{hostname}:/sites/{site-name}:/drive`.

        Returns:
                Drive:
                        Hydrated drive model from the response payload.

        Notes:
                `HOSTNAME` placeholders are resolved automatically.

        Example:
                ```python
                drive = await Drive.from_path(
                        client,
                        "/sites/HOSTNAME:/sites/ProjectA:/drive",
                )
                ```
        """
        if "HOSTNAME" in path:
            hostname = await client.sites._get_hostname()
            path = path.replace("HOSTNAME", hostname)
        _logger.debug("Drive.from_path path=%s", path)
        data = await client.get(path)
        return Drive.from_graph(data=data, client=client)


class DriveQuerySetProxy:
    def __init__(self, client: Client) -> None:
        self._client = client


class ItemActivity(BaseItem):
    """
    Graph `itemActivity` resource.

    Exposes activity events associated with a drive item.

    https://learn.microsoft.com/en-us/graph/api/resources/itemactivity?view=graph-rest-1.0
    """

    PATH = "/activities"

    access = Field()
    activity_date_time = DateTimeField()
    actor = Field()
    drive_item = Field()
    list_item = Field()
    times = Field()

    def __repr__(self) -> str:
        return f"<ItemActivity: {self.id}>"


class ItemActivityQuerySet(QuerySet[ItemActivity]):
    """
    QuerySet for drive item activities (`.../items/{id}/activities`).
    """

    model_class = ItemActivity


class DriveItem(BaseItem):
    """
    Graph `driveItem` resource.

    This model is used for files/folders and path/id navigation under drives.
    Helpers are provided for child enumeration, id/path lookup, upload, download,
    copy, and move operations.

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
    activities = QuerySetField(ItemActivityQuerySet, order_by=True)
    workbook = ModelField(Workbook, is_proxy=True)

    def __repr__(self) -> str:
        return f"<DriveItem: {self.name or self.id}>"

    @property
    def path(self) -> str:
        """
        Return the request path for this drive item.

        Returns:
                str:
                        Id-based path (`.../items/{id}`) when `id` is present, otherwise the
                        bound path (useful for root/path-based handles).

        Example:
                ```python
                root = (await client.users.get(id="user-id")).drive.root
                report = root.by_path("/Reports/2024.xlsx")
                assert report.path == "/users/user-id/drive/root:/Reports/2024.xlsx"
                ```
        """
        if self.id is None and (p := self._args[1]):
            return p
        return super().path

    # p: str = self._args[1] or ""
    # if ":" in p:
    #     return p
    # return super().path

    @property
    def items(self) -> DriveItemsQueryset:
        """
        Return a queryset for direct children of this drive item.

        Returns:
                DriveItemsQueryset:
                        Child collection queryset with correctly normalized children path.

        Notes:
                - For id-based paths, `/children` is appended.
                - For colon paths (`...:/folder`), `:/children` is appended.

        Example:
                ```python
                folder = (await client.users.get(id="user-id")).drive.root.by_path("/Reports")
                children = [item async for item in folder.items]
                ```
        """
        base_path = self.path
        # id-based paths (no ":"), and /root should use /children
        # e.g. /drives/{id}/root or /users/{id}/drive/root
        if ":" not in base_path or base_path.endswith("root"):
            path = f"{self.path}/children"
        else:
            # colon-based paths need :/children suffix
            # e.g. /drives/{id}/root:/folder -> /drives/{id}/root:/folder:/children
            path = f"{self.path}:/children"
        _logger.debug("DriveItem.items base_path=%s path=%s", base_path, path)
        return DriveItemsQueryset(self._args[0], path=path)

    def by_path(self, path: str) -> DriveItem:
        """
        Return a lazy drive item handle addressed by relative path.

        Args:
                path:
                        Relative child path from this item. Leading slash is optional.

        Returns:
                DriveItem:
                        A new lazy `DriveItem` bound to a Graph path-based endpoint.

        Notes:
                Path segments are URL-encoded while preserving `/` separators.

        Example:
                ```python
                item = (await client.users.get(id="user-id")).drive.root.by_path(
                        "/Reports/2024.xlsx"
                )
                file_item = await item.get()
                ```
        """
        orig_path = path
        p = (path or "").strip()
        # normalize leading slash for relative paths
        if not p.startswith("/"):
            p = "/" + p
        # encode path segments but keep "/" separators
        p_encoded = quote(p, safe="/")
        p = self.path
        # if already rooted at /root:/, append directly
        if "/root:/" in p:
            path = f"{p}{p_encoded}"
        else:
            # otherwise, build /{item-id}:/path
            path = f"{p}:{p_encoded}"
        _logger.debug(
            "DriveItem.by_path base=%s input=%s normalized=%s result=%s",
            self.path,
            orig_path,
            p_encoded,
            path,
        )
        return DriveItem(client=self._args[0], path=path)

    def by_id(self, id: str) -> DriveItem:
        """
        Return a lazy child handle by drive item id.

        Args:
                id:
                        Drive item id.

        Returns:
                DriveItem:
                        A `DriveItem` bound to an id-based `/items/{id}` endpoint.

        Notes:
                If current path is root-based (`.../root`), it is normalized to
                `.../items` before attaching the id.

        Example:
                ```python
                item = (await client.users.get(id="user-id")).drive.root.by_id("item-id")
                file_item = await item.get()
                ```
        """
        p = self.path
        # /drives/{drive-id}/root -> /drives/{drive-id}/items
        # /users/{user-id}/drive/root -> /users/{user-id}/drive/items
        if p.endswith("/root"):
            p = f"{p.split('/root')[0]}/items"
        _logger.debug("DriveItem.by_id base_path=%s id=%s path=%s", self.path, id, p)
        return DriveItem(client=self._args[0], path=p, id=id)

    async def get(self) -> DriveItem:
        """
        Fetch this drive item from Graph and return a hydrated model.

        Returns:
                DriveItem:
                        Hydrated drive item.

        Raises:
                RuntimeError:
                        If a `/sites/...` path shape is not supported by the resolver.

        Notes:
                When called with site-root path syntax (`/sites/.../drive/root:/...`),
                the method resolves the site drive first and then fetches the item from
                an equivalent `/drives/{drive-id}/root:/...` endpoint.

        Example:
                ```python
                item = (await client.users.get(id="user-id")).drive.root.by_path(
                        "/Shared/report.xlsx"
                )
                obj = await item.get()
                print(obj.id, obj.name)
                ```
        """
        p = self.path
        di_p: str | None = None
        if p.startswith("/sites/"):
            # /sites/{hostname}:/path:/drive/root:/folder[:/children]
            if "/root:" in p:
                # resolve site drive, then rebase to /drives/{id}/root:/path
                base, _, tail = p.partition("/root:")
                d = await Drive.from_path(self._client, base)
                # store /drives/{id}/items so DriveItem paths are id-based
                di_p = f"{d.path}/items"
                p = f"{d.path}/root:{tail}"
            else:
                raise RuntimeError(f"Unknown path, {p}")
        elif p.startswith("/users/") and "/drive/root" in p:
            # Rebase path-based/root-based user drive items to /drive/items
            di_p = f"{p.split('/root', 1)[0]}/items"
        elif p.startswith("/users/") and "/drive/items/" in p and ":" in p:
            # Rebase user drive id+path items to /drive/items
            di_p = f"{p.split('/items/', 1)[0]}/items"
        elif p.startswith("/drives/") and "/root" in p:
            # Rebase path-based/root-based drive items to /drives/{id}/items
            di_p = f"{'/'.join(p.split('/')[:3])}/items"
        elif p.startswith("/drives/") and "/items/" in p and ":" in p:
            # Rebase drive id+path items to /drives/{id}/items
            di_p = f"{'/'.join(p.split('/')[:3])}/items"
        _logger.debug("DriveItem.get request_path=%s model_path=%s", p, di_p or p)
        data = await self._client.get(p)

        return DriveItem.from_graph(data, client=self._client, path=di_p or p)

    async def _get_path(self) -> str:
        """
        Resolve a path-based DriveItem (e.g. /sites/.../drive/root:/path)
        to an id-based DriveItem (/drives/{drive-id}/items/{item-id}).

        Returns:
                str:
                        Resolved id-based path when resolution succeeds, otherwise the
                        normalized original path.

        Notes:
                This method also caches resolved graph payload/path on the current
                instance so subsequent operations can reuse id-based endpoints.
        """
        p = self.path
        c = self._client
        resolved: DriveItem | None = None
        _logger.debug("DriveItem._get_path start=%s", p)

        if "HOSTNAME" in p:
            hostname = await c.sites._get_hostname()
            p = p.replace("HOSTNAME", hostname)
            _logger.debug("DriveItem._get_path hostname_resolved=%s", p)

        # Normalize children suffixes to resolve the parent item.
        if p.endswith(":/children"):
            p = p[: -len(":/children")]
        elif p.endswith("/children"):
            p = p[: -len("/children")]
        _logger.debug("DriveItem._get_path normalized_children=%s", p)

        if "/drive/root" in p and (p.startswith("/sites/") or p.startswith("/users/")):
            base = f"{p.split('/drive/root', 1)[0]}/drive"
            drive = await Drive.from_path(c, base)
            if "/drive/root:" in p:
                tail = p.split("/drive/root:", 1)[1]
                p = f"{drive.path}/root:{tail}"
            else:
                p = f"{drive.path}/root"
            data = await c.get(p)
            resolved = DriveItem.from_graph(data, client=c, path=f"{drive.path}/items")
            _logger.debug(
                "DriveItem._get_path resolved_from_site drive=%s resolved_path=%s",
                drive.path,
                resolved.path,
            )

        if p.startswith("/drives/") and "/root" in p:
            base = "/".join(p.split("/")[:3])
            if "/root:" in p:
                tail = p.split("/root:", 1)[1]
                p = f"{base}/root:{tail}"
            else:
                p = f"{base}/root"
            data = await c.get(p)
            resolved = DriveItem.from_graph(data, client=c, path=f"{base}/items")
            _logger.debug(
                "DriveItem._get_path resolved_from_drive base=%s resolved_path=%s",
                base,
                resolved.path,
            )

        if resolved is not None:
            self._data = resolved._data
            self._graph_data = resolved._graph_data
            try:
                self._dirty.clear()
            except AttributeError:
                self._dirty = set()
            self._args = (self._args[0], resolved._args[1])
            _logger.debug("DriveItem._get_path cached=%s", self.path)
            return self.path

        _logger.debug("DriveItem._get_path passthrough=%s", p)
        return p

    async def upload(
        self,
        name: str | None = None,
        content: bytes | str | None = None,
        *,
        file_path: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> "DriveItem":
        """
        Upload a file into this folder using Graph simple upload.

        Args:
                name:
                        Target file name. Required when using raw `content`.
                content:
                        File payload as bytes/string.
                file_path:
                        Local file path to read and upload. When provided and `name` is
                        `None`, the filename from disk is used.
                content_type:
                        HTTP `Content-Type` header sent with the upload request.

        Returns:
                DriveItem:
                        Newly uploaded file item.

        Raises:
                FileNotFoundError:
                        If `file_path` does not exist.
                ValueError:
                        If neither `content` nor `file_path` is provided, or if `name` is
                        missing while using raw `content`.

        Example:
                ```python
                folder = user.drive.root.by_path("/Reports")
                uploaded = await folder.upload("report.csv", b"col1,col2\n1,2\n")
                ```
        """

        # if not getattr(self, "folder", None):
        #     raise ValueError("Parent drive item is not a folder")

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

        path = f"{await self._get_path()}:/{name}:/content"
        _logger.debug(
            "DriveItem.upload path=%s name=%s content_type=%s from_file=%s",
            path,
            name,
            content_type,
            file_path is not None,
        )
        data = await self._client.put(
            path,
            content=content,
            headers={"Content-Type": content_type},
        )
        return self.__class__(graph_data=data, parent=self)

    async def download(self, dest_path: str | Path | None = None) -> bytes:
        """
        Download this drive item's file content.

        Args:
                dest_path:
                        Optional destination file path. When provided, downloaded bytes are
                        also written to disk.

        Returns:
                bytes:
                        Downloaded file bytes.

        Example:
                ```python
                data = await item.download(dest_path="report.csv")
                ```
        """
        _logger.debug(
            "DriveItem.download item_path=%s dest_path=%s", self.path, dest_path
        )
        data = await self._client.get_content(
            f"{await self._get_path()}/content", headers={}
        )
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
        Copy this drive item, optionally into another folder/drive.

        Args:
                name:
                        Optional new name for the copied item.
                parent_id:
                        Destination parent folder id.
                drive_id:
                        Destination drive id.
                parent_item:
                        Optional destination folder model. If provided, `id` and
                        `parent_reference.driveId` are used as defaults.

        Returns:
                DriveItem:
                        Model created from the copy operation response payload.

        Example:
                ```python
                copied = await item.copy(name="Q4-copy.xlsx", parent_id="dest-folder-id")
                ```
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

        _logger.debug("DriveItem.copy path=%s body=%s", self.path, body)
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
        """
        Move (re-parent/rename) this drive item.

        Args:
                name:
                        Optional new name after move.
                parent_id:
                        Destination parent folder id.
                drive_id:
                        Destination drive id.
                parent_item:
                        Optional destination folder model. If provided, `id` and
                        `parent_reference.driveId` are used as defaults.

        Returns:
                DriveItem:
                        Updated drive item returned by Graph.

        Example:
                ```python
                moved = await item.move(parent_id="archive-folder-id")
                ```
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

        _logger.debug("DriveItem.move path=%s body=%s", self.path, body)
        data = await self._client.patch(self.path, body=body)
        return self.__class__(graph_data=data, client=self._client)


class DriveItemsQueryset(QuerySet[DriveItem]):
    """
    QuerySet for drive item collections.

    This queryset normalizes Graph path variants (`/drives/...`, `/users/.../drive`,
    `/sites/.../drive`) so child items are hydrated with stable id-based paths.

    Example:
            ```python
            root_items = (await client.users.get(id="user-id")).drive.root.items
            files = [obj async for obj in root_items.filter(file__exists=True)]
            ```
    """

    model_class = DriveItem

    def make_from_graph(self, data: dict[str, Any]):
        """
        Build a `DriveItem` model from response data with normalized base path.

        Args:
                data:
                        Raw Graph item payload.

        Returns:
                DriveItem:
                        Hydrated item using an id-friendly base path.

        Raises:
                RuntimeError:
                        If the queryset path shape is unsupported.
        """
        p = self.path
        if p.startswith("/drives"):
            # /drives/{drive-id}/root[/children]
            # /drives/{drive-id}/root:/path[:/children]
            if "/root" in p:
                # normalize to /drives/{drive-id}/items so child DriveItem uses id-based path
                p = f"{'/'.join(self.path.split("/")[:3])}/items"
            # /drives/{drive-id}/items/{item-id}[/children]
            elif "/items" in p:
                # keep /drives/{drive-id}/items as the base for DriveItem paths
                p = "/".join(self.path.split("/")[:4])
            else:
                raise RuntimeError(f"Unknown path, {p}")
        elif p.startswith("/users"):
            # /users/{user-id}/drive/root:/path[:/children]
            if "drive/root:" in p:
                # normalize to /users/{user-id}/drive/items
                p = f"{p.split("/root:")[0]}/items"
            # /users/{user-id}/drive/items/{item-id}[/children]
            elif "/items" in p:
                # keep /users/{user-id}/drive/items as the base for DriveItem paths
                p = f"{p.split("/items")[0]}/items"
            # /users/{user-id}/drive/root/children
            elif p.endswith("/root/children"):
                # normalize to /users/{user-id}/drive/items
                p = f"{p.split("/root/children")[0]}/items"
            else:
                raise RuntimeError(f"Unknown path, {p}")
        else:
            raise RuntimeError(f"Unknown path, {p}")

        _logger.debug(
            "DriveItemsQueryset.make_from_graph source_path=%s normalized_path=%s",
            self.path,
            p,
        )
        return self._model_class.from_graph(data, client=self._client, path=p)

    async def _get_path(self):
        """
        Resolve site-based collection paths to drive-id-based endpoints.

        Returns:
                str:
                        Resolved request path for Graph calls.

        Raises:
                RuntimeError:
                        If the site path shape is unsupported.

        Notes:
                Resolved paths are cached into queryset args for subsequent requests.
        """
        p = self.path
        if p.startswith("/sites/"):
            c = self._client
            # /sites/{hostname}:/path:/drive/root/children
            if p.endswith("/root/children"):
                # resolve site drive, then use /drives/{id}/root/children
                base = p.split("/root/children")[0]
                d = await Drive.from_path(c, base)
                p = d.root.items.path
            # /sites/{hostname}:/path:/drive/root:/folder[:/children]
            elif "/root:" in p:
                # resolve site drive, then rebase to /drives/{id}/root:/path
                base, _, tail = p.partition("/root:")
                d = await Drive.from_path(c, base)
                p = f"{d.path}/root:{tail}"
            else:
                raise RuntimeError(f"Unknown path, {p}")
            # cache resolved path for subsequent calls
            self._args = c, p, self._args[2]
            _logger.debug("DriveItemsQueryset._get_path resolved=%s", p)
        else:
            _logger.debug("DriveItemsQueryset._get_path passthrough=%s", p)
        return p
