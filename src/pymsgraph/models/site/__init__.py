from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, override
from urllib.parse import quote

from pymsgraph.models.common import BaseItem, SharePointIds, SiteCollection
from pymsgraph.models.drive import Drive
from pymsgraph.models.fields import (
    BooleanField,
    CharField,
    Field,
    ListField,
    ModelField,
)
from pymsgraph.models.query import Q, QuerySet

from .list import ListQuerySet

if TYPE_CHECKING:
    from pymsgraph.client import Client

_logger = logging.getLogger(__name__)


class Site(BaseItem):
    """
    Graph SharePoint site resource.

    Reference:
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
    onenote = Field()
    operations = ListField()
    pages = ListField()
    permissions = ListField()
    sites = ListField()
    term_store = Field()
    term_stores = ListField()

    @property
    def path(self) -> str:
        """
        Resolve the request path for this site instance.

        Returns:
            str:
                Site path based on `id` or the model's bound path argument.

        Notes:
            If `id` is missing but a path was provided at construction time
            (for example from `SiteQuerySet.by_path(...)`), that path is used.
        """
        if self.id is None and (p := self._args[1]) is not None:
            return p
        return super().path

    @property
    def drive(self):
        """
        Return a queryset/model handle for the site's default document library.

        Returns:
            Drive:
                Drive handle targeting `{site.path}/drive`.

        Notes:
            For path-based site addressing, a trailing `:` is preserved before
            appending `/drive` to comply with Graph URL rules.
        """
        p = self.path
        if ":" in p:
            p = f"{p}:"
        _logger.debug("Site.drive base_path=%s path=%s", self.path, f"{p}/drive")
        return Drive(client=self._args[0], path=f"{p}/drive")

    @property
    def lists(self):
        """
        Return a queryset for SharePoint lists under this site.

        Returns:
            ListQuerySet:
                Queryset targeting `{site.path}/lists`.

        Notes:
            For path-based site addressing, a trailing `:` is preserved before
            appending `/lists` to comply with Graph URL rules.
        """
        p = self.path
        if ":" in p:
            p = f"{p}:"
        _logger.debug("Site.lists base_path=%s path=%s", self.path, f"{p}/lists")
        return ListQuerySet(client=self._args[0], path=f"{p}/lists")

    def __repr__(self) -> str:
        return f"<Site: {self.display_name or self.name}>"

    async def get(self) -> "Site":
        """
        Fetch and hydrate this site from Graph.

        Returns:
            Site:
                Refreshed site model from Graph response data.

        Notes:
            If the path contains the `HOSTNAME` placeholder, it is resolved
            via `SiteQuerySet._get_hostname()` before the request is sent.

        Example:
            ```python
            # by_path() may create a lazy path with HOSTNAME placeholder:
            # /sites/HOSTNAME:/sites/Engineering
            lazy_site = client.sites.by_path("/sites/Engineering")

            # get() resolves HOSTNAME (e.g. contoso.sharepoint.com) and fetches:
            # /sites/contoso.sharepoint.com:/sites/Engineering
            site = await lazy_site.get()
            print(site.id, site.display_name)
            ```
        """
        p = self.path
        c = self._client
        if "HOSTNAME" in p:
            hostname = await c.sites._get_hostname()
            p = p.replace("HOSTNAME", hostname)
        _logger.debug("Site.get path=%s", p)
        data = await c.get(p)
        return Site.from_graph(data=data, client=c)


# class SitePath(PropertyModel):

#     @property
#     def path(self) -> str:
#         if p := self._args[1]:
#             return p
#         raise AttributeError(f"{type(self).__name__} object has no attribute 'path'")

#     @property
#     def drive(self):
#         return Drive(client=self._args[0], path=f"{self.path}:/drive")

#     @property
#     def lists(self) -> ListQuerySet:
#         return ListQuerySet(client=self._args[0], path=f"{self.path}:/lists")


class SiteQuerySet(QuerySet[Site]):
    """
    QuerySet for Microsoft Graph SharePoint site resources.
    """

    model_class = Site

    @override
    def search(
        self, *q_objects: "Q", keyword: str | None = None, **kwargs: Any
    ) -> Self:
        """
        Build a site search queryset using keyword search.

        Args:
            *q_objects:
                Not supported for site search. Must be empty.
            keyword:
                Search keyword passed as Graph `search` parameter.
            **kwargs:
                Not supported for site search. Must be empty.

        Returns:
            Self:
                Cloned queryset with consistency header and search keyword set.

        Raises:
            ValueError:
                If `q_objects`/`kwargs` are provided, or `keyword` is missing.
        """
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
        _logger.debug("SiteQuerySet.search keyword=%s", keyword)
        return qs

    async def get(
        self, id: str | None = None, *, path: str | None = None, **kwargs: Any
    ) -> Site:
        """
        Retrieve a site by site id or server-relative path.

        Args:
            id:
                Site id for direct lookup (`/sites/{id}`).
            path:
                Server-relative path (for example `/sites/Engineering`).
            **kwargs:
                Reserved for compatibility. Not used.

        Returns:
            Site:
                Hydrated site model.

        Raises:
            ValueError:
                If neither `id` nor `path` is provided.
            httpx.HTTPStatusError:
                If Graph returns an HTTP error.
        """
        data = None
        if id:
            request_path = f"{self.path}/{id}"
            _logger.debug("SiteQuerySet.get by_id id=%s path=%s", id, request_path)
            data = await self._client.get(
                request_path, params=self._params, headers=self._headers
            )
        elif path:
            p = (path or "").strip()
            if not p.startswith("/"):
                p = "/" + p
            p_encoded = quote(p, safe="/")
            c: Client = self._client
            hostname = await c.sites._get_hostname()
            request_path = f"{self.path}/{hostname}:{p_encoded}"
            _logger.debug(
                "SiteQuerySet.get by_path input=%s hostname=%s path=%s",
                path,
                hostname,
                request_path,
            )
            data = await c.get(
                request_path,
                params=self._params,
                headers=self._headers,
            )
        else:
            raise ValueError(
                f"{type(self).__name__} get method requires a id/path argument."
            )

        return self.make_from_graph(data)

    def by_path(self, path: str) -> Site:
        """
        Create a lazy `Site` handle from a server-relative path.

        Args:
            path:
                Server-relative site path (for example `/sites/Engineering`).

        Returns:
            Site:
                Site model bound to a path-based Graph endpoint.

        Raises:
            ValueError:
                If `path` is empty.

        Notes:
            The resulting site is not fetched until `.get()` is called.
            If hostname is not yet cached, `HOSTNAME` placeholder is used and
            resolved later by `Site.get()`.
        """
        p = (path or "").strip()
        if not p:
            raise ValueError(f"{type(self).__name__} by_path requires a path.")
        if not p.startswith("/"):
            p = "/" + p
        p_encoded = quote(p, safe="/")
        host = getattr(self, "_hostname", None) or getattr(
            self._args[0], "_sharepoint_hostname", None
        )
        if not host:
            host = "HOSTNAME"
        full_path = f"{self.path}/{host}:{p_encoded}"
        _logger.debug(
            "SiteQuerySet.by_path input=%s hostname=%s normalized=%s path=%s",
            path,
            host,
            p_encoded,
            full_path,
        )
        return Site(client=self._args[0], path=full_path)

    async def _get_hostname(self) -> str:
        """Resolve and cache the SharePoint hostname (e.g. contoso.sharepoint.com)."""
        c = self._client
        hostname = getattr(c, "_sharepoint_hostname", None)
        if hostname is None:
            _logger.debug("SiteQuerySet._get_hostname cache_miss")
            root = await c.get("/sites/root")
            hostname = (root.get("siteCollection") or {}).get("hostname")
            if not hostname:
                raise RuntimeError(
                    "Could not discover SharePoint hostname from /sites/root"
                )
            setattr(c, "_sharepoint_hostname", hostname)
            _logger.debug("SiteQuerySet._get_hostname discovered=%s", hostname)
        else:
            _logger.debug("SiteQuerySet._get_hostname cache_hit=%s", hostname)
        return hostname
