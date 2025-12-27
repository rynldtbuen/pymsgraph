from __future__ import annotations

from typing import Any

from pymsgraph.fields import BooleanField, CharField, DateTimeField
from pymsgraph.models.base import Model
from pymsgraph.query import Capabilities, QuerySet
from .list import ListQuerySet

__all__ = ["Site", "SiteQuerySet", "ListQuerySet"]


class Site(Model):
    """
    Graph site resource type.
    """

    display_name = CharField(read_only=True)
    name = CharField()
    description = CharField()
    etag = CharField(read_only=True)
    is_personal_site = BooleanField(read_only=True)
    created_date_time = DateTimeField(read_only=True)
    last_modified_date_time = DateTimeField(read_only=True)
    web_url = CharField(read_only=True)

    # Complex properties (dicts)
    # root = Field()  # root
    # sharepoint_ids = Field()  # sharepointIds
    # site_collection = Field()  # siteCollection

    is_read_only = True
    endpoint = "/sites"
    search_field = "display_name"

    @property
    def lists(self) -> ListQuerySet:
        return ListQuerySet(parent=self)

    def __repr__(self) -> str:
        return f"<Site: {self.display_name or self.name}>"


class SiteQuerySet(QuerySet[Site]):
    model_class = Site
    capabilities = Capabilities.read_only(search=True)

    def search(self, keyword: str) -> "QuerySet[Site]":
        self._params["search"] = f'"{keyword}"'
        self._headers.setdefault("ConsistencyLevel", "eventual")
        return self._make_clone()

    def get(
        self,
        *,
        id: str | None = None,
        path: str | None = None,
        **lookups: Any,
    ) -> Site:
        # Enforce only id= or path=
        if (id is None and path is None) or (id is not None and path is not None):
            raise ValueError("Provide exactly one of id= or path=")

        if id:
            data = self._client.get(
                f"{self.endpoint}/{id}", params=self._params, headers=self._headers
            )
        else:
            # path resolution: /sites/{hostname}:{server-relative-path}
            p = (path or "").strip()
            if not p.startswith("/"):
                p = "/" + p
            data = self._client.get(
                f"{self.endpoint}/{self._get_hostname()}:{p}",
                params=self._params,
                headers=self._headers,
            )

        return self.model_class(graph_data=data, parent=self)

    def _get_hostname(self) -> str:
        """Resolve and cache the SharePoint hostname (e.g. contoso.sharepoint.com)."""

        client = self._client
        hostname = getattr(client, "_sharepoint_hostname", None)
        if hostname is None:
            root = client.get("/sites/root")
            hostname = (root.get("siteCollection") or {}).get("_sharepoint_hostname")
            if not hostname:
                raise RuntimeError(
                    "Could not discover SharePoint hostname from /sites/root"
                )

            setattr(
                client, "_sharepoint_hostname", hostname
            )  # cache on client instance
        return hostname
