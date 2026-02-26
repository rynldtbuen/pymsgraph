from __future__ import annotations

from typing import Any
from urllib.parse import quote

from pymsgraph.models.base import PropertyModel, ReadOnlyModel
from pymsgraph.models.fields import CharField, Field, IntegerField


class WorksheetRange:
    """
    Lazy worksheet range handle.

    This object stores a worksheet range address and only issues Graph requests
    when terminal methods like `.get()` or `.update(...)` are called.
    """

    def __init__(
        self,
        worksheet: "Worksheet",
        address: str,
        *,
        workbook_session_id: str | None = None,
    ) -> None:
        self._worksheet = worksheet
        self._address = address
        self._workbook_session_id = workbook_session_id

    @property
    def address(self) -> str:
        """
        Return the bound A1-style range address.
        """
        return self._address

    async def get(self, *, workbook_session_id: str | None = None) -> list[list[Any]]:
        """
        Get values from this bound range.
        """
        addr = (self._address or "").strip()
        if not addr:
            raise ValueError(
                f"{type(self._worksheet).__name__} range.get method requires an address."
            )

        escaped_address = addr.replace("'", "''")
        path = f"{self._worksheet.path}/range(address='{escaped_address}')"
        session_id = workbook_session_id or self._workbook_session_id
        headers: dict[str, str] | None = None
        if session_id:
            headers = {"workbook-session-id": session_id}

        data = await self._worksheet._client.get(path, headers=headers)
        values = data.get("values")
        if isinstance(values, list):
            return values
        return []

    async def update(
        self,
        values: list[list[Any]],
        *,
        workbook_session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Update values in this bound range.
        """
        addr = (self._address or "").strip()
        if not addr:
            raise ValueError(
                f"{type(self._worksheet).__name__} range.update method requires an address."
            )
        if not isinstance(values, list) or any(not isinstance(r, list) for r in values):
            raise ValueError(
                f"{type(self._worksheet).__name__} range.update method requires values as list[list[Any]]."
            )

        escaped_address = addr.replace("'", "''")
        path = f"{self._worksheet.path}/range(address='{escaped_address}')"
        body = {"values": values}
        session_id = workbook_session_id or self._workbook_session_id
        headers: dict[str, str] | None = None
        if session_id:
            headers = {"workbook-session-id": session_id}

        data = await self._worksheet._client.patch(path, body=body, headers=headers)
        if isinstance(data, dict):
            return data
        return {}


class WorksheetRangeProxy:
    """
    Helper API for worksheet range operations.

    Usage:
    - lazy handle style: `worksheet.range("A1:B1").get()`
    """

    def __init__(self, worksheet: "Worksheet") -> None:
        self._worksheet = worksheet

    def __call__(
        self,
        address: str,
        *,
        workbook_session_id: str | None = None,
    ) -> WorksheetRange:
        """
        Create a lazy range handle for an address.
        """
        return WorksheetRange(
            self._worksheet,
            address,
            workbook_session_id=workbook_session_id,
        )


class Worksheet(ReadOnlyModel):
    """
    Graph `workbookWorksheet` resource.

    https://learn.microsoft.com/en-us/graph/api/resources/workbookworksheet?view=graph-rest-1.0
    """

    PATH = "/worksheets"

    name = CharField()
    position = IntegerField()
    visibility = CharField()

    def __repr__(self) -> str:
        return f"<Worksheet: {self.name or self.id}>"

    @property
    def range(self) -> WorksheetRangeProxy:
        """
        Return high-level range helper API.

        Example:
            ```python
            values = await worksheet.range("A1:B1").get()
            await worksheet.range("A1:B1").update([["Name", "Department"]])
            ```
        """
        return WorksheetRangeProxy(self)

    async def get(self) -> "Worksheet":
        """
        Fetch this worksheet from Graph.

        Returns:
            Worksheet:
                Hydrated worksheet model.

        Example:
            ```python
            workbook = await item.workbook.get()
            sheet = await workbook.worksheets.by_id("Sheet1").get()
            ```
        """
        path = self.path
        data = await self._client.get(path)
        return Worksheet.from_graph(
            data=data,
            client=self._client,
            path=self._args[1],
        )


class WorksheetsProxy:
    """
    Workbook worksheet collection helper.

    Provides collection-level operations such as add/delete.
    """

    def __init__(self, workbook: "Workbook") -> None:
        self._workbook = workbook

    @property
    def path(self) -> str:
        """
        Return worksheet collection path for the bound workbook.
        """
        return f"{self._workbook.path}/worksheets"

    def by_id(self, id_or_name: str) -> Worksheet:
        """
        Create a lazy worksheet handle from worksheet id or name.

        Args:
            id_or_name:
                Worksheet id or worksheet name.

        Returns:
            Worksheet:
                Lazy worksheet model bound to `{workbook.path}/worksheets/{value}`.

        Raises:
            ValueError:
                If `id_or_name` is empty.
        """
        value = (id_or_name or "").strip()
        if not value:
            raise ValueError(f"{type(self).__name__} by_id requires an id/name.")
        value_encoded = quote(value, safe="")
        return Worksheet(
            client=self._workbook._client,
            path=self.path,
            id=value_encoded,
        )

    async def add(
        self,
        name: str,
        *,
        workbook_session_id: str | None = None,
    ) -> Worksheet:
        """
        Add a worksheet to the workbook.

        Args:
            name:
                New worksheet name.
            workbook_session_id:
                Optional workbook session id sent as `workbook-session-id`.

        Returns:
            Worksheet:
                Hydrated worksheet model from Graph response.
        """
        sheet_name = (name or "").strip()
        if not sheet_name:
            raise ValueError(
                f"{type(self).__name__} add method requires a worksheet name."
            )

        headers: dict[str, str] | None = None
        if workbook_session_id:
            headers = {"workbook-session-id": workbook_session_id}

        data = await self._workbook._client.post(
            f"{self.path}/add",
            body={"name": sheet_name},
            headers=headers,
        )
        return Worksheet.from_graph(
            data=data,
            client=self._workbook._client,
            path=self.path,
        )

    async def delete(
        self,
        id_or_name: str,
        *,
        workbook_session_id: str | None = None,
    ) -> None:
        """
        Delete a worksheet by id or name.

        Args:
            id_or_name:
                Worksheet id or worksheet name.
            workbook_session_id:
                Optional workbook session id sent as `workbook-session-id`.
        """
        target = (id_or_name or "").strip()
        if not target:
            raise ValueError(
                f"{type(self).__name__} delete method requires a worksheet id/name."
            )

        headers: dict[str, str] | None = None
        if workbook_session_id:
            headers = {"workbook-session-id": workbook_session_id}

        worksheet = self.by_id(target)
        await self._workbook._client.post(
            f"{worksheet.path}/delete",
            body={},
            headers=headers,
        )


class Workbook(ReadOnlyModel, PropertyModel):
    """
    Graph `workbook` resource bound to a `driveItem`.

    This is a lightweight starting model intended for workbook-scoped APIs
    (worksheets, tables, ranges, sessions) that can be expanded incrementally.

    https://learn.microsoft.com/en-us/graph/api/resources/workbook?view=graph-rest-1.0
    """

    PATH = "/workbook"

    application = Field()
    names = Field()
    operations = Field()
    tables = Field()

    def __repr__(self) -> str:
        return f"<Workbook: path={self.path}>"

    @property
    def path(self) -> str:
        """
        Return the workbook endpoint path.

        Supports both:
        - base driveItem paths (for example `/users/{id}/drive/items/{item-id}`)
        - fully-qualified workbook paths ending with `/workbook`
        """
        if (p := self._args[1]) and p.endswith("/workbook"):
            return p
        return super().path

    async def get(self) -> "Workbook":
        """
        Fetch workbook metadata from Graph.

        Returns:
            Workbook:
                Hydrated workbook model at the current workbook endpoint.

        Example:
            ```python
            user = await client.users.get(id="user-id")
            item = user.drive.root.by_path("/Reports/financials.xlsx")
            workbook = await item.workbook.get()
            ```
        """
        data = await self._client.get(self.path)
        return Workbook.from_graph(
            data=data,
            client=self._client,
            path=self._args[1],
        )

    @property
    def worksheets(self) -> WorksheetsProxy:
        """
        Return worksheet collection helper for add/delete operations.

        Example:
            ```python
            sheet = await workbook.worksheets.add("Report")
            await workbook.worksheets.delete("OldSheet")
            current = await workbook.worksheets.by_id("Report").get()
            ```
        """
        return WorksheetsProxy(self)
