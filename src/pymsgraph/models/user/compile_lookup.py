from typing import Any
from pymsgraph.query import PY_LOOKUP_TO_ODATA_QUERY, odata_literal


def _licenses(lookup: str, value: Any) -> str:
    def _isnull():
        if not isinstance(value, bool):
            raise ValueError(f"Value is not an instance of bool, {value!r}")

        if value:
            return f"assignedLicenses/$count eq 0"
        return f"assignedLicenses/$count ne 0"

    def _sku_id__exact():
        return (
            PY_LOOKUP_TO_ODATA_QUERY["exact"]("assignedLicenses/any(u:u/skuId", value)
            + ")"
        )

    func_mapping = {
        "isnull": _isnull,
        "sku_id": _sku_id__exact,
        "sku_id__exact": _sku_id__exact,
    }

    if func := func_mapping.get(lookup):
        return func()
    raise ValueError(f"Unsupported lookup for licenses: {lookup!r}")
