import os
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Generic, Self, Type, TypeVar
from unittest.mock import Base

import requests

from .fields import CharField, DateTimeField, DictField, IntegerField
from .resources import MultiValuedResource, R, Resource, SingleValuedResource

if TYPE_CHECKING:
    from pymsgraph import Client


# https://learn.microsoft.com/en-us/graph/api/resources/onedrive?view=graph-rest-1.0
# https://learn.microsoft.com/en-us/graph/api/drive-list?view=graph-rest-1.0&tabs=http


class Drives(Resource):

    @property
    def relative_url(self) -> str:
        return "/drives"

    def by_id(self, drive_id: str) -> "DriveById":
        return DriveById(self._client, parent=self, drive_id=drive_id)


class Drive(SingleValuedResource):
    id = CharField(fallback="drive_id")
    created_date_time = DateTimeField()
    description = CharField()
    drive_type = CharField()
    last_modified_date_time = DateTimeField()
    name = CharField()
    web_url = CharField()


class DriveById(Drive):

    @property
    def relative_url(self) -> str:
        return f"/{self._drive_id}"

    @property
    def items(self) -> "DriveItems":
        return DriveItems(self._client, parent=self)

    @property
    def root(self) -> "RootDriveItem":
        return RootDriveItem(self._client, parent=self)

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        _drive_id = kwargs.get("drive_id") or self.id
        if _drive_id is None:
            raise ValueError(
                "drive_id is required and by setting a drive_id or data argument."
            )
        self._drive_id = _drive_id


class DriveItemChildren(MultiValuedResource["DriveItem"]):
    class RequestMethod(MultiValuedResource.RequestMethod):
        POST = True

    class RequestQueryParam(MultiValuedResource.RequestQueryParam):
        FILTER = False
        TOP = True

    ITEM_CLASS = "DriveItem"

    @property
    def relative_url(self) -> str:
        return self._relative_url

    def _get_obj(
        self, klass: type["DriveItem"], client: "Client", data: dict[str, Any]
    ) -> "DriveItem":
        drive_items = client.drives.by_id(data["parentReference"]["driveId"]).items
        return klass(client, data=data, parent=drive_items)

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        chidren_relative_url = kwargs.get("chidren_relative_url")
        if chidren_relative_url is None:
            raise ValueError("Argument is required, 'chidren_relative_url'")
        self._relative_url = chidren_relative_url


class DriveItems(Resource):

    @property
    def relative_url(self) -> str:
        return "/items"

    def by_id(self, item_id: str) -> "DriveItem":
        return DriveItem(self._client, parent=self, item_id=item_id)


class BaseDriveItem(SingleValuedResource):

    class RequestMethod(SingleValuedResource.RequestMethod):
        PATCH = True

    class RequestQueryParam(SingleValuedResource.RequestQueryParam):
        SEARCH = True

    created_date_time = DateTimeField()
    id = CharField(fallback="item_id")
    last_modified_date_time = DateTimeField()
    name = CharField()
    web_url = CharField()
    size = IntegerField()
    parent_reference = CharField()
    download_url = CharField(to_field="@microsoft.graph.downloadUrl")
    file = DictField()

    @property
    def children(self) -> "DriveItemChildren":
        return DriveItemChildren(
            self._client, parent=self, chidren_relative_url=self.children_relative_url
        )

    @property
    @abstractmethod
    def children_relative_url(self) -> str:
        pass


# https://learn.microsoft.com/en-us/graph/api/driveitem-get?view=graph-rest-1.0&tabs=http
class DriveItem(BaseDriveItem):

    @property
    def children_relative_url(self) -> str:
        return "/children"

    @property
    def content(self) -> "DriveItem.Content":
        return self.Content(self._client, parent=self)

    @property
    def relative_url(self) -> str:
        return f"/{self._item_id}"

    def by_relative_path(self, relative_path: str) -> "DriveItemByRelativePath":
        return DriveItemByRelativePath(
            self._client, parent=self, relative_path=relative_path
        )

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        _item_id = kwargs.get("item_id") or self.id
        if _item_id is None:
            raise ValueError(
                "item_id is required by either setting item_id or data argument"
            )
        self._item_id = _item_id

    def download(self, folder_path: str | None = None) -> "DriveItem":
        content = self.content.get()
        name = self.name
        if name is None:
            raise ValueError("Attribute name must return a str at this point.")
        if folder_path is not None:
            path = os.path.join(folder_path, name)
        else:
            path = name
        with open(path, "wb") as f:
            f.write(content._get_response.content)
        return self

    class Content(SingleValuedResource):
        @property
        def relative_url(self) -> str:
            return f"/content"

        class RequestMethod(BaseDriveItem.RequestMethod):
            PUT = True


class RootDriveItem(BaseDriveItem):

    @property
    def children_relative_url(self):
        return "/children"

    @property
    def relative_url(self) -> str:
        return "/root"

    def by_relative_path(self, relative_path: str) -> "DriveItemByRelativePath":
        return DriveItemByRelativePath(
            self._client, parent=self, relative_path=relative_path
        )

    def upload(self, path: str) -> "RootDriveItem":
        # PUT https://graph.microsoft.com/v1.0/me/drive/root:/FolderA/FileB.txt:/content

        _, filename = os.path.split(path)
        with open(path, "rb") as f:
            content = f.read()
            self.by_relative_path(filename).content.put(content)
        return self


class DriveItemByRelativePath(DriveItem):

    @property
    def children_relative_url(self) -> str:
        return ":/children"

    @property
    def content(self) -> "DriveItemByRelativePath.Content":
        return self.Content(self._client, parent=self)

    @property
    def relative_url(self) -> str:
        return f":/{self._relative_path}"

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        _relative_path = kwargs.get("relative_path")
        if _relative_path is None:
            raise ValueError("Argument is required, relative_path")
        self._relative_path = _relative_path
        self._children_relative_url = ":/chidren"

    def upload(self, path: str) -> "DriveItem":
        # PUT https://graph.microsoft.com/v1.0/me/drive/root:/FolderA/FileB.txt:/content

        _, filename = os.path.split(path)
        with open(path, "rb") as f:
            content = f.read()
            self.by_relative_path(filename).content.put(content)
        return self

    class Content(DriveItem.Content):
        @property
        def relative_url(self) -> str:
            return f":/content"
