from typing import Any

from .drives import Drive, Drives, RootDriveItem
from .fields import CharField, DateTimeField
from .resources import MultiValuedResource, Resource, SingleValuedResource


class Sites(MultiValuedResource["Site"]):
    class RequestQueryParam(MultiValuedResource.RequestQueryParam):
        SEARCH = True
        FILTER = False
        ORDERBY = False

    ITEM_CLASS = "Site"

    @property
    def relative_url(self) -> str:
        return "/sites"

    def __call__(self, hostname: str):
        return SiteByHostname(self._client, parent=self, hostname=hostname)

    @property
    def root(self) -> "SiteRoot":
        return SiteRoot(client=self._client, parent=self)

    def by_id(self, id: str) -> "SiteById":
        return SiteById(self._client, parent=self, site_id=id)

    def get(self) -> MultiValuedResource["Site"]:
        if self._query_params.get("search") is None:
            raise ValueError(
                f"GET method is unsupported without search in query params"
            )

        return super().get()


class BaseLists(MultiValuedResource["BaseList"]):
    ITEM_CLASS = "ListById"

    id = CharField()
    description = CharField()
    name = CharField()
    web_url = CharField()
    display_name = CharField()
    created_date_time = DateTimeField()
    last_modified_date_time = DateTimeField()


class Site(SingleValuedResource):

    class DefaultDrive(Drive):
        @property
        def relative_url(self) -> str:
            return ":/drive"

    class Lists(BaseLists):
        @property
        def relative_url(self) -> str:
            return ":/lists"

        def by_id(self, list_id: str) -> "ListById":
            return ListById(self._client, parent=self, list_id=list_id)

        def by_name(self, name: str) -> "ListByName":
            return ListByName(self._client, parent=self, name=name)

    id = CharField()
    description = CharField()
    name = (CharField(),)
    web_url = CharField()
    display_name = CharField()
    created_date_time = DateTimeField()
    last_modified_date_time = DateTimeField()

    @property
    def drive(self) -> "Site.DefaultDrive":
        return self.DefaultDrive(self._client, parent=self)

    @property
    def lists(self) -> "Site.Lists":
        return self.Lists(self._client, parent=self)


class SiteRoot(Site):

    @property
    def relative_url(self) -> str:
        return "/root"

    def by_relative_path(self, relative_path: str) -> "SiteByRelativePath":
        return SiteByRelativePath(
            self._client, parent=self, relative_path=relative_path
        )


class SiteByHostname(Site):
    @property
    def relative_url(self) -> str:
        return f"/{self._hostname}"

    def by_relative_path(self, relative_path: str) -> "SiteByRelativePath":
        return SiteByRelativePath(
            self._client, parent=self, relative_path=relative_path
        )

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        hostname = kwargs.get("hostname") or self.id
        if hostname is None:
            raise ValueError("Argument is required, 'hostname'")
        self._hostname = hostname


class SiteById(Site):
    class DefaultDrive(Site.DefaultDrive):
        @property
        def relative_url(self) -> str:
            return "/drive"

        @property
        def root(self) -> "RootDriveItem":
            return RootDriveItem(self._client, parent=self)

    class Lists(Site.Lists):
        @property
        def relative_url(self) -> str:
            return "/lists"

    id = CharField(fallback="site_id")

    @property
    def relative_url(self) -> str:
        return f"/{self._site_id}"

    @property
    def drive(self) -> "SiteById.DefaultDrive":
        return self.DefaultDrive(self._client, parent=self)

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        site_id = kwargs.get("site_id") or self.id
        if site_id is None:
            raise ValueError(
                "device_id is required by either setting the device_id or data argument"
            )
        self._site_id = site_id


class SiteByRelativePath(Site):
    # class DefaultDrive(DefaultDrive):
    #     @property
    #     def relative_url(self) -> str:
    #         return ":/drive"

    # class Lists(BaseLists):
    #     @property
    #     def relative_url(self) -> str:
    #         return ":/lists"

    #     def by_name(self, name: str) -> "ListByName":
    #         return ListByName(self._client, parent=self, name=name)

    @property
    def relative_url(self) -> str:
        return f":/{self._relative_path}"

    # @property
    # def drive(self) -> "SiteByRelativePath.DefaultDrive":
    #     return self.DefaultDrive(self._client, parent=self)

    # @property
    # def lists(self) -> "SiteByRelativePath.Lists":
    #     return self.Lists(self._client, parent=self)

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        relative_path = kwargs.get("relative_path")
        if relative_path is None:
            raise ValueError("Argument is required, 'relative_path'")
        self._relative_path = relative_path


class BaseList(SingleValuedResource):

    id = CharField()
    description = CharField()
    name = CharField()
    web_url = CharField()
    display_name = CharField()
    created_date_time = DateTimeField()
    last_modified_date_time = DateTimeField()

    @property
    def items(self) -> "ListItems":
        return ListItems(self._client, parent=self)


class ListById(BaseList):

    @property
    def relative_url(self) -> str:
        return f"/{self._list_id}"

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        list_id = kwargs.get("list_id") or self.id
        if list_id is None:
            raise ValueError("Argument is required, 'list_id'")
        self._list_id = list_id


class ListByName(BaseList):

    @property
    def relative_url(self) -> str:
        return f"/{self._name}"

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        name = kwargs.get("name") or self.name
        if name is None:
            raise ValueError("Argument is required, 'list_id'")
        self._name = name


class ListItems(MultiValuedResource["ListItem"]):
    class RequestMethod(MultiValuedResource.RequestMethod):
        POST = True

    class RequestQueryParam(MultiValuedResource.RequestQueryParam):
        EXPAND = True

    ITEM_CLASS = "ListItem"

    @property
    def relative_url(self) -> str:
        return f"/items"

    def by_id(self, item_id: str) -> "ListItem":
        return ListItem(self._client, parent=self, item_id=item_id)


class ListItem(SingleValuedResource):

    class RequestMethod(SingleValuedResource.RequestMethod):
        DELETE = True

    class RequestQueryParam(SingleValuedResource.RequestQueryParam):
        EXPAND = True

    id = CharField()
    name = CharField()
    created_date_tine = DateTimeField()
    description = DateTimeField()
    eTag = CharField()
    last_modified_date_time = DateTimeField()
    webUrl = CharField()

    @property
    def relative_url(self) -> str:
        return f"/{self._item_id}"

    @property
    def fields(self) -> "ListItemFields":
        return ListItemFields(self._client, parent=self)

    def _set_kwargs(self, kwargs: dict[str, Any]) -> None:
        item_id = kwargs.get("item_id") or self.id
        if item_id is None:
            raise ValueError("Argument is required, 'item_id'")
        self._item_id = item_id


class ListItemFields(Resource):

    class RequestMethod(Resource.RequestMethod):
        PATCH = True
        GET = True

    @property
    def relative_url(self):
        return f"/fields"

    def get(self):
        parent = self._parent
        if parent is not None:
            parent.get()
        return self

    def asdict(self) -> dict[str, Any]:
        self.get()
        return self._data["fields"]
