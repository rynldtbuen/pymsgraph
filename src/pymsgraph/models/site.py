from __future__ import annotations
from typing import Any

from pymsgraph.fields import CharField, Field
from pymsgraph.manager import BaseManager
from pymsgraph.models.base import GraphModel
from pymsgraph.queryset import QuerySet
from urllib.parse import quote


class SiteQuerySet(QuerySet["Site"]):
    def get(
        self,
        *,
        id: str | None = None,
        path: str | None = None,
        **lookups: Any,
    ) -> "Site":
        m = self.model
        client = m._get_client()

        # Allow id/path to come via **lookups (keeps QuerySet.get(...) feel),
        # but reject everything else since Site doesn't support filtering.
        if lookups:
            allowed = {"id", "path"}
            unknown = set(lookups) - allowed
            if unknown:
                raise TypeError(
                    f"{m.__name__}.objects.get() only supports id= or path= "
                    f"(got unsupported lookups: {', '.join(sorted(unknown))})"
                )
            id = id if id is not None else lookups.get("id")
            path = path if path is not None else lookups.get("path")

        # Enforce exactly one selector
        if (id is None) == (path is None):
            raise TypeError("Provide exactly one of id= or path=.")

        # 1) /sites/{site-id}
        if id is not None:
            payload = client.get(
                f"{m.endpoint}/{id}",
                params=self._params,
                headers=self._headers,
            )
            return m.from_graph(payload)

        # 2) /sites/{hostname}:/{server-relative-path}
        p = (path or "").strip()
        p = "/" + p.lstrip("/")  # normalize leading slash

        # Optional: if you *don't* want root-by-path here, make it explicit.
        if p == "/":
            raise TypeError(
                "path='/' (root) is not supported here; use Site.get_root() (or similar)."
            )

        hostname = m.get_hostname()
        if not hostname:
            raise ValueError(
                "hostname is required to resolve a SharePoint site by path."
            )

        # Encode path but keep slashes
        p_encoded = quote(p, safe="/")

        payload = client.get(
            f"{m.endpoint}/{hostname}:{p_encoded}",
            params=self._params,
            headers=self._headers,
        )
        return m.from_graph(payload)

    def search(self, query: str) -> list["Site"]:
        """
        Search SharePoint sites (first page only).

        Calls: GET /sites?search={query}
        """

        q = (query or "").strip()
        if not q:
            raise ValueError("query is required")

        m = self.model
        client = m._get_client()

        params = dict(self._params or {})
        params["search"] = q

        payload = client.get(
            m.endpoint,
            params=params,
            headers=self._headers,
        )

        items = payload.get("value") or []
        return [m.from_graph(item) for item in items]


class Site(GraphModel):
    """
    SharePoint Site model (minimal).

    Typical GET patterns you’ll want to support:
      - /sites/root
      - /sites/{site-id}
      - /sites/{hostname}:{server-relative-path}:
    """

    endpoint = "/sites"
    objects = SiteQuerySet.as_manager()

    # Common site fields returned by Graph
    display_name = CharField(read_only=True, max_length=255, strip=True)  # displayName
    name = CharField(read_only=True, max_length=255)  # name
    web_url = CharField(read_only=True, max_length=2048)  # webUrl

    # Nested siteCollection object (often present on sites)
    site_collection = Field(read_only=True)  # siteCollection

    @classmethod
    def get_hostname(cls) -> str:
        """Resolve and cache the SharePoint hostname (e.g. contoso.sharepoint.com)."""
        client = cls._get_client()

        hostname = getattr(client, "_sp_hostname", None)
        if hostname is None:
            root = client.get("/sites/root")
            hostname = (root.get("siteCollection") or {}).get("hostname")
            if not hostname:
                raise RuntimeError(
                    "Could not discover SharePoint hostname from /sites/root"
                )

            setattr(client, "_sp_hostname", hostname)  # cache on client instance
        return hostname

    @property
    def lists(self):
        """
        Related manager:
            site.lists.all() -> QuerySet[List] hitting /sites/{site-id}/lists
        """
        try:
            return self._lists
        except AttributeError:
            mgr = BaseManager.from_queryset(_SiteListsQuerySet)(List, site=self)
            self._lists = mgr
            return mgr


class _SiteListsQuerySet(QuerySet["List"]):
    """Site-scoped lists endpoint: /sites/{site-id}/lists"""

    @property
    def endpoint(self) -> str:
        site: Site = self._kwargs["site"]
        return f"{site.get_endpoint()}/lists"


class List(GraphModel):
    """
    SharePoint List model (minimal).

    NOTE:
      Lists are typically *scoped under a site*, so you'll usually access them via:
        site.lists.all()
      rather than List.objects.all().
    """

    endpoint = (
        "/lists"  # not commonly used directly; site-scoped endpoints are preferred.
    )

    # Common list fields returned by Graph
    display_name = CharField(read_only=True, max_length=255, strip=True)  # displayName
    name = CharField(read_only=True, max_length=255)  # name (often present)
    web_url = CharField(read_only=True, max_length=2048)  # webUrl

    # Graph returns a nested "list" object (template, hidden, etc.)
    # If you name the attr "list_info", you likely want graph_name="list" explicitly.
    list_info = Field(graph_name="list", read_only=True)
