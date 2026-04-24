# leapmotor-api

Unofficial Python client for the Leapmotor vehicle cloud API.

Extracted from the [leapmotor-ha](https://github.com/kerniger/leapmotor-ha) Home Assistant integration
to provide a reusable, framework-agnostic library.

## Installation

```bash
pip install leapmotor-api
```

## Quick Start

```python
from leapmotor_api import LeapmotorApiClient

client = LeapmotorApiClient(
    username="user@example.com",
    password="password",
    app_cert_path="/path/to/app_cert.pem",
    app_key_path="/path/to/app_key.pem",
    language="it-IT",  # default: en-GB
)

client.login()
data = client.fetch_data()

for vin, vehicle in data["vehicles"].items():
    print(f"{vin}: {vehicle['status']['battery_percent']}% battery")

client.close()
```

## Async Usage

```python
from leapmotor_api import LeapmotorApiClient
from leapmotor_api.async_client import AsyncLeapmotorApiClient

sync_client = LeapmotorApiClient(
    username="user@example.com",
    password="password",
    app_cert_path="/path/to/app_cert.pem",
    app_key_path="/path/to/app_key.pem",
    language="it-IT",
)
client = AsyncLeapmotorApiClient(sync_client)

await client.login()
data = await client.fetch_data()
await client.close()
```

## Remote Control

Remote actions require the vehicle PIN:

```python
client = LeapmotorApiClient(
    username="user@example.com",
    password="password",
    app_cert_path="/path/to/app_cert.pem",
    app_key_path="/path/to/app_key.pem",
    operation_password="1234",
    language="de-DE",
)

client.login()
client.lock_vehicle("WLM...")
client.unlock_vehicle("WLM...")
client.open_trunk("WLM...")
client.close()
```

## License

MIT

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `username` | `str` | — | Leapmotor account email |
| `password` | `str` | — | Leapmotor account password |
| `app_cert_path` | `str` | — | Path to app certificate PEM |
| `app_key_path` | `str` | — | Path to app private key PEM |
| `operation_password` | `str \| None` | `None` | Vehicle PIN (required for remote control) |
| `language` | `str` | `"en-GB"` | API language (`en-GB`, `it-IT`, `de-DE`, `fr-FR`, …) |
| `verify_ssl` | `bool` | `False` | Verify server TLS certificate |
| `base_url` | `str` | `DEFAULT_BASE_URL` | API base URL |
| `timeout` | `int` | `30` | HTTP timeout in seconds |
| `device_id` | `str \| None` | `None` | Custom device ID (auto-generated if omitted) |
