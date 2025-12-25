from typing import Any
from pymsgraph.query import PY_LOOKUP_TO_ODATA_QUERY, odata_literal


def _group_types(lookup: str, value: str) -> str:
    # /groups?$filter=groupTypes/any(c:c+eq+'Unified')
    func_mapping = {
        "exact": lambda x: (
            PY_LOOKUP_TO_ODATA_QUERY["exact"]("groupTypes/any(u:u", x) + ")"
        )
    }

    if func := func_mapping.get(lookup):
        return func(value)
    raise ValueError(f"Unsupported lookup for licenses: {lookup!r}")
