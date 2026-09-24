# leapmotor-api

[![PyPI version](https://img.shields.io/pypi/v/leapmotor-api)](https://pypi.org/project/leapmotor-api/)
[![Python versions](https://img.shields.io/pypi/pyversions/leapmotor-api)](https://pypi.org/project/leapmotor-api/)
[![License](https://img.shields.io/github/license/markoceri/leapmotor-api)](https://github.com/markoceri/leapmotor-api/blob/main/LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/leapmotor-api)](https://pypi.org/project/leapmotor-api/)
[![CI](https://github.com/markoceri/leapmotor-api/actions/workflows/ci.yml/badge.svg)](https://github.com/markoceri/leapmotor-api/actions)
[![codecov](https://codecov.io/gh/markoceri/leapmotor-api/graph/badge.svg)](https://codecov.io/gh/markoceri/leapmotor-api)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/type--checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20me-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/markoceri)

Unofficial Python client for the Leapmotor vehicle cloud API.

Extracted from the [leapmotor-ha](https://github.com/kerniger/leapmotor-ha) Home Assistant integration
to provide a reusable, framework-agnostic library.

## Acknowledgments

Special thanks to [Jakob Kern](https://github.com/kerniger) for the impressive reverse engineering work on the Leapmotor application and for generously sharing his work.

## Installation

```bash
pip install leapmotor-api
```

### Certificates

The library requires the Leapmotor app certificate and private key to authenticate API requests.
Download them from the dedicated repository:

```bash
wget https://github.com/markoceri/leapmotor-certs/archive/refs/tags/v1.0.0.zip
unzip v1.0.0.zip
```

The extracted folder contains `app_cert.pem` and `app_key.pem`. Pass their paths to the client via `app_cert_path` and `app_key_path`.

## Quick Start

```python
from leapmotor_api import LeapmotorApiClient

client = LeapmotorApiClient(
    username="user@example.com",
    password="password",
    app_cert_path="/path/to/app_cert.pem",
    app_key_path="/path/to/app_key.pem",
)

client.login()
vehicles = client.get_vehicle_list()

for vehicle in vehicles:
    status = client.get_vehicle_status(vehicle)
    print(f"{vehicle.vin} — Battery: {status.battery.soc}% — Range: {status.battery.expected_mileage} km")

client.close()
```

### Async Usage

```python
from leapmotor_api import LeapmotorApiClient
from leapmotor_api.async_client import AsyncLeapmotorApiClient

sync_client = LeapmotorApiClient(
    username="user@example.com",
    password="password",
    app_cert_path="/path/to/app_cert.pem",
    app_key_path="/path/to/app_key.pem",
)
client = AsyncLeapmotorApiClient(sync_client)

await client.login()
vehicles = await client.get_vehicle_list()
status = await client.get_vehicle_status(vehicles[0])
await client.close()
```

## Vehicle Status

`get_vehicle_status()` returns a `VehicleStatus` dataclass with typed sub-objects:

| Sub-object | Key fields |
|---|---|
| `status.battery` | `soc`, `expected_mileage`, `charge_state`, `is_charging`, `is_charge_fast_gun_insert`, `is_charge_slow_gun_insert`, `charging_power_kw`, `battery_power`, `dump_energy_kwh`, `charge_plan.*` |
| `status.driving` | `speed`, `total_mileage`, `gear_status`, `is_parked` |
| `status.location` | `latitude`, `longitude` |
| `status.climate` | `ac_switch`, `ac_setting`, `outdoor_temp`, `interior_temp`, `ac_operate_mode`, `ac_air_volume`, `ac_cooling_and_heating` |
| `status.doors` | `is_locked`, `bbcm_back_door_status` |
| `status.windows` | `left_front_window_percent`, `right_front_window_percent`, `sun_shade` |
| `status.tires` | `front_left_bar`, `front_right_bar`, `rear_left_bar`, `rear_right_bar`, `all_ok` |
| `status.connectivity` | `bluetooth_state`, `hotspot_state` |
| `status.seat_comfort` | `driver_seat_heating`, `driver_seat_ventilation`, `steering_wheel_heating` |
| `status.security` | `vehicle_security_active`, `sentry_mode`, `roof_opening` |
| `status.ignition` | `bcm_key_position_on1`, `bcm_key_position_on3` |

Top-level convenience properties: `status.is_locked`, `status.is_plugged`, `status.is_charging`, `status.is_parked`, `status.is_driving`, `status.is_regening`, `status.tire_pressure_bar`.

All fields are `T | None` — they are populated only when the vehicle reports the corresponding signal.

For raw API data, use `get_vehicle_raw_status()` or access `status.raw`.

## Charging History

```python
from datetime import date, timedelta

result = client.get_charging_daily_detail(
    vehicle.vin,
    start_time=date.today() - timedelta(days=90),
    end_time=date.today(),
    timezone="GMT+01:00",
    page_size=50,
)
for record in result.records:
    charge_kind = "DC (fast)" if record.is_fast_charge else "AC (normal)"
    print(f"{record.start_datetime} -> {record.end_datetime}  {charge_kind}  {record.energy_kwh} kWh")
```

`ChargeRecord` fields: `start_ts`, `end_ts`, `charge_type` (`ChargeType.AC` / `ChargeType.DC`), `energy_kwh`, `longitude`, `latitude`, `timezone`.  
Convenience properties: `start_datetime`, `end_datetime`, `duration_seconds`, `is_fast_charge`.

## Energy Consumption Statistics

```python
# Last week energy breakdown (driving, A/C, other)
breakdown = client.get_consumption_last_week_breakdown(vehicle)
print(f"Driver: {breakdown.driver_ec} kWh, AC: {breakdown.ac_ec} kWh, Other: {breakdown.other_ec} kWh")
print(f"Total: {breakdown.total_ec} kWh")

# Six-week consumption history and ranking
weekly_rank = client.get_consumption_weekly_rank(vehicle)
print(f"Rank: {weekly_rank.rank.rank}, Avg: {weekly_rank.rank.hundred_km_ec} kWh/100km")
for week in weekly_rank.weekly:
    print(f"  {week.week_start} ~ {week.week_end}: {week.hundred_km_ec} kWh/100km")
```

## Vehicle Permissions

The `Vehicle` object exposes the Leapmotor 3-tier permission system as typed enums:

| Field | Type | Description |
|---|---|---|
| `vehicle.abilities` | `list[VehicleAbility]` | Hardware feature flags (what the vehicle can do) |
| `vehicle.rights` | `list[VehicleRight]` | Remote command permissions (what the account can execute) |
| `vehicle.module_rights` | `list[ModuleRight]` | Macro sharing categories |

```python
from leapmotor_api import VehicleAbility, VehicleRight

vehicle = vehicles[0]

# Check capabilities
if vehicle.has_right(VehicleRight.WINDOWS):
    client.open_windows(vehicle.vin)

if vehicle.has_ability(VehicleAbility.NAVIGATION):
    client.send_destination(vehicle.vin, ...)

# Inspect permissions
for right in vehicle.rights:
    print(f"{right.name} ({right.value}): {right.description}")
```

Remote commands automatically log a warning when the vehicle may lack the required permission, but still proceed (the server enforces permissions authoritatively).

## Remote Control

Remote actions require the vehicle PIN (`operation_password`):

```python
client = LeapmotorApiClient(..., operation_password="1234")
client.login()

client.lock_vehicle("WLM...")
client.unlock_vehicle("WLM...")
client.open_trunk("WLM...")
client.close_trunk("WLM...")
client.find_vehicle("WLM...")
client.hotspot("WLM...")
client.autopark("WLM...")
client.open_windows("WLM...")
client.close_windows("WLM...")
client.ac_on("WLM...")
client.ac_off("WLM...")
client.ac_switch("WLM...")
client.quick_cool("WLM...")
client.quick_heat("WLM...")
client.windshield_defrost("WLM...")
client.open_sunshade("WLM...")
client.close_sunshade("WLM...")
client.battery_preheat("WLM...")
client.battery_preheat_off("WLM...")
client.sentry_mode_on("WLM...")
client.sentry_mode_off("WLM...")
client.start_charging("WLM...")
client.stop_charging("WLM...")
client.steering_wheel_heat_on("WLM...")
client.steering_wheel_heat_off("WLM...")
client.fuel_heating_on("WLM...")
client.fuel_heating_off("WLM...")
client.rearview_mirror_heat_on("WLM...")
client.rearview_mirror_heat_off("WLM...")
client.healthy_charging_on("WLM...")
client.healthy_charging_off("WLM...")
client.on3_on("WLM...")
client.on3_off("WLM...")
client.ble_key_restart("WLM...")
client.music("WLM...", operation="play")
client.video("WLM...", operation="play")
client.fota_download("WLM...", task_id=123)
client.fota_install("WLM...", task_id=123)
client.fota_schedule("WLM...", task_id=123, schedule_time="2026-05-13T10:00:00")
client.rear_seats("WLM...", seat_info="fold")
client.prepare_car("WLM...", params={"temperature": "24"})
# Schedule prepare-car (cmd 361) — full-state replacement; [] cancels all
client.set_prepare_car_schedule("WLM...", controls=[{
    "datacontent": {"air_condition": {"mode": "cold", "temperature": "18", "circle": "in",
                                       "windlevel": "7", "wshld": "1", "operate": "manual",
                                       "position": "all", "enable": True}},
    "days": [1, 2, 3, 4, 5], "enable": True,
    "set_id": "ios_<hash><epoch>", "start_time": "2026-06-17 07:30:00",
}])
client.cancel_prepare_car_schedule("WLM...")
client.seat_adjust("WLM...", params={"position": "driver"})
client.piloted_parking("WLM...", params={"action": "start"})
client.set_speed_limit("WLM...", value="80")
client.seat_heat("WLM...", position=3, level=3)
client.seat_ventilation("WLM...", position=3, level=2)
client.open_sunroof("WLM...")
client.close_sunroof("WLM...")
client.set_charge_limit("WLM...", charge_limit_percent=80)
client.set_charge_schedule(
    "WLM...",
    enabled=True,
    soc_limit=80,
    start_time="23:00",
    end_time="07:00",
    cycles="1,2,3,4,5,6,7",
    circulation=1,
)
client.unlock_charger("WLM...")
```

> [!NOTE]
> The `recharge` field of the charge schedule (`get_charge_schedule` / `set_charge_schedule`) mirrors the official app's **"resume charging if schedule is missed"** toggle — it makes the vehicle resume/retry charging if it's unplugged or falls outside the configured time window, instead of waiting for the next scheduled cycle. Confirmed against a real vehicle: toggling that setting in the app changed only this field between two consecutive `get_charge_schedule` calls (`recharge: 0` -> `recharge: 1`, all other fields unchanged).

> [!TIP]
> Consider creating a **shared/secondary account** in the Leapmotor app and sharing the vehicle with it. This avoids conflicts with your primary account sessions (e.g. being logged out from the phone app or **temporary account locks** on Leapmotor's servers).

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

Token refresh is handled **automatically** — all methods detect expired tokens and transparently refresh or re-login. See `token_refresh()` for manual control.

## Documentation

- [API Reference](docs/api.md) — endpoints, cryptography and remote commands
- [Vehicle Model Differences](docs/vehicles.md) — API response format and signal IDs across vehicle models

## Contributing

Interested in contributing? Read the [contributing guide](CONTRIBUTING.md) for development setup, testing, and PR guidelines.

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).