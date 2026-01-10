# from __future__ import annotations
# from typing import TYPE_CHECKING

# from pymsgraph.models.query import Q, QuerySet

# if TYPE_CHECKING:
#     from .conftest import MakeClient


# class DummyClient:
#     pass


# class DummyModel:
#     pass


# def make_qs() -> QuerySet[DummyModel]:  # pyright: ignore[reportInvalidTypeArguments]
#     # ctx = Context(, model_class=DummyModel, endpoint="/dummy")
#     return QuerySet(DummyClient())


# def test_queryset_filter_single() -> None:
#     qs = make_qs().filter(display_name="Alice")
#     params = qs._build_params()
#     assert params["$filter"] == "(displayName eq 'Alice')"


# def test_queryset_filter_multiple() -> None:
#     qs = make_qs().filter(display_name="Alice", mail="a@x.com")
#     params = qs._build_params()
#     filt = params["$filter"]
#     assert "displayName eq 'Alice'" in filt
#     assert "mail eq 'a@x.com'" in filt
#     assert " and " in filt


# def test_queryset_filter_dup() -> None:
#     qs = make_qs().filter(display_name="Alice", mail="a@x.com").filter(mail="a@x.com")
#     params = qs._build_params()
#     filt = params["$filter"]
#     assert "displayName eq 'Alice'" in filt
#     assert "mail eq 'a@x.com'" in filt
#     assert " and " in filt
#     assert len(qs._params["$filter"]) == 2


# def test_queryset_filter_q_or_with_kwargs() -> None:
#     qs = make_qs().filter(Q(display_name="A") | Q(mail="a@x.com"), account_enabled=True)
#     params = qs._build_params()
#     filt = params["$filter"]
#     assert "displayName eq 'A'" in filt
#     assert "mail eq 'a@x.com'" in filt
#     assert " or " in filt
#     assert "accountEnabled eq true" in filt
#     assert " and " in filt
#     assert (
#         filt
#         == "((displayName eq 'A') or (mail eq 'a@x.com')) and (accountEnabled eq true)"
#     )


# def test_queryset_filter_q_not() -> None:
#     qs = make_qs().filter(~Q(display_name="A"))
#     params = qs._build_params()
#     assert params["$filter"] == "(not (displayName eq 'A'))"


# def test_queryset_select_collects_fields() -> None:
#     qs = make_qs().select("display_name", "mail")
#     params = qs._build_params()
#     assert params["$select"] == "displayName,mail"


# def test_queryset_select_dedupes_fields() -> None:
#     qs = make_qs().select("display_name", "mail").select("display_name")
#     params = qs._build_params()
#     assert params["$select"] == "displayName,mail"


# def test_queryset_order_by_single() -> None:
#     qs = make_qs().order_by("display_name")
#     params = qs._build_params()
#     assert params["$orderby"] == "displayName"


# def test_queryset_order_by_desc() -> None:
#     qs = make_qs().order_by("-display_name")
#     params = qs._build_params()
#     assert params["$orderby"] == "displayName desc"


# def test_queryset_order_by_multiple() -> None:
#     qs = make_qs().order_by("display_name", "-mail")
#     params = qs._build_params()
#     assert params["$orderby"] == "displayName,mail desc"


# def test_queryset_expand_single() -> None:
#     qs = make_qs().expand("manager", "display_name", "department")
#     params = qs._build_params()
#     assert params["$expand"] == "manager($select=department,displayName)"


# def test_queryset_expand_multiple() -> None:
#     qs = (
#         make_qs()
#         .expand("manager", "display_name", "department")
#         .expand("member_of", "display_name", "mail")
#     )
#     params = qs._build_params()
#     assert params["$expand"] == (
#         "manager($select=department,displayName),memberOf($select=displayName,mail)"
#     )


# def test_queryset_search_with_q_and_kwargs() -> None:
#     params = make_qs().search(display_name="A")._build_params()
#     assert params["$search"] == '"displayName:A"'

#     params = make_qs().search(display_name="A", description="B")._build_params()
#     assert params["$search"] == '"displayName:A" AND "description:B"'

#     params = (
#         make_qs()
#         .search(Q(display_name="A") | Q(display_name="B"), description="C")
#         ._build_params()
#     )
#     assert (
#         params["$search"] == '("displayName:A" OR "displayName:B") AND "description:C"'
#     )
