from __future__ import annotations

from typing import Any
from urllib.parse import quote

from pymsgraph.models.base import Model, PropertyModel, ReadOnlyModel
from pymsgraph.models.fields import (
    BooleanField,
    CharField,
    Field,
    IntegerField,
    ListField,
)
from pymsgraph.models.query import QuerySet

_COMMON_COLORS: dict[str, str] = {
    "black": "#000000",
    "white": "#FFFFFF",
    "red": "#FF0000",
    "green": "#008000",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "orange": "#FFA500",
    "purple": "#800080",
    "pink": "#FFC0CB",
    "brown": "#A52A2A",
    "gray": "#808080",
    "grey": "#808080",
    "light_gray": "#D3D3D3",
    "light_grey": "#D3D3D3",
    "dark_gray": "#A9A9A9",
    "dark_grey": "#A9A9A9",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "lime": "#00FF00",
    "maroon": "#800000",
    "navy": "#000080",
    "olive": "#808000",
    "teal": "#008080",
    "silver": "#C0C0C0",
    "gold": "#FFD700",
}


def _normalize_color_value(color: str) -> str:
    value = (color or "").strip()
    if not value:
        raise ValueError("Color value is required.")

    if value.startswith("#"):
        hex_part = value[1:]
        if len(hex_part) == 3 and all(
            ch in "0123456789abcdefABCDEF" for ch in hex_part
        ):
            hex_part = "".join(ch * 2 for ch in hex_part)
        if len(hex_part) != 6 or not all(
            ch in "0123456789abcdefABCDEF" for ch in hex_part
        ):
            raise ValueError(
                "Color must be a named color or a valid hex value like '#RRGGBB'."
            )
        return f"#{hex_part.upper()}"

    key = value.lower().replace("-", "_").replace(" ", "_")
    if mapped := _COMMON_COLORS.get(key):
        return mapped

    supported = ", ".join(sorted(k for k in _COMMON_COLORS if k == k.replace(" ", "_")))
    raise ValueError(
        f"Unsupported color: {color!r}. Use hex '#RRGGBB' or one of: {supported}"
    )


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

    @property
    def font(self) -> "WorksheetRangeFont":
        """
        Return font-formatting helper for this range.

        Example:
            ```python
            await worksheet.range("A1:B1").font.set_color("#FF0000")
            ```
        """
        return WorksheetRangeFont(self)

    @property
    def fill(self) -> "WorksheetRangeFill":
        """
        Return fill-formatting helper for this range.

        Example:
            ```python
            await worksheet.range("A1:B1").fill.set_color("#FFF2CC")
            ```
        """
        return WorksheetRangeFill(self)

    def _range_path(self) -> str:
        addr = (self._address or "").strip()
        if not addr:
            raise ValueError(
                f"{type(self._worksheet).__name__} range method requires an address."
            )
        escaped_address = addr.replace("'", "''")
        return f"{self._worksheet.path}/range(address='{escaped_address}')"

    def _headers(self, workbook_session_id: str | None = None) -> dict[str, str] | None:
        session_id = workbook_session_id or self._workbook_session_id
        if session_id:
            return {"workbook-session-id": session_id}
        return None

    async def get(self, *, workbook_session_id: str | None = None) -> list[list[Any]]:
        """
        Get values from this bound range.
        """
        data = await self._worksheet._client.get(
            self._range_path(), headers=self._headers(workbook_session_id)
        )
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
        self._range_path()
        if not isinstance(values, list) or any(not isinstance(r, list) for r in values):
            raise ValueError(
                f"{type(self._worksheet).__name__} range.update method requires values as list[list[Any]]."
            )

        body = {"values": values}
        data = await self._worksheet._client.patch(
            self._range_path(),
            body=body,
            headers=self._headers(workbook_session_id),
        )
        if isinstance(data, dict):
            return data
        return {}


class WorksheetRangeFont:
    """
    Font-formatting helper for a worksheet range.

    Reference:
    https://learn.microsoft.com/en-us/graph/api/resources/workbookrangefont
    """

    def __init__(self, range_ref: WorksheetRange) -> None:
        self._range = range_ref

    async def set_color(
        self,
        color: str,
        *,
        workbook_session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Set text color for all cells in the bound range.

        Args:
            color:
                Font color value (for example `#FF0000`).
            workbook_session_id:
                Optional workbook session id sent as `workbook-session-id`.

        Returns:
            dict[str, Any]:
                Graph response payload for range font update.
        """
        color_value = _normalize_color_value(color)

        data = await self._range._worksheet._client.patch(
            f"{self._range._range_path()}/format/font",
            body={"color": color_value},
            headers=self._range._headers(workbook_session_id),
        )
        if isinstance(data, dict):
            return data
        return {}


class WorksheetRangeFill:
    """
    Fill-formatting helper for a worksheet range.

    Reference:
    https://learn.microsoft.com/en-us/graph/api/resources/workbookrangefill
    """

    def __init__(self, range_ref: WorksheetRange) -> None:
        self._range = range_ref

    async def set_color(
        self,
        color: str,
        *,
        workbook_session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Set fill color for all cells in the bound range.

        Args:
            color:
                Fill color value (for example `#FFF2CC`).
            workbook_session_id:
                Optional workbook session id sent as `workbook-session-id`.

        Returns:
            dict[str, Any]:
                Graph response payload for range fill update.
        """
        color_value = _normalize_color_value(color)

        data = await self._range._worksheet._client.patch(
            f"{self._range._range_path()}/format/fill",
            body={"color": color_value},
            headers=self._range._headers(workbook_session_id),
        )
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

    @property
    def tables(self) -> "WorkbookTablesProxy":
        """
        Return worksheet-scoped table collection helper.

        Example:
            ```python
            table = await worksheet.tables.add("Sheet1!A1:D5")
            ```
        """
        return WorkbookTablesProxy(self)

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


class WorkbookTableColumn(ReadOnlyModel):
    """
    Graph `workbookTableColumn` resource.

    https://learn.microsoft.com/en-us/graph/api/resources/workbooktablecolumn?view=graph-rest-1.0
    """

    PATH = "/columns"

    index = IntegerField()
    name = CharField()
    values = Field()

    def __repr__(self) -> str:
        return f"<WorkbookTableColumn: {self.name or self.id}>"


class WorkbookTableColumnQuerySet(QuerySet[WorkbookTableColumn]):
    """
    QuerySet for workbook table columns.
    """

    model_class = WorkbookTableColumn


class WorkbookTableRow(ReadOnlyModel):
    """
    Graph `workbookTableRow` resource.

    https://learn.microsoft.com/en-us/graph/api/resources/workbooktablerow?view=graph-rest-1.0
    """

    PATH = "/rows"

    index = IntegerField()
    values = Field()

    def __repr__(self) -> str:
        return (
            f"<WorkbookTableRow: {self.index if self.index is not None else self.id}>"
        )


class WorkbookTableRowQuerySet(QuerySet[WorkbookTableRow]):
    """
    QuerySet for workbook table rows.
    """

    model_class = WorkbookTableRow


class WorkbookTableRowsProxy:
    """
    Helper for workbook table row collection operations.
    """

    def __init__(self, table: "WorkbookTable") -> None:
        self._table = table

    @property
    def path(self) -> str:
        return f"{self._table.path}/rows"

    def queryset(self) -> WorkbookTableRowQuerySet:
        return WorkbookTableRowQuerySet(self._table._client, path=self.path)

    def __aiter__(self):
        return self.queryset().__aiter__()

    async def add(
        self,
        values: list[list[Any]],
        *,
        index: int | None = None,
        workbook_session_id: str | None = None,
    ) -> WorkbookTableRow:
        """
        Add one or more rows to this table.

        Args:
            values:
                Two-dimensional row values to append or insert.
            index:
                Optional zero-based insertion index. When omitted, Graph appends rows.
            workbook_session_id:
                Optional workbook session id sent as `workbook-session-id`.
        """
        if not isinstance(values, list) or any(not isinstance(r, list) for r in values):
            raise ValueError(
                f"{type(self).__name__} add method requires values as list[list[Any]]."
            )

        body: dict[str, Any] = {"values": values}
        if index is not None:
            body["index"] = index

        data = await self._table._client.post(
            f"{self.path}/add",
            body=body,
            headers=_workbook_headers(workbook_session_id),
        )
        return WorkbookTableRow.from_graph(
            data=data,
            client=self._table._client,
            path=self.path,
        )


class WorkbookTableColumnsProxy:
    """
    Helper for workbook table column collection operations.
    """

    def __init__(self, table: "WorkbookTable") -> None:
        self._table = table

    @property
    def path(self) -> str:
        return f"{self._table.path}/columns"

    def queryset(self) -> WorkbookTableColumnQuerySet:
        return WorkbookTableColumnQuerySet(self._table._client, path=self.path)

    def __aiter__(self):
        return self.queryset().__aiter__()

    async def add(
        self,
        *,
        index: int | None = None,
        values: list[list[Any]] | None = None,
        name: str | None = None,
        workbook_session_id: str | None = None,
    ) -> WorkbookTableColumn:
        """
        Add a column to this table.

        Args:
            index:
                Optional zero-based insertion index.
            values:
                Optional two-dimensional column values.
            name:
                Optional new column name.
            workbook_session_id:
                Optional workbook session id sent as `workbook-session-id`.
        """
        body: dict[str, Any] = {}
        if index is not None:
            body["index"] = index
        if values is not None:
            if not isinstance(values, list) or any(
                not isinstance(r, list) for r in values
            ):
                raise ValueError(
                    f"{type(self).__name__} add method requires values as list[list[Any]]."
                )
            body["values"] = values
        if name:
            body["name"] = name
        if not body:
            raise ValueError(
                f"{type(self).__name__} add method requires index, values, or name."
            )

        data = await self._table._client.post(
            f"{self.path}/add",
            body=body,
            headers=_workbook_headers(workbook_session_id),
        )
        return WorkbookTableColumn.from_graph(
            data=data,
            client=self._table._client,
            path=self.path,
        )


class WorkbookTable(Model):
    """
    Graph `workbookTable` resource.

    https://learn.microsoft.com/en-us/graph/api/resources/workbooktable?view=graph-rest-1.0
    """

    PATH = "/tables"

    highlight_first_column = BooleanField()
    highlight_last_column = BooleanField()
    legacy_id = CharField(read_only=True, graph_attr_name="legacyId")
    name = CharField()
    show_banded_columns = BooleanField()
    show_banded_rows = BooleanField()
    show_filter_button = BooleanField()
    show_headers = BooleanField()
    show_totals = BooleanField()
    style = CharField()

    def __repr__(self) -> str:
        return f"<WorkbookTable: {self.name or self.id}>"

    @property
    def rows(self) -> WorkbookTableRowsProxy:
        """
        Return table row collection helper.
        """
        return WorkbookTableRowsProxy(self)

    @property
    def columns(self) -> WorkbookTableColumnsProxy:
        """
        Return table column collection helper.
        """
        return WorkbookTableColumnsProxy(self)

    async def get(self) -> "WorkbookTable":
        """
        Fetch this table from Graph.
        """
        data = await self._client.get(self.path)
        return WorkbookTable.from_graph(
            data=data,
            client=self._client,
            path=self._args[1],
        )

    async def update(
        self,
        *,
        workbook_session_id: str | None = None,
        **fields: Any,
    ) -> "WorkbookTable":
        """
        Update table properties and return the updated table.
        """
        if not fields:
            return self

        body: dict[str, Any] = {}
        for attr_name, value in fields.items():
            field = self.FIELDS.get(attr_name)
            if field is None:
                raise ValueError(f"Unknown field {attr_name!r}")
            if field.read_only:
                raise ValueError(f"{attr_name!r} is read-only")
            body[field.graph_attr_name or attr_name] = field.to_graph(value)

        data = await self._client.patch(
            self.path,
            body=body,
            headers=_workbook_headers(workbook_session_id),
        )
        if isinstance(data, dict):
            refreshed = WorkbookTable.from_graph(
                data=data,
                client=self._client,
                path=self._args[1],
            )
            self._data = refreshed._data
            self._graph_data = refreshed._graph_data
        return self

    async def delete(self, *, workbook_session_id: str | None = None) -> None:
        """
        Delete this table.
        """
        await self._client.delete(
            self.path,
            headers=_workbook_headers(workbook_session_id),
        )

    async def clear_filters(self, *, workbook_session_id: str | None = None) -> None:
        """
        Clear all filters currently applied to this table.
        """
        await self._client.post(
            f"{self.path}/clearFilters",
            body={},
            headers=_workbook_headers(workbook_session_id),
        )

    async def reapply_filters(self, *, workbook_session_id: str | None = None) -> None:
        """
        Reapply filters currently applied to this table.
        """
        await self._client.post(
            f"{self.path}/reapplyFilters",
            body={},
            headers=_workbook_headers(workbook_session_id),
        )

    async def convert_to_range(
        self, *, workbook_session_id: str | None = None
    ) -> dict[str, Any]:
        """
        Convert this table into a normal range and return Graph range payload.
        """
        data = await self._client.post(
            f"{self.path}/convertToRange",
            body={},
            headers=_workbook_headers(workbook_session_id),
        )
        return data if isinstance(data, dict) else {}

    async def range(self, *, workbook_session_id: str | None = None) -> dict[str, Any]:
        """
        Return the range associated with the entire table.
        """
        return await self._get_range("range", workbook_session_id=workbook_session_id)

    async def data_body_range(
        self, *, workbook_session_id: str | None = None
    ) -> dict[str, Any]:
        """
        Return the range associated with the table data body.
        """
        return await self._get_range(
            "dataBodyRange", workbook_session_id=workbook_session_id
        )

    async def header_row_range(
        self, *, workbook_session_id: str | None = None
    ) -> dict[str, Any]:
        """
        Return the range associated with the table header row.
        """
        return await self._get_range(
            "headerRowRange", workbook_session_id=workbook_session_id
        )

    async def total_row_range(
        self, *, workbook_session_id: str | None = None
    ) -> dict[str, Any]:
        """
        Return the range associated with the table total row.
        """
        return await self._get_range(
            "totalRowRange", workbook_session_id=workbook_session_id
        )

    async def _get_range(
        self,
        endpoint: str,
        *,
        workbook_session_id: str | None = None,
    ) -> dict[str, Any]:
        data = await self._client.get(
            f"{self.path}/{endpoint}",
            headers=_workbook_headers(workbook_session_id),
        )
        return data if isinstance(data, dict) else {}


class WorkbookTableQuerySet(QuerySet[WorkbookTable]):
    """
    QuerySet for workbook table collections.
    """

    model_class = WorkbookTable


class WorkbookTablesProxy:
    """
    Workbook table collection helper.
    """

    def __init__(self, parent: "Workbook | Worksheet") -> None:
        self._parent = parent

    @property
    def path(self) -> str:
        return f"{self._parent.path}/tables"

    def queryset(self) -> WorkbookTableQuerySet:
        return WorkbookTableQuerySet(self._parent._client, path=self.path)

    def __aiter__(self):
        return self.queryset().__aiter__()

    def by_id(self, id_or_name: str) -> WorkbookTable:
        """
        Create a lazy table handle from table id or name.
        """
        value = (id_or_name or "").strip()
        if not value:
            raise ValueError(f"{type(self).__name__} by_id requires an id/name.")
        return WorkbookTable(
            client=self._parent._client,
            path=self.path,
            id=quote(value, safe=""),
        )

    async def add(
        self,
        address: str,
        *,
        has_headers: bool = True,
        workbook_session_id: str | None = None,
    ) -> WorkbookTable:
        """
        Create a table from a worksheet range address.
        """
        range_address = (address or "").strip()
        if not range_address:
            raise ValueError(f"{type(self).__name__} add method requires an address.")

        data = await self._parent._client.post(
            f"{self.path}/add",
            body={"address": range_address, "hasHeaders": has_headers},
            headers=_workbook_headers(workbook_session_id),
        )
        return WorkbookTable.from_graph(
            data=data,
            client=self._parent._client,
            path=self.path,
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

    @property
    def tables(self) -> WorkbookTablesProxy:
        """
        Return workbook table collection helper.

        Example:
            ```python
            table = await workbook.tables.add("Sheet1!A1:D5")
            rows = [row async for row in table.rows]
            ```
        """
        return WorkbookTablesProxy(self)


def _workbook_headers(workbook_session_id: str | None = None) -> dict[str, str] | None:
    if workbook_session_id:
        return {"workbook-session-id": workbook_session_id}
    return None
