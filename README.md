> **Disclaimer**
> This project is an independent implementation for Microsoft Graph and is not sponsored, endorsed, or affiliated with Microsoft. Feature coverage is intentionally partial and may change as Microsoft Graph and this library evolve. Validate behavior in your environment and apply appropriate testing, security controls, and version pinning before production use.

# pymsgraph

Python client for Microsoft Graph with Django-style query syntax

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue.svg)](https://rynldtbuen.github.io/pymsgraph/)
[![Docs Workflow](https://github.com/rynldtbuen/pymsgraph/actions/workflows/docs.yml/badge.svg)](https://github.com/rynldtbuen/pymsgraph/actions/workflows/docs.yml)

### Prerequisites

- Python `3.12+`
- Access to a Microsoft Entra app registration
- Microsoft Graph permissions appropriate for the operations you plan to run

### Install from source

`pymsgraph` is not yet published to PyPI.

```bash
git clone https://github.com/rynldtbuen/pymsgraph.git
cd pymsgraph
python -m venv .venv
```

Windows (PowerShell):

```bash
.venv\Scripts\activate
pip install -e .
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -e .
```

### Configure athentication

`pymsgraph` accepts a token provider with `get_access_token(...)`.

Built-in providers:

- `ConfidentialClientAuth`: app-only/client-credentials flow
- `PublicClientAuth`: delegated flow (interactive or cached sign-in)

#### Using app-only (Confidential Client)

Set environment variables:

- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`

```python
from pymsgraph.auth import ConfidentialClientAuth

provider = ConfidentialClientAuth(
    tenant_id=os.environ["AZURE_TENANT_ID"],
    client_id=os.environ["AZURE_CLIENT_ID"],
    client_secret=os.environ["AZURE_CLIENT_SECRET"],
)
```

#### Using delegated (Public Client)

Set environment variables:

- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`

```python
from pymsgraph.auth import PublicClientAuth

provider = PublicClientAuth(
    tenant_id=os.environ["AZURE_TENANT_ID"],
    client_id=os.environ["AZURE_CLIENT_ID"],
    default_scopes=["User.Read"],
)
```

### Example

```python
import asyncio
import logging
import os

from pymsgraph.auth import ConfidentialClientAuth
from pymsgraph.client import Client


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    provider = ConfidentialClientAuth(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"],
    )

    async with Client(provider) as graph:
        # 1) Fetch one user by object ID or UPN.
        user = await graph.users.get(id="alice@contoso.com")
        print(user.id, user.display_name, user.mail)

        # 2) Build a lazy queryset.
        enabled_users_qs = (
            graph.users
            .filter(account_enabled=True)
            .select("display_name", "mail")
            .order_by("display_name")
            .top(10)
        )

        # 3) Execute by iterating/materializing.
        enabled_users = [u async for u in enabled_users_qs]
        for u in enabled_users:
            print(u.display_name, u.mail)


if __name__ == "__main__":
    asyncio.run(main())
```