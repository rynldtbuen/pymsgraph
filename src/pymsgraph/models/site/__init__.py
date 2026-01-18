from __future__ import annotations

from typing import Any, Self, override
from urllib.parse import quote

from pymsgraph.models.common import BaseItem, SharePointIds, SiteCollection
from pymsgraph.models.drive import Drive
from pymsgraph.models.fields import (
    BooleanField,
    CharField,
    Field,
    ListField,
    ModelField,
    QuerySetField,
)
from pymsgraph.models.query import Q, QuerySet

from .list import ListQuerySet


class Site(BaseItem):
    """
    Graph site resource.

    https://learn.microsoft.com/en-us/graph/api/resources/site
    """

    PATH = "/sites"

    display_name = CharField(read_only=True)
    error = Field()
    is_personal_site = BooleanField(read_only=True)

    root = Field()
    sharepoint_ids = ModelField(SharePointIds)
    site_collection = ModelField(SiteCollection)

    # Navigation properties
    analytics = Field()
    columns = ListField()
    content_types = ListField()
    drives = ListField()
    external_columns = ListField()
    items = ListField()
    lists = QuerySetField(ListQuerySet)
    onenote = Field()
    operations = ListField()
    pages = ListField()
    permissions = ListField()
    sites = ListField()
    term_store = Field()
    term_stores = ListField()

    @property
    def drive(self):
        return Drive(client=self._args[0], path=f"{self.path}/drive")

    def __repr__(self) -> str:
        return f"<Site: {self.display_name or self.name}>"


class SiteQuerySet(QuerySet[Site]):
    model_class = Site

    @override
    def search(
        self, *q_objects: "Q", keyword: str | None = None, **kwargs: Any
    ) -> Self:
        qs = self.with_consistency_level_eventual()
        if q_objects or kwargs:
            raise ValueError(
                f"{type(self).__name__} search method does not support Q objects and kwargs."
            )
        if keyword is None:
            raise ValueError(
                f"{type(self).__name__} search method requires a keywork arg."
            )

        qs._params["search"] = keyword
        return qs

    async def get(
        self, id: str | None = None, *, path: str | None = None, **kwargs: Any
    ) -> Site:
        data = None
        if id:
            data = await self._client.get(
                f"{self.path}/{id}", params=self._params, headers=self._headers
            )
        elif path:
            p = (path or "").strip()
            if not p.startswith("/"):
                p = "/" + p
            p_encoded = quote(p, safe="/")
            hostname = await self._get_hostname()
            data = await self._client.get(
                f"{self.path}/{hostname}:{p_encoded}",
                params=self._params,
                headers=self._headers,
            )
        else:
            raise ValueError(
                f"{type(self).__name__} get method requires a id/path argument."
            )

        return self.make_from_graph(data)

    async def _get_hostname(self) -> str:
        """Resolve and cache the SharePoint hostname (e.g. contoso.sharepoint.com)."""

        c = self._client
        hostname = getattr(c, "_sharepoint_hostname", None)
        if hostname is None:
            root = await c.get("/sites/root")
            hostname = (root.get("siteCollection") or {}).get("_sharepoint_hostname")
            if not hostname:
                raise RuntimeError(
                    "Could not discover SharePoint hostname from /sites/root"
                )

            setattr(c, "_sharepoint_hostname", hostname)
        return hostname
