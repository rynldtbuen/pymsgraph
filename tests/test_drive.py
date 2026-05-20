import json
from typing import TYPE_CHECKING

import httpx
import pytest

from pymsgraph.models.drive import (
	Drive,
	DriveItem,
	ItemActivity,
	ItemActivityQuerySet,
	Workbook,
	WorkbookTable,
	Worksheet,
)
from pymsgraph.models.user import User

if TYPE_CHECKING:
	from .conftest import MakeClient


def test_path():
	drive = Drive(id="123")
	items = drive.root.items
	assert items.path == "/drives/123/root/children"
	assert drive.root.by_path(path="/abc/def").path == "/drives/123/root:/abc/def"
	assert (
		drive.root.by_path("/abc/def").items.path
		== "/drives/123/root:/abc/def:/children"
	)

	item = DriveItem(id="098", path="/drives/123/items")
	assert item.path == "/drives/123/items/098"
	assert item.items.path == "/drives/123/items/098/children"
	assert DriveItem(id="765", path="/drives/123/items").path == "/drives/123/items/765"
	assert (
		DriveItem(id="765", path="/drives/123/items").by_path("/abc/def").path
		== "/drives/123/items/765:/abc/def"
	)
	assert (
		DriveItem(id="765", path="/drives/123/items").by_path("/abc/def").items.path
		== "/drives/123/items/765:/abc/def:/children"
	)

	# DriveItemsQueryset does not support by_path chaining

	items = User(id="123").drive.root.items

	assert items.path == "/users/123/drive/root/children"
	assert (
		DriveItem(id="098", path="/users/123/drive/items").path
		== "/users/123/drive/items/098"
	)
	assert (
		DriveItem(id="098", path="/users/123/drive/items").items.path
		== "/users/123/drive/items/098/children"
	)
	assert (
		DriveItem(id="098", path="/users/123/drive/items").by_path("/abc/def").path
		== "/users/123/drive/items/098:/abc/def"
	)
	assert (
		DriveItem(id="098", path="/users/123/drive/items")
		.by_path("/abc/def")
		.items.path
		== "/users/123/drive/items/098:/abc/def:/children"
	)

	assert (
		User(id="123").drive.root.by_path("/abc/def").path
		== "/users/123/drive/root:/abc/def"
	)
	assert (
		User(id="123").drive.root.by_path("/abc/def").items.path
		== "/users/123/drive/root:/abc/def:/children"
	)

	User(id="123").drive.root.by_path("/123/456")


def test_drive_item_workbook_proxy(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, json={})

	client, _ = make_client(handler)
	item = DriveItem(id="item123", client=client, path="/users/u1/drive/items")

	workbook = item.workbook

	assert isinstance(workbook, Workbook)
	assert workbook.path == "/users/u1/drive/items/item123/workbook"


def test_drive_item_activities_queryset(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, json={"value": []})

	client, _ = make_client(handler)
	item = DriveItem(id="item123", client=client, path="/users/u1/drive/items")

	qs = item.activities

	assert isinstance(qs, ItemActivityQuerySet)
	assert qs.path == "/users/u1/drive/items/item123/activities"
	assert qs._model_class is ItemActivity


@pytest.mark.asyncio
async def test_drive_item_activities_list_uses_cached_data(
	make_client: "MakeClient",
) -> None:
	def handler(request: httpx.Request) -> httpx.Response:
		raise AssertionError("No HTTP call expected")

	client, _ = make_client(handler)
	item = DriveItem.from_graph(
		{
			"id": "item123",
			"activities": [
				{
					"id": "a1",
					"activityDateTime": "2026-03-10T01:23:45Z",
					"access": {},
					"actor": {"user": {"displayName": "Ada Lovelace"}},
				}
			],
		},
		client=client,
		path="/users/u1/drive/items",
	)

	items = [obj async for obj in item.activities]

	assert len(items) == 1
	assert isinstance(items[0], ItemActivity)
	assert items[0].id == "a1"
	assert items[0].activity_date_time is not None
	assert items[0].actor == {"user": {"displayName": "Ada Lovelace"}}


@pytest.mark.asyncio
async def test_user_drive_get_by_id(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.url.path == "/v1.0/users/u1":
			return httpx.Response(200, json={"id": "u1"})
		if request.url.path == "/v1.0/users/u1/drive":
			return httpx.Response(
				200,
				json={
					"id": "drive123",
					"name": "Demo Drive",
					"driveType": "documentLibrary",
					"webUrl": "https://contoso.sharepoint.com/drives/drive123",
				},
			)
		return httpx.Response(404)

	client, _ = make_client(handler)

	user = await client.users.get(id="u1")
	data = await client.get(user.drive.path)
	drive = Drive.from_graph(data, client=client, path=user.drive.path)

	assert drive.id == "drive123"
	assert drive.name == "Demo Drive"


@pytest.mark.asyncio
async def test_drive_item_workbook_get(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == "GET" and request.url.path == "/v1.0/users/u1/drive/items/item123/workbook":
			return httpx.Response(
				200,
				json={
					"application": {"name": "Excel"},
				},
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	item = DriveItem(id="item123", client=client, path="/users/u1/drive/items")

	workbook = await item.workbook.get()

	assert isinstance(workbook, Workbook)
	assert workbook.path == "/users/u1/drive/items/item123/workbook"
	assert workbook.application == {"name": "Excel"}


def test_workbook_worksheets_proxy_path(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, json={})

	client, _ = make_client(handler)
	workbook = Workbook(client=client, path="/users/u1/drive/items/item123/workbook")

	assert workbook.worksheets.path == "/users/u1/drive/items/item123/workbook/worksheets"


def test_workbook_tables_proxy_path(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, json={})

	client, _ = make_client(handler)
	workbook = Workbook(client=client, path="/users/u1/drive/items/item123/workbook")

	assert workbook.tables.path == "/users/u1/drive/items/item123/workbook/tables"
	assert workbook.tables.by_id("Table 1").path in {
		"/users/u1/drive/items/item123/workbook/tables/Table%201",
		"/users/u1/drive/items/item123/workbook/tables/Table 1",
	}


@pytest.mark.asyncio
async def test_workbook_tables_list(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if (
			request.method == "GET"
			and request.url.path == "/v1.0/users/u1/drive/items/item123/workbook/tables"
		):
			return httpx.Response(
				200,
				json={
					"value": [
						{
							"id": "table-1",
							"name": "SalesTable",
							"showHeaders": True,
							"showTotals": False,
							"style": "TableStyleMedium2",
						}
					]
				},
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	workbook = Workbook(client=client, path="/users/u1/drive/items/item123/workbook")

	tables = [table async for table in workbook.tables]

	assert len(tables) == 1
	assert isinstance(tables[0], WorkbookTable)
	assert tables[0].id == "table-1"
	assert tables[0].name == "SalesTable"
	assert tables[0].show_headers is True
	assert tables[0].style == "TableStyleMedium2"


@pytest.mark.asyncio
async def test_workbook_tables_add(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if (
			request.method == "POST"
			and request.url.path == "/v1.0/users/u1/drive/items/item123/workbook/tables/add"
		):
			assert request.headers.get("workbook-session-id") == "session-table"
			body = json.loads(request.content.decode())
			assert body == {"address": "Sheet1!A1:D5", "hasHeaders": True}
			return httpx.Response(
				200,
				json={
					"id": "table-1",
					"name": "Table1",
					"showHeaders": True,
					"showTotals": False,
				},
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	workbook = Workbook(client=client, path="/users/u1/drive/items/item123/workbook")

	table = await workbook.tables.add(
		"Sheet1!A1:D5",
		workbook_session_id="session-table",
	)

	assert isinstance(table, WorkbookTable)
	assert table.id == "table-1"
	assert table.name == "Table1"
	assert table.path == "/users/u1/drive/items/item123/workbook/tables/table-1"


@pytest.mark.asyncio
async def test_worksheet_tables_add(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if (
			request.method == "POST"
			and request.url.path
			== "/v1.0/users/u1/drive/items/item123/workbook/worksheets/s1/tables/add"
		):
			body = json.loads(request.content.decode())
			assert body == {"address": "A1:B3", "hasHeaders": False}
			return httpx.Response(
				200,
				json={
					"id": "table-2",
					"name": "SheetTable",
					"showHeaders": False,
				},
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	table = await worksheet.tables.add("A1:B3", has_headers=False)

	assert isinstance(table, WorkbookTable)
	assert table.id == "table-2"
	assert table.path == (
		"/users/u1/drive/items/item123/workbook/worksheets/s1/tables/table-2"
	)


@pytest.mark.asyncio
async def test_workbook_table_get_update_delete(make_client: "MakeClient"):
	seen = []

	def handler(request: httpx.Request) -> httpx.Response:
		seen.append(
			{
				"method": request.method,
				"path": request.url.path,
				"body": json.loads(request.content.decode()) if request.content else None,
				"headers": dict(request.headers),
			}
		)
		if (
			request.method == "GET"
			and request.url.path == "/v1.0/users/u1/drive/items/item123/workbook/tables/table-1"
		):
			return httpx.Response(
				200,
				json={"id": "table-1", "name": "SalesTable", "showHeaders": True},
			)
		if (
			request.method == "PATCH"
			and request.url.path == "/v1.0/users/u1/drive/items/item123/workbook/tables/table-1"
		):
			assert request.headers.get("workbook-session-id") == "session-update"
			return httpx.Response(
				200,
				json={
					"id": "table-1",
					"name": "SalesTableRenamed",
					"showHeaders": False,
				},
			)
		if (
			request.method == "DELETE"
			and request.url.path == "/v1.0/users/u1/drive/items/item123/workbook/tables/table-1"
		):
			return httpx.Response(204)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	table_ref = Workbook(
		client=client,
		path="/users/u1/drive/items/item123/workbook",
	).tables.by_id("table-1")

	table = await table_ref.get()
	await table.update(
		name="SalesTableRenamed",
		show_headers=False,
		workbook_session_id="session-update",
	)
	await table.delete()

	assert table.name == "SalesTableRenamed"
	assert any(
		item["method"] == "PATCH"
		and item["body"] == {"name": "SalesTableRenamed", "showHeaders": False}
		for item in seen
	)


@pytest.mark.asyncio
async def test_workbook_table_rows_add(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if (
			request.method == "POST"
			and request.url.path
			== "/v1.0/users/u1/drive/items/item123/workbook/tables/table-1/rows/add"
		):
			assert request.headers.get("workbook-session-id") == "session-rows"
			body = json.loads(request.content.decode())
			assert body == {"values": [[1, 2, 3], [4, 5, 6]], "index": 5}
			return httpx.Response(200, json={"index": 5, "values": [[1, 2, 3]]})
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	table = Workbook(
		client=client,
		path="/users/u1/drive/items/item123/workbook",
	).tables.by_id("table-1")

	row = await table.rows.add(
		[[1, 2, 3], [4, 5, 6]],
		index=5,
		workbook_session_id="session-rows",
	)

	assert row.index == 5
	assert row.values == [[1, 2, 3]]


@pytest.mark.asyncio
async def test_workbook_table_columns_add(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if (
			request.method == "POST"
			and request.url.path
			== "/v1.0/users/u1/drive/items/item123/workbook/tables/table-1/columns/add"
		):
			body = json.loads(request.content.decode())
			assert body == {
				"index": 1,
				"values": [["Region"], ["West"]],
				"name": "Region",
			}
			return httpx.Response(
				200,
				json={"id": "col-1", "index": 1, "name": "Region"},
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	table = Workbook(
		client=client,
		path="/users/u1/drive/items/item123/workbook",
	).tables.by_id("table-1")

	column = await table.columns.add(
		index=1,
		values=[["Region"], ["West"]],
		name="Region",
	)

	assert column.id == "col-1"
	assert column.index == 1
	assert column.name == "Region"


@pytest.mark.asyncio
async def test_workbook_table_range_actions(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		base = "/v1.0/users/u1/drive/items/item123/workbook/tables/table-1"
		if request.method == "GET" and request.url.path == f"{base}/range":
			assert request.headers.get("workbook-session-id") == "session-range"
			return httpx.Response(200, json={"address": "Sheet1!A1:D5"})
		if request.method == "GET" and request.url.path == f"{base}/dataBodyRange":
			return httpx.Response(200, json={"address": "Sheet1!A2:D5"})
		if request.method == "POST" and request.url.path == f"{base}/clearFilters":
			return httpx.Response(204)
		if request.method == "POST" and request.url.path == f"{base}/reapplyFilters":
			return httpx.Response(204)
		if request.method == "POST" and request.url.path == f"{base}/convertToRange":
			return httpx.Response(200, json={"address": "Sheet1!A1:D5"})
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	table = Workbook(
		client=client,
		path="/users/u1/drive/items/item123/workbook",
	).tables.by_id("table-1")

	table_range = await table.range(workbook_session_id="session-range")
	data_body = await table.data_body_range()
	await table.clear_filters()
	await table.reapply_filters()
	converted = await table.convert_to_range()

	assert table_range["address"] == "Sheet1!A1:D5"
	assert data_body["address"] == "Sheet1!A2:D5"
	assert converted["address"] == "Sheet1!A1:D5"


@pytest.mark.asyncio
async def test_workbook_worksheets_add(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == "POST" and request.url.path == "/v1.0/users/u1/drive/items/item123/workbook/worksheets/add":
			assert request.headers.get("workbook-session-id") == "session-add"
			body = json.loads(request.content.decode())
			assert body == {"name": "Sheet2"}
			return httpx.Response(
				200,
				json={
					"id": "sheet-2",
					"name": "Sheet2",
					"position": 2,
					"visibility": "Visible",
				},
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	workbook = Workbook(client=client, path="/users/u1/drive/items/item123/workbook")

	sheet = await workbook.worksheets.add("Sheet2", workbook_session_id="session-add")

	assert isinstance(sheet, Worksheet)
	assert sheet.id == "sheet-2"
	assert sheet.name == "Sheet2"
	assert sheet.path == "/users/u1/drive/items/item123/workbook/worksheets/sheet-2"


@pytest.mark.asyncio
async def test_workbook_worksheets_delete(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		expected = "/v1.0/users/u1/drive/items/item123/workbook/worksheets/Q1%20Summary/delete"
		if request.method == "POST" and request.url.path in {expected, expected.replace("%20", " ")}:
			assert request.headers.get("workbook-session-id") == "session-del"
			body = json.loads(request.content.decode())
			assert body == {}
			return httpx.Response(204)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	workbook = Workbook(client=client, path="/users/u1/drive/items/item123/workbook")

	await workbook.worksheets.delete("Q1 Summary", workbook_session_id="session-del")


@pytest.mark.asyncio
async def test_workbook_worksheets_add_delete_invalid_args(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		raise AssertionError("No HTTP call expected")

	client, _ = make_client(handler)
	workbook = Workbook(client=client, path="/users/u1/drive/items/item123/workbook")

	with pytest.raises(ValueError):
		await workbook.worksheets.add("")
	with pytest.raises(ValueError):
		await workbook.worksheets.delete("   ")


def test_workbook_sheet_requires_id_or_name(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		return httpx.Response(200, json={})

	client, _ = make_client(handler)
	workbook = Workbook(client=client, path="/users/u1/drive/items/item123/workbook")

	with pytest.raises(ValueError):
		workbook.worksheets.by_id("")


@pytest.mark.asyncio
async def test_workbook_get_sheet_by_id(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == "GET" and request.url.path == "/v1.0/users/u1/drive/items/item123/workbook/worksheets/s1":
			return httpx.Response(
				200,
				json={
					"id": "s1",
					"name": "Sheet1",
					"position": 0,
					"visibility": "Visible",
				},
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	workbook = Workbook(client=client, path="/users/u1/drive/items/item123/workbook")

	sheet = await workbook.worksheets.by_id("s1").get()

	assert isinstance(sheet, Worksheet)
	assert sheet.id == "s1"
	assert sheet.name == "Sheet1"
	assert sheet.position == 0
	assert sheet.path == "/users/u1/drive/items/item123/workbook/worksheets/s1"


@pytest.mark.asyncio
async def test_workbook_get_sheet_by_name(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == "GET" and request.url.path in {
			"/v1.0/users/u1/drive/items/item123/workbook/worksheets/Q1 Summary",
			"/v1.0/users/u1/drive/items/item123/workbook/worksheets/Q1%20Summary",
		}:
			return httpx.Response(
				200,
				json={
					"id": "sheet-q1",
					"name": "Q1 Summary",
					"position": 1,
					"visibility": "Visible",
				},
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	workbook = Workbook(client=client, path="/users/u1/drive/items/item123/workbook")

	sheet = await workbook.worksheets.by_id("Q1 Summary").get()

	assert isinstance(sheet, Worksheet)
	assert sheet.id == "sheet-q1"
	assert sheet.name == "Q1 Summary"
	assert sheet.position == 1
	assert sheet.path == "/users/u1/drive/items/item123/workbook/worksheets/sheet-q1"


def test_workbook_by_id_invalid_args(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		raise AssertionError("No HTTP call expected")

	client, _ = make_client(handler)
	workbook = Workbook(client=client, path="/users/u1/drive/items/item123/workbook")

	with pytest.raises(ValueError):
		workbook.worksheets.by_id("")
	with pytest.raises(ValueError):
		workbook.worksheets.by_id("   ")


@pytest.mark.asyncio
async def test_workbook_sheet_insert_values(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		expected = "/v1.0/users/u1/drive/items/item123/workbook/worksheets/s1/range(address='A1:B2')"
		if request.method == "PATCH" and request.url.path in {
			expected,
			expected.replace("'", "%27"),
		}:
			assert request.headers.get("workbook-session-id") == "session-1"
			assert request.content
			body = json.loads(request.content.decode())
			assert body == {
				"values": [["Name", "Department"], ["Alice", "Engineering"]]
			}
			return httpx.Response(
				200,
				json={
					"address": "Sheet1!A1:B2",
					"values": [["Name", "Department"], ["Alice", "Engineering"]],
				},
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	data = await worksheet.range("A1:B2", workbook_session_id="session-1").update(
		[["Name", "Department"], ["Alice", "Engineering"]]
	)

	assert data["address"] == "Sheet1!A1:B2"
	assert data["values"][1][0] == "Alice"


@pytest.mark.asyncio
async def test_workbook_sheet_insert_values_invalid_args(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		raise AssertionError("No HTTP call expected")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	with pytest.raises(ValueError):
		await worksheet.range("").update([["a"]])
	with pytest.raises(ValueError):
		await worksheet.range("A1").update(["a"])  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_workbook_sheet_get_values(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		expected = "/v1.0/users/u1/drive/items/item123/workbook/worksheets/s1/range(address='A1:B2')"
		if request.method == "GET" and request.url.path in {
			expected,
			expected.replace("'", "%27"),
		}:
			assert request.headers.get("workbook-session-id") == "session-1"
			return httpx.Response(
				200,
				json={
					"values": [["Name", "Department"], ["Alice", "Engineering"]],
				},
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	values = await worksheet.range("A1:B2", workbook_session_id="session-1").get()

	assert values == [["Name", "Department"], ["Alice", "Engineering"]]


@pytest.mark.asyncio
async def test_workbook_sheet_get_values_invalid_args(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		raise AssertionError("No HTTP call expected")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	with pytest.raises(ValueError):
		await worksheet.range("").get()


@pytest.mark.asyncio
async def test_workbook_sheet_range_get(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		expected = "/v1.0/users/u1/drive/items/item123/workbook/worksheets/s1/range(address='A1:B1')"
		if request.method == "GET" and request.url.path in {
			expected,
			expected.replace("'", "%27"),
		}:
			assert request.headers.get("workbook-session-id") == "session-1"
			return httpx.Response(200, json={"values": [["Name", "Department"]]})
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	values = await worksheet.range("A1:B1", workbook_session_id="session-1").get()

	assert values == [["Name", "Department"]]


@pytest.mark.asyncio
async def test_workbook_sheet_lazy_range_get(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		expected = "/v1.0/users/u1/drive/items/item123/workbook/worksheets/s1/range(address='A1:B1')"
		if request.method == "GET" and request.url.path in {
			expected,
			expected.replace("'", "%27"),
		}:
			assert request.headers.get("workbook-session-id") == "session-2"
			return httpx.Response(200, json={"values": [["Name", "Department"]]})
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	range_ref = worksheet.range("A1:B1", workbook_session_id="session-2")
	values = await range_ref.get()

	assert values == [["Name", "Department"]]


@pytest.mark.asyncio
async def test_workbook_sheet_lazy_range_update(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		expected = "/v1.0/users/u1/drive/items/item123/workbook/worksheets/s1/range(address='A1:B2')"
		if request.method == "PATCH" and request.url.path in {
			expected,
			expected.replace("'", "%27"),
		}:
			assert request.headers.get("workbook-session-id") == "session-3"
			body = json.loads(request.content.decode())
			assert body == {"values": [["Name", "Department"], ["Alice", "Engineering"]]}
			return httpx.Response(200, json={"address": "Sheet1!A1:B2"})
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	range_ref = worksheet.range("A1:B2", workbook_session_id="session-3")
	data = await range_ref.update([["Name", "Department"], ["Alice", "Engineering"]])

	assert data["address"] == "Sheet1!A1:B2"


@pytest.mark.asyncio
async def test_workbook_sheet_range_get_invalid_args(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		raise AssertionError("No HTTP call expected")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	with pytest.raises(ValueError):
		await worksheet.range("").get()


@pytest.mark.asyncio
async def test_workbook_sheet_range_font_set_color(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		expected = "/v1.0/users/u1/drive/items/item123/workbook/worksheets/s1/range(address='A1:B1')/format/font"
		if request.method == "PATCH" and request.url.path in {
			expected,
			expected.replace("'", "%27"),
		}:
			assert request.headers.get("workbook-session-id") == "session-font"
			body = json.loads(request.content.decode())
			assert body == {"color": "#FF0000"}
			return httpx.Response(200, json={"color": "#FF0000"})
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	data = await worksheet.range("A1:B1", workbook_session_id="session-font").font.set_color("#FF0000")

	assert data["color"] == "#FF0000"


@pytest.mark.asyncio
async def test_workbook_sheet_range_font_set_color_named_color(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		expected = "/v1.0/users/u1/drive/items/item123/workbook/worksheets/s1/range(address='A1:B1')/format/font"
		if request.method == "PATCH" and request.url.path in {
			expected,
			expected.replace("'", "%27"),
		}:
			body = json.loads(request.content.decode())
			assert body == {"color": "#000000"}
			return httpx.Response(200, json={"color": "#000000"})
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	data = await worksheet.range("A1:B1").font.set_color("black")

	assert data["color"] == "#000000"


@pytest.mark.asyncio
async def test_workbook_sheet_range_font_set_color_invalid_args(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		raise AssertionError("No HTTP call expected")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	with pytest.raises(ValueError):
		await worksheet.range("A1").font.set_color("")
	with pytest.raises(ValueError):
		await worksheet.range("").font.set_color("#FF0000")


@pytest.mark.asyncio
async def test_workbook_sheet_range_fill_set_color(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		expected = "/v1.0/users/u1/drive/items/item123/workbook/worksheets/s1/range(address='A1:B1')/format/fill"
		if request.method == "PATCH" and request.url.path in {
			expected,
			expected.replace("'", "%27"),
		}:
			assert request.headers.get("workbook-session-id") == "session-fill"
			body = json.loads(request.content.decode())
			assert body == {"color": "#FFF2CC"}
			return httpx.Response(200, json={"color": "#FFF2CC"})
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	data = await worksheet.range("A1:B1", workbook_session_id="session-fill").fill.set_color("#FFF2CC")

	assert data["color"] == "#FFF2CC"


@pytest.mark.asyncio
async def test_workbook_sheet_range_fill_set_color_named_color(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		expected = "/v1.0/users/u1/drive/items/item123/workbook/worksheets/s1/range(address='A1:B1')/format/fill"
		if request.method == "PATCH" and request.url.path in {
			expected,
			expected.replace("'", "%27"),
		}:
			body = json.loads(request.content.decode())
			assert body == {"color": "#D3D3D3"}
			return httpx.Response(200, json={"color": "#D3D3D3"})
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	data = await worksheet.range("A1:B1").fill.set_color("light gray")

	assert data["color"] == "#D3D3D3"


@pytest.mark.asyncio
async def test_workbook_sheet_range_fill_set_color_invalid_args(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		raise AssertionError("No HTTP call expected")

	client, _ = make_client(handler)
	worksheet = Worksheet(
		client=client,
		path="/users/u1/drive/items/item123/workbook/worksheets",
		id="s1",
	)

	with pytest.raises(ValueError):
		await worksheet.range("A1").fill.set_color("")
	with pytest.raises(ValueError):
		await worksheet.range("").fill.set_color("#FFF2CC")


@pytest.mark.asyncio
async def test_user_driveitems_get_by_id(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.url.path == "/v1.0/users/u1":
			return httpx.Response(200, json={"id": "u1"})
		if request.url.path == "/v1.0/users/u1/drive/items/item123":
			return httpx.Response(
				200,
				json={
					"id": "item123",
					"name": "Doc1",
					"webUrl": "https://contoso.sharepoint.com/doc1",
					"size": 1024,
					"file": {},
				},
			)
		return httpx.Response(404)

	client, _ = make_client(handler)

	user = await client.users.get(id="u1")
	item_ref = DriveItem(id="item123", path="/users/u1/drive/items")
	data = await client.get(item_ref.path)
	item = DriveItem.from_graph(data, client=client, path=item_ref.path)

	assert item.id == "item123"
	assert item.name == "Doc1"


@pytest.mark.asyncio
async def test_user_driveitems_get_by_path(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.url.path == "/v1.0/users/u1":
			return httpx.Response(200, json={"id": "u1"})
		if request.url.path == "/v1.0/users/u1/drive/root:/Reports/2024.xlsx":
			return httpx.Response(
				200,
				json={
					"id": "itemXYZ",
					"name": "2024.xlsx",
					"webUrl": "https://contoso.sharepoint.com/reports/2024.xlsx",
					"size": 2048,
					"file": {},
				},
			)
		return httpx.Response(404)

	client, _ = make_client(handler)
	user = await client.users.get(id="u1")
	item_ref = user.drive.root.by_path("/Reports/2024.xlsx")
	data = await client.get(item_ref.path)
	item = DriveItem.from_graph(data, client=client, path=item_ref.path)

	assert item.id == "itemXYZ"
	assert item.name == "2024.xlsx"


@pytest.mark.asyncio
async def test_driveitem_get_by_path_rebases_workbook_path(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.url.path == "/v1.0/users/u1":
			return httpx.Response(200, json={"id": "u1"})
		if request.url.path == "/v1.0/users/u1/drive/root:/Reports/2024.xlsx":
			return httpx.Response(
				200,
				json={
					"id": "itemXYZ",
					"name": "2024.xlsx",
					"file": {},
				},
			)
		return httpx.Response(404)

	client, _ = make_client(handler)
	user = await client.users.get(id="u1")

	item = await user.drive.root.by_path("/Reports/2024.xlsx").get()

	assert item.path == "/users/u1/drive/items/itemXYZ"
	assert item.workbook.path == "/users/u1/drive/items/itemXYZ/workbook"


@pytest.mark.asyncio
async def test_driveitem_children(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.url.path == "/v1.0/users/u1":
			return httpx.Response(200, json={"id": "u1"})
		if request.url.path == "/v1.0/users/u1/drive/items/item123/children":
			return httpx.Response(
				200,
				json={
					"value": [
						{"id": "child1", "name": "DocA", "file": {}},
						{"id": "child2", "name": "DocB", "file": {}},
					]
				},
			)
		return httpx.Response(404)

	c, _ = make_client(handler)
	u = await c.users.get(id="u1")
	children = [c.id async for c in u.drive.root.by_id("item123").items]

	assert children == ["child1", "child2"]


@pytest.mark.asyncio
async def test_user_drive_root_items(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.url.path == "/v1.0/users/u1":
			return httpx.Response(200, json={"id": "u1"})
		if request.url.path == "/v1.0/users/u1/drive/root/children":
			return httpx.Response(
				200,
				json={
					"value": [
						{"id": "item1", "name": "Folder", "folder": {}},
						{"id": "item2", "name": "File.docx", "file": {}},
					]
				},
			)
		return httpx.Response(404)

	c, _ = make_client(handler)
	u = await c.users.get(id="u1")
	items = [i.id async for i in u.drive.root.items]
	assert items == ["item1", "item2"]


@pytest.mark.asyncio
async def test_driveitem_upload(make_client: "MakeClient"):
	seen = []

	def handler(request: httpx.Request) -> httpx.Response:
		seen.append(
			{
				"method": request.method,
				"path": request.url.path,
				"body": request.content,
				"headers": dict(request.headers),
			}
		)
		if request.url.path == "/v1.0/users/u1/drive/items/folder1:/hello.txt:/content":
			assert request.method == "PUT"
			return httpx.Response(
				201,
				json={"id": "file1", "name": "hello.txt", "size": 5, "file": {}},
			)
		return httpx.Response(404)

	client, _ = make_client(handler)
	folder = DriveItem.from_graph(
		{"id": "folder1", "name": "Folder", "folder": {"childCount": 0}},
		client=client,
		path="/users/u1/drive/items",
	)

	uploaded = await folder.upload("hello.txt", b"hello")

	assert isinstance(uploaded, DriveItem)
	assert any(
		entry["method"] == "PUT"
		and entry["path"] == "/v1.0/users/u1/drive/items/folder1:/hello.txt:/content"
			for entry in seen
	)


@pytest.mark.asyncio
async def test_driveitem_upload_from_path(make_client: "MakeClient", tmp_path):
	seen = []

	file_path = tmp_path / "hello.txt"
	file_path.write_text("hello from path", encoding="utf-8")

	def handler(request: httpx.Request) -> httpx.Response:
		seen.append(
			{
				"method": request.method,
				"path": request.url.path,
				"body": request.content,
			}
		)
		if request.url.path == "/v1.0/users/u1/drive/items/folder1:/hello.txt:/content":
			assert request.method == "PUT"
			assert request.content == b"hello from path"
			return httpx.Response(
				201,
				json={"id": "file1", "name": "hello.txt", "size": 15, "file": {}},
			)
		return httpx.Response(404)

	client, _ = make_client(handler)
	folder = DriveItem.from_graph(
		{"id": "folder1", "name": "Folder", "folder": {"childCount": 0}},
		client=client,
		path="/users/u1/drive/items",
	)

	uploaded = await folder.upload(file_path=str(file_path))

	assert isinstance(uploaded, DriveItem)
	assert any(
		entry["method"] == "PUT"
		and entry["path"] == "/v1.0/users/u1/drive/items/folder1:/hello.txt:/content"
			for entry in seen
	)


@pytest.mark.asyncio
async def test_driveitem_upload_then_by_path_get_rebases_child_path(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == "GET" and request.url.path == "/v1.0/users/u1/drive":
			return httpx.Response(
				200,
				json={
					"id": "drive123",
					"name": "User Drive",
					"driveType": "documentLibrary",
				},
			)
		if request.method == "GET" and request.url.path == "/v1.0/drives/drive123/root:/Unprocessed":
			return httpx.Response(
				200,
				json={
					"id": "folder1",
					"name": "Unprocessed",
					"folder": {"childCount": 1},
				},
			)
		if request.method == "PUT" and request.url.path == "/v1.0/drives/drive123/items/folder1:/report.xlsx:/content":
			return httpx.Response(
				201,
				json={
					"id": "file1",
					"name": "report.xlsx",
					"file": {},
				},
			)
		if request.method == "GET" and request.url.path == "/v1.0/drives/drive123/items/folder1:/report.xlsx":
			return httpx.Response(
				200,
				json={
					"id": "file1",
					"name": "report.xlsx",
					"file": {},
				},
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	folder = DriveItem(
		client=client,
		path="/users/u1/drive/root:/Unprocessed",
	)

	await folder.upload("report.xlsx", b"hello")
	drive_item = await folder.by_path("report.xlsx").get()

	assert folder.path == "/drives/drive123/items/folder1"
	assert drive_item.path == "/drives/drive123/items/file1"
	assert drive_item.workbook.path == "/drives/drive123/items/file1/workbook"


@pytest.mark.asyncio
async def test_driveitem_copy(make_client: "MakeClient"):
	seen = []

	def handler(request: httpx.Request) -> httpx.Response:
		seen.append(
			{
				"method": request.method,
				"path": request.url.path,
				"body": request.content,
			}
		)
		if request.url.path == "/v1.0/users/u1/drive/items/item123/copy":
			assert request.method == "POST"
			return httpx.Response(
				200,
				json={"id": "copy123", "name": "Doc1-copy", "file": {}},
			)
		return httpx.Response(404)

	client, _ = make_client(handler)
	item = DriveItem.from_graph(
		{"id": "item123", "name": "Doc1", "file": {}},
		client=client,
		path="/users/u1/drive/items",
	)

	copied = await item.copy(name="Doc1-copy", parent_id="destFolder")

	assert isinstance(copied, DriveItem)
	assert any(
		entry["method"] == "POST"
		and entry["path"] == "/v1.0/users/u1/drive/items/item123/copy"
			for entry in seen
	)


@pytest.mark.asyncio
async def test_driveitem_copy_with_parent_item(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.url.path == "/v1.0/users/u1/drive/items/item123/copy":
			return httpx.Response(
				200,
				json={"id": "copy123", "name": "Doc1-copy", "file": {}},
			)
		return httpx.Response(404)

	client, _ = make_client(handler)
	parent = DriveItem.from_graph(
		{"id": "parentFolder", "name": "Dest", "folder": {}},
		client=client,
		path="/users/u1/drive/items",
	)
	item = DriveItem.from_graph(
		{"id": "item123", "name": "Doc1", "file": {}},
		client=client,
		path="/users/u1/drive/items",
	)

	copied = await item.copy(parent_item=parent, drive_id="drive123")

	assert isinstance(copied, DriveItem)


@pytest.mark.asyncio
async def test_driveitem_move(make_client: "MakeClient"):
	seen = []

	def handler(request: httpx.Request) -> httpx.Response:
		seen.append(
			{
				"method": request.method,
				"path": request.url.path,
				"body": request.content,
			}
		)
		if request.url.path == "/v1.0/users/u1/drive/items/item123":
			if request.method == "PATCH":
				return httpx.Response(
					200, json={"id": "item123", "name": "Doc1", "file": {}}
				)
		return httpx.Response(404)

	client, _ = make_client(handler)
	dest = DriveItem.from_graph(
		{"id": "destFolder", "name": "Dest", "folder": {}},
		client=client,
		path="/users/u1/drive/items",
	)
	item = DriveItem.from_graph(
		{"id": "item123", "name": "Doc1", "file": {}},
		client=client,
		path="/users/u1/drive/items",
	)

	moved = await item.move(parent_item=dest, drive_id="drive123")

	assert isinstance(moved, DriveItem)
	assert any(
		entry["method"] == "PATCH"
		and entry["path"] == "/v1.0/users/u1/drive/items/item123"
			for entry in seen
	)


@pytest.mark.asyncio
async def test_driveitem_download(make_client: "MakeClient", tmp_path):
	seen = []

	def handler(request: httpx.Request) -> httpx.Response:
		seen.append(request.url.path)
		if request.url.path == "/v1.0/users/u1/drive/items/file1/content":
			return httpx.Response(200, content=b"hello")
		return httpx.Response(404)

	client, _ = make_client(handler)
	item = DriveItem.from_graph(
		{"id": "file1", "name": "file1.txt", "file": {}},
		client=client,
		path="/users/u1/drive/items",
	)

	dest = tmp_path / "file1.txt"
	data = await item.download(dest_path=dest)

	assert data == b"hello"
	assert dest.read_bytes() == b"hello"
	assert "/v1.0/users/u1/drive/items/file1/content" in seen


@pytest.mark.asyncio
async def test_driveitem_download_follows_redirect(make_client: "MakeClient", tmp_path):
	seen = []

	def handler(request: httpx.Request) -> httpx.Response:
		seen.append(str(request.url))
		if request.url.path == "/v1.0/users/u1/drive/items/file1/content":
			return httpx.Response(
				302,
				headers={"Location": "https://download.example.com/file1"},
			)
		if str(request.url) == "https://download.example.com/file1":
			return httpx.Response(200, content=b"redirected-data")
		return httpx.Response(404)

	client, _ = make_client(handler)
	item = DriveItem.from_graph(
		{"id": "file1", "name": "file1.txt", "file": {}},
		client=client,
		path="/users/u1/drive/items",
	)

	dest = tmp_path / "file1.txt"
	data = await item.download(dest_path=dest)

	assert data == b"redirected-data"
	assert dest.read_bytes() == b"redirected-data"
	assert "https://graph.microsoft.com/v1.0/users/u1/drive/items/file1/content" in seen
	assert "https://download.example.com/file1" in seen


@pytest.mark.asyncio
async def test_driveitem_get_site_path(make_client: "MakeClient"):
	seen = []

	def handler(request: httpx.Request) -> httpx.Response:
		seen.append(request.url.path)
		if request.url.path == "/v1.0/sites/contoso.sharepoint.com:/sites/Test:/drive":
			return httpx.Response(
				200,
				json={
					"id": "drive123",
					"name": "Test Drive",
					"driveType": "documentLibrary",
				},
			)
		if request.url.path == "/v1.0/drives/drive123/root:/Shared":
			return httpx.Response(
				200,
				json={"id": "item1", "name": "Shared", "folder": {}},
			)
		return httpx.Response(404)

	client, _ = make_client(handler)
	item = DriveItem(
		client=client,
		path="/sites/contoso.sharepoint.com:/sites/Test:/drive/root:/Shared",
	)

	resolved = await item.get()

	assert resolved.id == "item1"
	assert resolved.name == "Shared"
	assert resolved.path == "/drives/drive123/items/item1"
	assert "/v1.0/sites/contoso.sharepoint.com:/sites/Test:/drive" in seen
	assert "/v1.0/drives/drive123/root:/Shared" in seen


@pytest.mark.asyncio
async def test_drive_item_get_path_resolves_site_drive(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if request.method == "GET" and request.url.path == "/v1.0/sites/root":
			return httpx.Response(
				200,
				json={"siteCollection": {"hostname": "contoso.sharepoint.com"}},
			)
		if (
			request.method == "GET"
			and request.url.path
			== "/v1.0/sites/contoso.sharepoint.com/sites/test-site/drive"
		):
			return httpx.Response(200, json={"id": "drive-1", "name": "Drive"})
		if (
			request.method == "GET"
			and request.url.path == "/v1.0/drives/drive-1/root:/General"
		):
			return httpx.Response(
				200, json={"id": "item-1", "name": "General"}
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	item = DriveItem(
		client=client,
		path="/sites/HOSTNAME/sites/test-site/drive/root:/General",
	)
	resolved_path = await item._get_path()

	assert resolved_path == "/drives/drive-1/items/item-1"
	assert item.path == "/drives/drive-1/items/item-1"
	assert item.id == "item-1"
	assert item._graph_data["name"] == "General"


@pytest.mark.asyncio
async def test_drive_item_get_path_resolves_site_drive_colon(make_client: "MakeClient"):
	def handler(request: httpx.Request) -> httpx.Response:
		if (
			request.method == "GET"
			and request.url.path
			== "/v1.0/sites/contoso.sharepoint.com:/sites/test-site:/drive"
		):
			return httpx.Response(200, json={"id": "drive-2", "name": "Drive"})
		if (
			request.method == "GET"
			and request.url.path == "/v1.0/drives/drive-2/root:/General"
		):
			return httpx.Response(
				200, json={"id": "item-2", "name": "General"}
			)
		raise AssertionError(f"Unexpected request: {request.method} {request.url}")

	client, _ = make_client(handler)
	item = DriveItem(
		client=client,
		path="/sites/contoso.sharepoint.com:/sites/test-site:/drive/root:/General",
	)
	resolved_path = await item._get_path()

	assert resolved_path == "/drives/drive-2/items/item-2"
	assert item.path == "/drives/drive-2/items/item-2"
	assert item.id == "item-2"
	assert item._graph_data["name"] == "General"
