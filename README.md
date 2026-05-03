# leapmotor-api

Unofficial Python client for the Leapmotor vehicle cloud API.

Extracted from the [leapmotor-ha](https://github.com/kerniger/leapmotor-ha) Home Assistant integration
to provide a reusable, framework-agnostic library.

## Acknowledgments

Special thanks to [Jakob Kern](https://github.com/kerniger) for the impressive reverse engineering work on the Leapmotor application and for generously sharing his work.

## Installation

```bash
pip install leapmotor-api
```

## Certificates

The library requires the Leapmotor app certificate and private key to authenticate API requests.
You can download them from the dedicated repository:

```bash
wget https://github.com/markoceri/leapmotor-certs/archive/refs/tags/v1.0.0.zip
unzip v1.0.0.zip
```

The extracted folder contains `app_cert.pem` and `app_key.pem`. Pass their paths to the client via the `app_cert_path` and `app_key_path` parameters.

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
vehicles = client.get_vehicle_list()

for vehicle in vehicles:
    print(f"{vehicle.vin} ({vehicle.car_type}) — {vehicle.vehicle_nickname}")
    status = client.get_vehicle_status(vehicle)
    print(f"  Battery: {status.battery.soc}%")
    print(f"  Range: {status.battery.expected_mileage} km")
    print(f"  Odometer: {status.driving.total_mileage} km")

client.close()
```

## Typed Models vs Raw Data

The library exposes two ways to access vehicle data:

### Typed models (recommended)

`get_vehicle_status()` returns a `VehicleStatus` dataclass with typed sub-objects:

```python
status = client.get_vehicle_status(vehicle)

# Battery & charging
status.battery.soc                  # int | None — state of charge %
status.battery.expected_mileage     # int | None — remaining range km
status.battery.charge_state         # ChargeState | None — NOT_CONNECTED, AC_CONNECTED, DC_CONNECTED
status.battery.is_charging          # bool | None
status.battery.is_discharging       # bool | None
status.battery.charging_power_kw    # float | None
status.battery.discharging_power_kw # float | None
status.battery.battery_power        # float | None — power in kW (voltage × current)
status.battery.dump_energy_kwh      # float | None — available energy in kWh
status.battery.battery_voltage      # float | None
status.battery.battery_current      # float | None
status.battery.charge_remain_time   # int | None — minutes remaining
status.battery.charge_soc_setting   # int | None — charge limit %

# Driving
status.driving.total_mileage        # int | None — odometer km
status.driving.speed                # int | None
status.driving.gear_status          # int | None
status.driving.is_parked            # bool | None

# Location
status.location.latitude            # float | None
status.location.longitude           # float | None

# Climate
status.climate.ac_switch            # bool | None
status.climate.ac_setting           # float | None — target temperature
status.climate.ac_air_volume        # int | None
status.climate.outdoor_temp         # int | None
status.climate.ptc_state            # int | None

# Doors & locks
status.doors.is_locked              # bool | None
status.doors.bbcm_back_door_status  # bool | None — trunk

# Windows
status.windows.left_front_window_percent   # int | None
status.windows.right_front_window_percent  # int | None
status.windows.left_rear_window_percent    # int | None
status.windows.right_rear_window_percent   # int | None
status.windows.sun_shade                   # int | None

# Tire pressure
status.tires.front_left_bar         # float | None — pressure in bar
status.tires.front_right_bar        # float | None
status.tires.rear_left_bar          # float | None
status.tires.rear_right_bar         # float | None
status.tires.all_ok                 # bool | None — all pressures normal
status.tires.all_bar                # dict[str, float | None]

# Connectivity
status.connectivity.bluetooth_state # bool | None
status.connectivity.hotspot_state   # bool | None

# Ignition
status.ignition.bcm_key_position_on1  # bool | None
status.ignition.bcm_key_position_on3  # bool | None

# Top-level convenience properties
status.is_locked                    # bool | None
status.is_charging                  # bool | None — plugged in, parked, and charging
status.is_regening                  # bool | None — regenerative braking
status.is_parked                    # bool | None
status.tire_pressure_bar            # dict[str, float | None]

# Timestamps
status.collect_time                 # datetime | None
status.create_time                  # datetime | None
```

### Raw API data

For forward-compatibility or debugging, use `get_vehicle_raw_status()`:

```python
raw = client.get_vehicle_raw_status(vehicle)
# Returns the full API JSON dict with signal codes, config, etc.
# raw["data"]["signal"]["1204"]  → battery SOC
# raw["data"]["config"]["3"]     → charging plan
```

The `VehicleStatus` object also retains the raw dict in `status.raw` for convenience.

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
vehicles = await client.get_vehicle_list()
status = await client.get_vehicle_status(vehicles[0])
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
client.close_trunk("WLM...")
client.find_vehicle("WLM...")
client.open_windows("WLM...")
client.close_windows("WLM...")
client.ac_switch("WLM...")
client.quick_cool("WLM...")
client.quick_heat("WLM...")
client.windshield_defrost("WLM...")
client.open_sunshade("WLM...")
client.close_sunshade("WLM...")
client.battery_preheat("WLM...")
client.set_charge_limit("WLM...", charge_limit_percent=80)
client.close()
```

## Token Management

The Leapmotor API tokens expire after ~20 minutes. The client handles this **automatically**: all public methods detect expired-token errors and transparently refresh the token (or fall back to a full re-login if the refresh token has also expired).

You can also manage token refresh manually:

```python
# Explicit refresh (rotates token + refresh token, reuses sign material)
client.token_refresh()

# Async
await client.token_refresh()
```

No configuration is needed — the `refreshToken` is obtained during `login()` and rotated on each refresh call.

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
