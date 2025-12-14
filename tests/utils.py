from __future__ import annotations

import json
import httpx


def read_json(request: httpx.Request) -> dict:
    if not request.content:
        return {}
    return json.loads(request.content.decode("utf-8"))
