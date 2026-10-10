# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- `ac_off()` now powers the A/C off on the T03 and on the B10/C10 ([#9](https://github.com/markoceri/leapmotor-api/issues/9)). It used to send `operate=close`, which the cloud accepts (`code=0`) but neither model executes: the B10 only switches the HVAC to AUTO and the T03 ignores it. It now sends `operate=off`: inside the full climate body on the T03, as the bare `{"operate":"off"}` on every other model. The payload is chosen from the target vehicle's `carType` through the new `REMOTE_ACTION_CAR_TYPE_SPECS` mapping.
- Fixed West/South cars jumping to the wrong hemisphere between polls on signal-based vehicles ([#17](https://github.com/markoceri/leapmotor-api/issues/17)). The 0.3.2 fix prefers the signed signals `2`/`3`, but the cloud sometimes omits them and occasionally puts the absolute value in them. The new `HemisphereGuard`, applied by `get_vehicle_status()`, remembers the last trusted sign per VIN: a negative reading is always trusted, an absolute-value reading gets the remembered sign back, and a positive signed reading that contradicts it is accepted only near the last trusted position or after 3 distinct frames in a row agree. The memory is in-process; persist it with `client.hemisphere_guard.export_state()` and restore it with `LeapmotorApiClient(hemisphere_guard=HemisphereGuard(state))`. Thanks to @ProtossBlaster for the analysis.

### Added
- `ClimateOperate.OFF` (`"off"`) and `RemoteActionCtlClimateOff`, the bare `{"operate":"off"}` climate command.
- Windowed cloud statistics ([#10](https://github.com/markoceri/leapmotor-api/issues/10)), on both clients. Both take timezone-aware `start` / `end` datetimes and reject naive or inverted windows with `ValueError`.
  - `get_mileage_energy_history(vehicle, start=, end=)` returns a `MileageEnergyHistory`: the lifetime `total_energy_kwh` (the cloud's `totalEnergy`, standby included), the mileage over the window and a per-day `DailyMileageEnergy` list. It calls `mileage/energy/detail` with a signed millisecond window; the existing `get_mileage_energy_detail()` is unchanged. The per-day energy is coarse; `total_energy_kwh` is the precise figure.
  - `get_consumption_breakdown(vehicle, start=, end=)` returns the driving / A/C / other split from `getLastweekEC` for any window instead of only the previous week.

  Thanks to @kerniger, whose `leapmotor-ha` already used the windowed request, and to @ProtossBlaster for mapping both endpoints on a B10.
- `get_share_invitations()`, `accept_share_invitation(invitation)` and `reject_share_invitation(invitation)` ([#20](https://github.com/markoceri/leapmotor-api/pull/20)): the recipient side of car sharing (`/sharecar/getsharemsg`, `/sharecar/setokmsg`), with a `ShareInvitation` model. Until an invitation is accepted the shared car is absent from `get_vehicle_list()` and vehicle calls fail with `No such permission`; so far the only way to accept was the official app. Also exposed on the async client. Verified end-to-end on a B10. Thanks to @arekm.
- Tire pressure in PSI ([#14](https://github.com/markoceri/leapmotor-api/issues/14)): `TirePressure.front_left_psi` / `front_right_psi` / `rear_left_psi` / `rear_right_psi`, the `all_psi` dict and `VehicleStatus.tire_pressure_psi`, alongside the existing bar conversion. The raw kPa values are unchanged. Thanks to @ASchneiderBR.
- `LocationStatus.latitude_signed` / `longitude_signed`: whether a signal-based coordinate came from the signed signals (`3`/`2`) or from an absolute-value fallback.
- Vehicle status falls back to the shared C10 endpoint when a model's own segment answers HTTP 404 (as the B05 did before it was mapped). The fallback is remembered per model for the client's lifetime, logs a one-time warning asking for a report, and is recorded in `last_api_results` as `vehicle status c10 fallback` next to the original 404. If C10 also fails, the error names both segments tried. Other errors are unchanged.

### Changed
- `ConsumptionLastWeekBreakdown` is renamed `ConsumptionBreakdown`; the old name remains as an alias. `get_consumption_last_week_breakdown()` now goes through the same code path as `get_consumption_breakdown()` and keeps its `last_api_results` key.
- `mappings.CAR_TYPE_PATH_MAP` is now the single source for vehicle status path mapping: `CarType.status_path` reads it, and the client resolves the path through `CarType.status_path`. The duplicate `models._CAR_TYPE_STATUS_PATH` was removed. `docs/vehicles.md` now lists `/status/get/c10` for the B05.

## [0.3.3] - 2026-10-08

### Fixed
- Fixed vehicle status failing on the **B05** ([#18](https://github.com/markoceri/leapmotor-api/issues/18)). Like the B10 and B11, it shares the C10 status endpoint: `/status/get/b05` is answered with `No message available` (HTTP 404) while login, vehicle list, abilities and commands all succeed. `CAR_TYPE_PATH_MAP` and `CarType.status_path` now map B05 → C10, and a test keeps the two mappings in sync. Thanks to @kerniger (#15) and @ProtossBlaster (#16).
- Fixed the dynamic car image compositing the open rear tailgate (`carpic_tailgate_open.png`) on top of the vehicle. The layer is now rendered in the background (below the body) so the open hatch no longer overlaps the car and only the protruding portion is visible.

### Added
- Added REEV range estimation fields ([#11](https://github.com/markoceri/leapmotor-api/issues/11), [#12](https://github.com/markoceri/leapmotor-api/pull/12)): `BatteryStatus.expected_fuel_mileage` / `expected_combined_mileage` (signals `3259` / `3261`) and `DrivingStatus.max_fuel_range` / `max_combined_range` (signals `3256` / `3258`). Thanks to @miguelprates.

## [0.3.2] - 2026-06-22

### Fixed
- Fixed GPS coordinates losing the hemisphere sign on signal-based vehicles (B10/C10), placing West-longitude cars (Portugal/UK) in the wrong hemisphere ([#21](https://github.com/markoceri/leapconnect/issues/21)). The signals used so far (`3724`/`3725`, with fallbacks `2191`/`2190`) carry the coordinate as an absolute value, dropping the West/South sign. Now the signed signals `2` (longitude) / `3` (latitude) take priority, falling back to the absolute-value signals only when absent.
- Fixed `set_charge_limit()` resetting the start time to `00:00` and disabling the schedule when an active charge plan exists ([#18](https://github.com/markoceri/leapconnect/issues/18)). For an enabled start-time-only plan the cloud omits `cycles`/`endtime`/`recharge`, so guarding the read-modify-write on `cycles` routed it into the all-defaults branch. Now preserves every field the response includes (notably `starttime` and `chargeEnable`) and falls back per-field only for the genuinely missing ones; only `chargesoc` changes.

### Documentation
- Documented that the window command (cmd 230) value is 0–100 on C10/T03 but a **B10** uses a 0–10 scale (actuating only `0/2/5/10`; other values are accepted by the cloud but ignored by the car) — observed on-car. Noted on `RemoteActionCtlWindows` and `windows()`.

### Added
- `set_prepare_car_schedule(vin, controls=[...])` and `cancel_prepare_car_schedule(vin)` — write support for the one-touch prepare-car schedule (cmd 361), the schedule counterpart of `prepare_car()` (cmd 360). Mirrors `set_climate_schedule`: a full-state replacement where an empty `controls` list cancels every entry. Also exposed on the async client. Reverse-engineered and verified end-to-end on a B10 (#6).

## [0.3.1] - 2026-05-28

### Fixed
- Fixed `set_charge_limit()` failing on vehicles (e.g. T03) where `status.battery.charge_plan` is empty — now fetches the current schedule via `get_charge_schedule(vin)` instead of relying on vehicle status, with sensible defaults when no schedule exists

## [0.3.0] - 2026-05-16

### Added
- Added `ac_on()` and `ac_off()` methods to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient` for explicit climate on/off control
- Added `REMOTE_CTL_AC_ON` and `REMOTE_CTL_AC_OFF` constants
- Added `ClimateOperate.CLOSE` value (`"close"`) — required to turn off the climate system
- Added `set_climate_schedule()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient` for scheduled climate activation (cmd_id=171)
- Added `cancel_climate_schedule()` convenience method to both clients (sends empty controls array)
- Added `REMOTE_CTL_AC_SCHEDULE` constant
- Added `RemoteActionCtlClimateSchedule` dataclass (cmd_id=171) — full-state replacement semantics: the controls array must contain all active schedules
- Added `get_climate_schedule()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient` — retrieves active climate schedules from the server via the `getAppointment` endpoint (cmdId=171)
- Added `get_ptc_heating_schedule()` method — retrieves PTC battery heating schedules (cmdId=161)
- Added `get_charge_schedule()` method — retrieves the charge schedule as a flat dict (cmdId=190)
- Added `get_prepare_car_schedule()` method — retrieves prepare-car pre-conditioning schedules (cmdId=361)
- Added `get_fota_schedule()` method — retrieves FOTA install schedules (cmdId=392)
- All `getAppointment` methods gracefully return empty results when the vehicle lacks permission for a given schedule type
- Added `set_charge_schedule()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient` for setting the full charging schedule (enabled, soc_limit, start_time, end_time, cycles, circulation, recharge)
- Added `REMOTE_CTL_CHARGE_SCHEDULE` constant

### Changed
- **BREAKING:** `ClimateMode.NO_HOT_COLD` renamed to `ClimateMode.WIND` (value changed from `"nohotcold"` to `"wind"` to match decompiled APK)
- **BREAKING:** `ClimateWindshield.NORMAL`/`DEFROST` renamed to `ClimateWindshield.OFF`/`ON` (values changed from `"1"`/`"2"` to `"0"`/`"1"` to match decompiled APK)
- Changed `RemoteActionCtlClimate` default `temperature` from `"24"` to `"26"` (APK default)
- Changed `RemoteActionCtlClimate` default `windlevel` from `4` to `3` (APK default)
- Updated all climate action specs in `REMOTE_ACTION_SPECS` to use corrected enum values
- `examples/commands.py` `ac-on` now uses `ac_on()` instead of `ac_switch()`, added `ac-off` command

### Fixed
- Added missing `get_consumption_weekly_rank()` and `get_consumption_last_week_breakdown()` methods to `AsyncLeapmotorApiClient`

## [0.2.0] - 2026-05-14

### Added
- Added `VehicleRight` enum members for all known international PEI permission codes: `AUTOPARK` (150), `TOGGLE_CHARGE` (193), `SKYLIGHT` (240), `MUSIC` (270), `SEAT_ADJUST` (280), `VIDEO` (290), `SEAT_HEAT` (301), `STEERING_WHEEL_HEAT` (320), `PREPARE_CAR` (360), `PREPARE_CAR_ALARM` (361), `SEAT_VENTILATION` (370), `FUEL_HEATING` (380) — these may appear in `rightList` for C10/B10/C16 models
- Added `VehicleAbility` enum members for all known international CODE* ability codes (4–53): `AUTOPARK`, `AC_ON`, `AC_CYCLE`, `AC_PRESET`, `CHARGE_RELATED_1`, `BLE_KEY`, `REAR_HEAT`, `FRONT_SEAT_HEAT`, `REAR_SEAT_HEAT`, `SCREEN_SAVER`, `CYCLIC_CHARGE`, `CHARGE_REPEAT_WEEKLY`, `CAR_TPMS`, `WINDSHIELD_DEFROST_TRIGGER`, `DRIVER_COPILOT`, `CALENDAR_SYNC`, `AIR_CYCLE`, `FUEL_HEATING`, `DRIVER_SEAT_VENTILATION`, `PASSENGER_SEAT_VENTILATION`, `MOBILE_CONTROL`, `ON3_STRAIGHT_CALL`, `CYCLIC_CHARGE_TRIGGER`, `UNLOCK_CHARGE_GUN`, `PARKING_PHOTO`, `SENTINEL`, `WEEKLY_CHARGE_REPEAT`, `BLE_KEY_RESTART` — covers the complete constant set- Added `CarType` StrEnum with all known vehicle models (`T03`, `S01`, `C01`, `C10`, `C11`, `C16`, `B10`, `B11`, `B05`, `B03X`) and `status_path` property for endpoint routing; includes `_missing_()` for graceful handling of unknown model strings
- Added B11 → C10 status path mapping (B11 shares the C10 status endpoint, like B10)
- Added `ABILITY_TO_RIGHTS` mapping dict in `mappings.py` documenting which `VehicleAbility` codes enable which `VehicleRight` codes (informational, based on decompiled international APK)
- Added `T03_S01_SUPPORTED_RIGHTS` frozenset listing the restricted right set for T03/S01 models
- Added `SentryModeValue` StrEnum (`ON="1"`, `OFF="0"`) and `RemoteActionCtlSentryMode` dataclass (`cmd_id=220`) for sentry mode (sentinel / dashcam) commands
- Added `sentry_mode_on()` and `sentry_mode_off()` methods to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_SENTRY_MODE`, `REMOTE_CTL_SENTRY_MODE_ON`, `REMOTE_CTL_SENTRY_MODE_OFF` constants
- Added `battery_preheat_off()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_BATTERY_PREHEAT_ON` and `REMOTE_CTL_BATTERY_PREHEAT_OFF` constants (aliases for on/off battery preheat)
- Added `start_charging()` and `stop_charging()` methods to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_CHARGE_START` and `REMOTE_CTL_CHARGE_STOP` constants
- Added `ChargeToggleValue` enum (`START`, `STOP`) and `RemoteActionCtlToggleCharge` dataclass
- Added `steering_wheel_heat_on()` and `steering_wheel_heat_off()` methods to both clients
- Added `REMOTE_CTL_STEERING_WHEEL_HEAT`, `REMOTE_CTL_STEERING_WHEEL_HEAT_ON`, `REMOTE_CTL_STEERING_WHEEL_HEAT_OFF` constants
- Added `SteeringWheelHeatValue` enum (`ON`, `OFF`) and `RemoteActionCtlSteeringWheelHeat` dataclass
- Added `fuel_heating_on()` and `fuel_heating_off()` methods to both clients
- Added `REMOTE_CTL_FUEL_HEATING`, `REMOTE_CTL_FUEL_HEATING_ON`, `REMOTE_CTL_FUEL_HEATING_OFF` constants
- Added `FuelHeatingValue` enum (`ON`, `OFF`) and `RemoteActionCtlFuelHeating` dataclass
- Added `rearview_mirror_heat_on()` and `rearview_mirror_heat_off()` methods to both clients
- Added `REMOTE_CTL_REARVIEW_MIRROR_HEAT`, `REMOTE_CTL_REARVIEW_MIRROR_HEAT_ON`, `REMOTE_CTL_REARVIEW_MIRROR_HEAT_OFF` constants
- Added `RearviewMirrorHeatValue` enum (`ON`, `OFF`) and `RemoteActionCtlRearviewMirrorHeat` dataclass
- Added `VehicleRight.REARVIEW_MIRROR_HEAT = 440`
- Added `set_speed_limit()` method to both clients
- Added `REMOTE_CTL_SPEED_LIMIT` constant
- Added `RemoteActionCtlSpeedLimit` dataclass
- Added `seat_heat()` method to both clients
- Added `REMOTE_CTL_SEAT_HEAT` constant and `RemoteActionCtlSeatHeat` dataclass
- Added `seat_ventilation()` method to both clients
- Added `REMOTE_CTL_SEAT_VENTILATION` constant and `RemoteActionCtlSeatVentilation` dataclass
- Added `open_sunroof()` and `close_sunroof()` methods to both clients
- Added `REMOTE_CTL_SUNROOF`, `REMOTE_CTL_SUNROOF_OPEN`, `REMOTE_CTL_SUNROOF_CLOSE` constants
- Added `SunroofValue` enum (`OPEN`, `CLOSE`) and `RemoteActionCtlSunroof` dataclass
- Added `healthy_charging_on()` and `healthy_charging_off()` methods to both clients
- Added `REMOTE_CTL_HEALTHY_CHARGING`, `REMOTE_CTL_HEALTHY_CHARGING_ON`, `REMOTE_CTL_HEALTHY_CHARGING_OFF` constants
- Added `HealthyChargingValue` enum (`ON`, `OFF`) and `RemoteActionCtlHealthyCharging` dataclass
- Added `VehicleRight.HEALTHY_CHARGING = 480`
- Added `hotspot()` method to both clients
- Added `REMOTE_CTL_HOTSPOT` constant and `RemoteActionCtlHotspot` dataclass (cmd_id=140)
- Added `VehicleRight.HOTSPOT = 140`
- Added `autopark()` method to both clients
- Added `REMOTE_CTL_AUTOPARK` constant and `RemoteActionCtlAutopark` dataclass (cmd_id=150)
- Added `on3_on()` and `on3_off()` methods to both clients
- Added `REMOTE_CTL_ON3`, `REMOTE_CTL_ON3_ON`, `REMOTE_CTL_ON3_OFF` constants
- Added `On3Value` enum (`ON`, `OFF`) and `RemoteActionCtlOn3` dataclass (cmd_id=410)
- Added `VehicleRight.ON3 = 410`
- Added `ble_key_restart()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_BLE_KEY_RESTART` constant and `RemoteActionCtlBleKeyRestart` dataclass (cmd_id=430)
- Added `VehicleRight.BLE_KEY_RESTART = 430`
- Added `music()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_MUSIC` constant and `RemoteActionCtlMusic` dataclass (cmd_id=270)
- Added `MusicOperation` enum (`PLAY`, `PAUSE`, `NEXT`, `PREVIOUS`)
- Added `video()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_VIDEO` constant and `RemoteActionCtlVideo` dataclass (cmd_id=290)
- Added `VideoOperation` enum (`PLAY`, `PAUSE`, `NEXT`, `PREVIOUS`)
- Added `fota_download()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_FOTA_DOWNLOAD` constant and `RemoteActionCtlFotaDownload` dataclass (cmd_id=390)
- Added `VehicleRight.FOTA_DOWNLOAD = 390`
- Added `fota_install()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_FOTA_INSTALL` constant and `RemoteActionCtlFotaInstall` dataclass (cmd_id=391)
- Added `VehicleRight.FOTA_INSTALL = 391`
- Added `fota_schedule()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_FOTA_SCHEDULE` constant and `RemoteActionCtlFotaSchedule` dataclass (cmd_id=392)
- Added `VehicleRight.FOTA_INSTALL_APPOINTMENT = 392`
- Added `rear_seats()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_REAR_SEATS` constant and `RemoteActionCtlRearSeats` dataclass (cmd_id=470)
- Added `VehicleRight.REAR_SEATS = 470`
- Added `prepare_car()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_PREPARE_CAR` constant and `RemoteActionCtlPrepareCar` dataclass (cmd_id=360)
- Added `seat_adjust()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_SEAT_ADJUST` constant and `RemoteActionCtlSeatAdjust` dataclass (cmd_id=280)
- Added `piloted_parking()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient`
- Added `REMOTE_CTL_PILOTED_PARKING` constant and `RemoteActionCtlPilotedParking` dataclass (cmd_id=350)
- Added permission reference table to `docs/api.md` mapping each `VehicleRight` to its corresponding remote command
- Added `VehicleSecurityState` IntEnum for `vehicle_security_active` field (signal `1255`): `INACTIVE=0`, `ACTIVE_1=1`, `ACTIVE_2=2`, `ACTIVE_3=3`
- Added `SecurityStatus.is_security_active` convenience property: `True` when anti-theft is active (values 1, 2, or 3)
- Added `ClimateStatus.is_windshield_defrost_active` convenience property: `True` when windshield defrost is ON (APK: both values 1 and 2 mean active)
- Added `BatteryStatus.healthy_charge_enabled` field: healthy charge switch (signal `48` / `isCarHealthyChargeOpen`, `BoolStatus`)
- Added `DrivingStatus.parking_brake_state` field: parking brake state (signal `1480` / `prakingState`)
- Added `ChargePlan.cancelled_once` field: scheduled charge cancelled once (signal `3737` / `isCancelChargeOnce`, `BoolStatus`)
- Added `GearStatus._missing_()` handler for graceful handling of unknown gear values (e.g. `0xFFFFFF` = invalid)
- Added `WindshieldDefrostState` IntEnum for `windshield_defrost` field (signal `1945`): `OFF=0`, `ON_1=1`, `ON_2=2` (both 1 and 2 mean active per APK)
### Changed
- **Breaking**: `VehicleStatus.is_parked` is now complementary to `is_driving` — uses ignition + gear logic (APK-aligned) instead of speed-based. Falls back to speed when ignition/gear data is unavailable
- `VehicleStatus.is_driving` now returns explicit `False` (instead of falsy `None`/`0`) when ignition or gear indicate not driving
- Added `HvacDirection` IntEnum for `ac_cooling_and_heating` field: `WIND=0`, `COLD=1`, `HOT=2`
- Added `HvacMode` IntEnum for `climate_mode` field (signal `$3713`): `OFF=0`, `FAST_COOL=1`, `FAST_HEAT=3`
- Added `AcOperateMode` IntEnum for `ac_operate_mode` field (signal `$1939`): `AUTO=0`, `MANUAL=1`
- Added `RecirculationMode` IntEnum for `recirculation_mode` field (signal `$1943`): `FRESH_AIR=0`, `RECIRCULATION=1`
- Added `ClimateStatus.ac_operate_mode` field: AC operation mode from signal `1939` (0=auto, else=manual)
- Added signal `1941` → `acAirVolume` mapping: HVAC fan speed (1–7) now populated on C10/B10 signal-based responses
- Added legacy HVAC air direction derivation: when signal `3713` is absent, combines cooling flap (`1940`) and heating flap (`1949`) signals into `acCoolingAndHeating` (0=wind, 1=cold, 2=hot) following the APK truth table
- Added `VehicleStatus.is_driving` convenience property: `True` when ignition ON3 is active and gear is in DRIVE or REVERSE (based on `bcmKeyPositionOn3` and `gearStatus`)
- Added `BatteryStatus.ac_input_slow_charge` field: AC slow charge input status (signal `47` / `acInputSlowCharge`)
- Added `BoolStatus` IntEnum (`OFF=0`, `ON=1`) for generic boolean signals from the API
- Added `BatteryStatus.is_charge_fast_gun_insert` computed property: `True` when the DC fast charge gun is inserted (`dcInputFastCharge == BoolStatus.ON`)
- Added `BatteryStatus.is_charge_slow_gun_insert` computed property: `True` when the AC slow charge gun is inserted (`acInputSlowCharge == BoolStatus.ON`)
- Added `GearStatus` IntEnum for gear position codes (`PARK=0`, `DRIVE=1`, `NEUTRAL=2`, `REVERSE=3`)
- Added `VehicleAbility`, `VehicleRight`, and `ModuleRight` IntEnum classes for typed vehicle permissions, replacing raw strings/lists
- `Vehicle.rights`, `Vehicle.abilities`, and `Vehicle.module_rights` are now typed lists of enum members (parsed from API strings) with empty-list defaults
- Added `Vehicle.has_ability()`, `Vehicle.has_right()`, and `Vehicle.has_module_right()` convenience methods accepting both enum members and raw ints
- Unknown permission codes from the API are handled gracefully via `_missing_()` (e.g. ability 61 → `UNKNOWN_61`) instead of raising errors
- Each enum member has a `.description` property with a human-readable label
- Added `required_right` field to `RemoteActionSpec` linking each remote command to its required `VehicleRight`
- Remote commands now log a warning when the vehicle's rights may not include the required permission (soft check — the server remains the authority)
- Added `LeapmotorPermissionError` exception class for consumers wanting strict permission enforcement
- Added `SeatComfortStatus` sub-object: driver/passenger seat heating and ventilation levels, steering wheel heating and remaining minutes
- Added `SecurityStatus` sub-object: vehicle security active, sentry mode, mirror heating (left/right), roof/skylight opening
- Added new fields to `BatteryStatus`: `precise_soc`, `min_battery_temp`, `battery_thermal_request`, `charge_completed`
- Added `ChargePlan` sub-object inside `BatteryStatus` (`battery.charge_plan`) grouping charge schedule fields: `soc_setting`, `time_setting`, `enabled`, `start`, `end`, `cycles`, `circulation`, `recharge`
- Added new fields to `DrivingStatus`: `vehicle_state`, `speed_limit`, `speed_limit_unit`, `speed_limit_active`, `live_remaining_range`, `max_range`, `range_mode`
- Added new fields to `ClimateStatus`: `ac_setting_right`, `interior_temp`, `recirculation_mode`, `windshield_defrost`, `rear_window_heating`, `climate_mode`, `rapid_cooling`, `rapid_heating`
- Added `bcm_key_position_on2` to `IgnitionStatus`
- Added `config.3` charge plan mapping for C10/B10: charge limit and scheduling fields are now populated from the `config` section (including `recharge`)
- Added GPS fallback using alternative coordinates (signals `2190`/`2191`) when primary GPS signals are absent
- Added 30+ new signal IDs to `_SIGNAL_TO_NAMED` covering all new fields
- Added documentation for api (`docs/api.md`) and vehicles (`docs/vehicles.md`)
- Added `RemoteActionCtlChargePlan` typed dataclass for charge plan/schedule commands (`cmd_id=190`) with fields: `charge_enable`, `chargesoc`, `circulation`, `cycles`, `endtime`, `recharge`, `starttime`
- Added `REMOTE_CTL_CHARGE_LIMIT` constant and corresponding entry in `REMOTE_ACTION_SPECS`
- Added `RemoteActionCtlSendDestination` typed dataclass for navigation destination commands (`cmd_id=180`) with fields: `address`, `address_name`, `latitude`, `longitude`
- Added `REMOTE_CTL_SEND_DESTINATION` constant and corresponding entry in `REMOTE_ACTION_SPECS`
- Added `requires_pin` field to `RemoteActionSpec` (default `True`); pin-less commands like `send_destination` set it to `False`
- Added typed energy consumption models: `WeeklyConsumption`, `ConsumptionRank`, `ConsumptionWeeklyRank`, and `ConsumptionLastWeekBreakdown` (with `total_ec` computed property)
- Added `get_consumption_weekly_rank()` and `get_consumption_last_week_breakdown()` methods for retrieving energy consumption statistics from the cloud
- Added `unlock_charger()` remote command (`cmd_id=192`) for unlocking the charging connector before unplugging, with `RemoteActionCtlUnlockCharger` dataclass, `REMOTE_CTL_UNLOCK_CHARGER` constant, `VehicleRight.UNLOCK_CHARGER` (192), and `ChargerOperation` enum
- Added `get_charging_daily_detail()` method for fetching paginated charging session history, with typed models: `ChargeType` enum (`AC`/`DC`), `ChargeRecord` dataclass (with `start_datetime`, `end_datetime`, `duration_seconds`, `is_fast_charge` properties), and `ChargeDailyDetailPage` paginated response; accepts `datetime.date` for `start_time`/`end_time` and a `timezone` parameter (default `"GMT+00:00"`)

### Changed
- **Breaking:** `RemoteActionCtlClimate.windlevel` changed from `str` (default `"4"`) to `int` (default `4`) with validation constraining the value to the range 1–7; the JSON payload still serialises the value as a string for API compatibility
- **Breaking:** `ChargeState` enum members renamed: `NOT_CONNECTED` → `NOT_CHARGING`, `AC_CONNECTED` → `CHARGING`, `DC_CONNECTED` → `FINISH`; added new members: `ERROR=3`, `SETTING=4`, `REGENING=5`, `PAUSE=6`
- **Breaking:** `BatteryStatus.is_charging` now uses `charge_state == ChargeState.CHARGING` instead of `charging_power_kw is not None and charge_remain_time`
- **Breaking:** `VehicleStatus.is_plugged` now returns `True` even while actively charging (previously required `not is_charging`); checks fast gun first, then falls back to `charge_state` when `ac_input_slow_charge` is unavailable (T03), otherwise uses slow gun signal; all paths require `is_parked`
- **Breaking:** `VehicleStatus.is_charging` simplified to `charge_state == ChargeState.CHARGING and is_parked and is_charging`
- **Breaking:** `VehicleStatus.is_regening` now checks `charge_state == ChargeState.REGENING` instead of combining `battery.is_charging` with `charge_state == NOT_CHARGING`
- **Breaking:** `DrivingStatus.gear_status` changed from `int | None` to `GearStatus | None`
- **Breaking:** `Vehicle.rights` changed from `str | None` to `list[VehicleRight]` (was a comma-separated string like `"110,120,230"`)
- **Breaking:** `Vehicle.abilities` changed from `list[str] | None` to `list[VehicleAbility]` (was a list of numeric strings like `["1", "10", "36"]`)
- **Breaking:** `Vehicle.module_rights` changed from `str | None` to `list[ModuleRight]` (was a comma-separated string like `"100,200,300,400"`)
- `DrivingStatus.is_parked` now falls back to `vehicle_state` signal when `speed` is unavailable (improves C10/B10 reliability)
- `set_charge_limit` now reads charging plan data from the typed `VehicleStatus.battery.charge_plan` sub-object instead of navigating raw API dicts
- `set_charge_limit` now delegates to `_remote_control()` for consistent token/PIN/permission checks instead of calling `_remote_control_raw()` directly
- `send_destination` now uses `RemoteActionCtlSendDestination` and delegates to `_remote_control()` for consistent permission checks instead of inline JSON and `_remote_control_without_pin_raw()`
- `_remote_control()` now routes pin-less commands (where `spec.requires_pin` is `False`) to `_remote_control_without_pin_raw()` automatically
- **Breaking:** `BatteryStatus` charge schedule fields (`charge_soc_setting`, `charge_time_setting`, `charge_schedule_enabled`, `charge_schedule_start`, `charge_schedule_end`, `charge_schedule_cycles`, `charge_schedule_circulation`, `charge_schedule_recharge`) moved into `BatteryStatus.charge_plan` (`ChargePlan` sub-object) — e.g. `battery.charge_schedule_start` → `battery.charge_plan.start`
- **Breaking:** `RemoteActionCtlChargeLimit` renamed to `RemoteActionCtlChargePlan`
- All crypto header builders (`build_consumption_weekly_rank_headers`, `build_consumption_last_week_headers`) now return `ApiRequestHeaders` instead of raw `dict[str, str]`

### Removed
- **Breaking:** Removed `fetch_data()` from `LeapmotorApiClient` and `AsyncLeapmotorApiClient` — was a debug-only aggregation method; use `get_vehicle_list()` + `get_vehicle_status()` instead
- **Breaking:** Removed `normalize_vehicle()` — debug-only flattening helper superseded by typed `VehicleStatus` model with raw data included
- **Breaking:** Removed `_fetch_authenticated_data()` internal method — debug-only helper no longer needed

## [0.1.7] - 2026-05-07

### Fixed
- Fixed vehicle status endpoint returning HTTP 404 for B10 vehicles: the international backend reports `carType=B10` in the vehicle list but the status endpoint is shared with C10 (`/status/get/c10`)

## [0.1.6] - 2026-05-06

### Added
- Added debug logging to `_post` (logs HTTP status and response body for all API calls), `_post_binary` (logs HTTP status and response size), and `_poll_remote_control_result` (logs each polling iteration) for better troubleshooting

## [0.1.5] - 2026-05-05

### Fixed
- Fixed `Vehicle.seat_layout` and `Vehicle.rudder` fields: convert to `str` in `from_dict()` to handle B10 vehicles returning integer values from the API

## [0.1.4] - 2026-05-03

### Fixed
- Fixed `BatteryStatus.is_charging` returning `True` when vehicle is off/not charging because `charge_remain_time` was `0` instead of `None`; now requires a truthy (non-zero) value

## [0.1.3] - 2026-05-03

### Added
- Automatic token refresh: all public API methods now transparently handle expired tokens by calling `/acct/v1/token/refresh` before falling back to a full re-login
- Added `token_refresh()` method to both `LeapmotorApiClient` and `AsyncLeapmotorApiClient` for explicit token renewal
- Stored `refresh_token` from login response for use by the refresh flow
- Added `VehicleStatus.is_plugged` property: returns `True` when a charger is connected but charging has not started yet
- Charging image layers: `is_plugged` state shows `carpic_charge_open` + `carpic_charge1` (static plug indicator); active charging starts from frame 2

### Changed
- Refactored `RemoteActionSpec` into typed subclasses (`RemoteActionCtlLock`, `RemoteActionCtlTrunk`, `RemoteActionCtlFindCar`, `RemoteActionCtlSunshade`, `RemoteActionCtlBatteryPreheat`, `RemoteActionCtlWindows`, `RemoteActionCtlClimate`) with explicit parameters per command
- Added `StrEnum` value types for type-safe command parameters: `LockValue`, `ToggleValue`, `SunshadeValue`, `WindowsValue`, `BatteryPreheatValue`, `ClimateCircle`, `ClimateMode`, `ClimateOperate`, `ClimatePosition`, `ClimateWindshield`
- `RemoteActionCtlSunshade` and `RemoteActionCtlWindows` now validate value ranges (0-10 and 0-100 respectively) at construction time
- Charging animation now excludes frame 1 and uses frames 2–15

### Fixed
- Fixed `Vehicle.from_dict` mapping: `userNickname` → `nickName` and `rights` → `rightList` to match actual API response keys
- Correct `is_charging` assignment in image layer composition

## [0.1.2] - 2026-05-02

### Added
- Added `Message` and `MessageList` models for notification messages
- Added `get_message_list(page_no, page_size)` method to retrieve paginated messages
- Added `get_unread_message_count()` method to get the number of unread messages
- Added async variants of message methods to `AsyncLeapmotorApiClient`
- Added `body_params` support to `build_signed_headers` for endpoints that include body parameters in the HMAC signature
- Updated example usage script to display messages

### Changed
- Remote control methods (`open_windows`, `close_windows`, `windows`, `control_sunshade`, `open_sunshade`, `close_sunshade`) now accept an optional `value` parameter to control intensity/position
- AC methods (`ac_switch`, `quick_cool`, `quick_heat`, `windshield_defrost`) now accept an optional `params` dict to override default climate settings (temperature, wind level, etc.)
- Internal `_remote_control` accepts optional `cmd_content` override for custom payloads

## [0.1.1] - 2026-05-01

### Added
- Added Enum for `ChargeState` and mapped raw integer values to enum members (e.g., `NOT_CONNECTED`, `AC_CONNECTED`, `DC_CONNECTED`)
- Added discharging power and `is_discharging` properties to battery status model
- Added `from_dict` class method to `BatteryStatus` for mapping raw API response into structured model
- Added regenerative braking status to vehicle status model (`is_regening` property) that indicates when the vehicle is regeneratively braking (i.e., driving with battery charging)
- Added `certs` folder for storing certificate files used for API communication
- Added `email`, `plate_number`, `vehicle_nickname`, `mobile_number`, `out_color`, `share_time`, `expire_time`, `duration_type`, `seat_layout`, `rudder` and `allocation_code` fields to `Vehicle` model based on API response data
- Added `raw` property to `Vehicle` model for storing original API response data for forward-compatibility and debugging
- Added `from_dict` class method to `Vehicle` model for mapping raw API response into structured model
- Added example usage script (`examples/usage.py`) that demonstrates how to use the `LeapmotorApiClient` to connect to the API, retrieve vehicle status, and display it in a human-readable format
- Added `pre-commit` dependency in `pyproject.toml` for managing git hooks and ensuring code quality before commits

### Changed
- Updated `BatteryStatus` to use `ChargeState` enum instead of raw integers
- Updated `BatteryStatus` logic for charging and discharging states
- Renamed `nickname` field in `Vehicle` model to `vehicle_nickname` for clarity
- Refactored `get_vehicle_status` method into `LeapmotorApiClient` to utilize new `VehicleStatus.from_dict` for parsing API response into structured model

### Removed
- Battery fields that map raw api into `BatteryStatus` model (e.g., `soc` and `chargeState` properties that were previously calculated based on raw api values)


## [0.1.0] - 2026-04-30

### Added
- Initial release with login, vehicle status, and remote commands
- Async client support
- AES encryption utilities for API communication
- Vehicle image generation
- Typed models for API responses
