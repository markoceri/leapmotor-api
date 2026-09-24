"""Leapmotor API data models."""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Any

from .const import (
    DEFAULT_APP_VERSION,
    DEFAULT_CHANNEL,
    DEFAULT_DEVICE_TYPE,
    DEFAULT_LANGUAGE,
    DEFAULT_P12_ENC_ALG,
    DEFAULT_SOURCE,
)

# ---------------------------------------------------------------------------
# API request headers model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ApiRequestHeaders:
    """Signed HTTP headers for Leapmotor API requests.

    All ``build_*_headers`` functions in :mod:`crypto` return an instance of
    this model.  Call :meth:`to_dict` to obtain a mutable ``dict[str, str]``
    suitable for ``requests`` or ``httpx``.

    Constant protocol fields carry defaults from the module-level constants
    so callers only need to supply the per-request fields (``nonce``,
    ``device_id``, ``timestamp``, ``sign``).
    """

    # -- Per-request fields (required) --
    nonce: str
    device_id: str
    timestamp: str
    sign: str

    # -- Protocol constants (defaults from module-level constants) --
    accept_language: str = DEFAULT_LANGUAGE
    channel: str = DEFAULT_CHANNEL
    device_type: str = DEFAULT_DEVICE_TYPE
    source: str = DEFAULT_SOURCE
    version: str = DEFAULT_APP_VERSION
    p12_enc_alg: str | None = DEFAULT_P12_ENC_ALG
    content_type: str | None = "application/x-www-form-urlencoded"

    def to_dict(self) -> dict[str, str]:
        """Convert to a mutable dict with the original API header names."""
        headers: dict[str, str] = {
            "acceptLanguage": self.accept_language,
            "channel": self.channel,
            "deviceType": self.device_type,
            "source": self.source,
            "version": self.version,
            "nonce": self.nonce,
            "deviceId": self.device_id,
            "timestamp": self.timestamp,
            "sign": self.sign,
        }
        if self.p12_enc_alg is not None:
            headers["X-P12_ENC_ALG"] = self.p12_enc_alg
        if self.content_type is not None:
            headers["Content-Type"] = self.content_type
        return headers


# ---------------------------------------------------------------------------
# Enums and data classes for structured vehicle status and metadata.
# ---------------------------------------------------------------------------


class ChargeState(IntEnum):
    """Charging state codes reported by the vehicle."""

    NOT_CHARGING = 0
    CHARGING = 1
    FINISH = 2
    ERROR = 3
    SETTING = 4
    REGENING = 5
    PAUSE = 6


class ChargeType(StrEnum):
    """Charging type codes."""

    AC = "1"
    DC = "2"


class CarType(StrEnum):
    """Known Leapmotor vehicle model identifiers.

    The API returns ``carType`` as a string (e.g. ``"T03"``, ``"C10"``).
    Values are **lowercase** to match endpoint path segments.
    Use :attr:`status_path` to get the correct status endpoint segment.
    """

    T03 = "t03"
    S01 = "s01"
    C01 = "c01"
    C10 = "c10"
    C11 = "c11"
    C16 = "c16"
    B10 = "b10"
    B11 = "b11"
    B05 = "b05"
    B03X = "b03x"

    @classmethod
    def _missing_(cls, value: object) -> CarType | None:
        if not isinstance(value, str):
            return None
        # Normalise to lowercase
        lower = value.lower()
        for member in cls:
            if member.value == lower:
                return member
        member = str.__new__(cls, lower)
        member._name_ = f"UNKNOWN_{lower.upper()}"
        member._value_ = lower
        return member

    @property
    def status_path(self) -> str:
        """Endpoint path segment for the vehicle status API.

        B10 and B11 share the C10 status endpoint.
        """
        return _CAR_TYPE_STATUS_PATH.get(self.value, self.value)


_CAR_TYPE_STATUS_PATH: dict[str, str] = {
    "b10": "c10",
    "b11": "c10",
}


class ModuleRight(IntEnum):
    """Macro-category permission codes for vehicle sharing."""

    BASIC = 100
    VEHICLE_CONTROL = 200
    VEHICLE_POSITIONING = 300
    MILEAGE_ENERGY = 400

    @classmethod
    def _missing_(cls, value: object) -> ModuleRight | None:
        if not isinstance(value, int):
            return None
        member = int.__new__(cls, value)
        member._name_ = f"UNKNOWN_{value}"
        member._value_ = value
        return member

    @property
    def description(self) -> str:
        return _MODULE_RIGHT_DESCRIPTIONS.get(self.value, f"Unknown module right ({self.value})")


_MODULE_RIGHT_DESCRIPTIONS: dict[int, str] = {
    100: "Basic authorisation (lock/unlock)",
    200: "Vehicle control (climate, charge, quick control)",
    300: "Vehicle positioning (GPS)",
    400: "Mileage & energy consumption",
}


class VehicleRight(IntEnum):
    """Remote command permission codes (rightList).

    These are PEI_* constants from the international APK
    (``CarAblityToPerManager.java``).  The server returns a subset
    of these codes in ``rightList`` depending on the vehicle model,
    abilities, and sharing level.
    """

    LOCK = 110
    FIND_CAR = 120
    TRUNK = 130
    HOTSPOT = 140
    AUTOPARK = 150
    SUNROOF = 160
    SUNSHADE = 161
    CLIMATE = 170
    QUICK_CLIMATE = 171
    SEND_DESTINATION = 180
    BATTERY_PREHEAT = 190
    UNLOCK_CHARGER = 192
    TOGGLE_CHARGE = 193
    SENTRY_MODE = 220
    WINDOWS = 230
    SKYLIGHT = 240
    MUSIC = 270
    SEAT_ADJUST = 280
    VIDEO = 290
    SEAT_HEAT = 301
    STEERING_WHEEL_HEAT = 320
    CHARGE_LIMIT = 340
    PILOTED_PARKING = 350
    PREPARE_CAR = 360
    PREPARE_CAR_ALARM = 361
    SEAT_VENTILATION = 370
    FUEL_HEATING = 380
    FOTA_DOWNLOAD = 390
    FOTA_INSTALL = 391
    FOTA_INSTALL_APPOINTMENT = 392
    ON3 = 410
    BLE_KEY_RESTART = 430
    REARVIEW_MIRROR_HEAT = 440
    WINDSHIELD_DEFROST = 460
    REAR_SEATS = 470
    HEALTHY_CHARGING = 480
    SPEED_LIMIT = 510

    @classmethod
    def _missing_(cls, value: object) -> VehicleRight | None:
        if not isinstance(value, int):
            return None
        member = int.__new__(cls, value)
        member._name_ = f"UNKNOWN_{value}"
        member._value_ = value
        return member

    @property
    def description(self) -> str:
        return _VEHICLE_RIGHT_DESCRIPTIONS.get(self.value, f"Unknown right ({self.value})")


_VEHICLE_RIGHT_DESCRIPTIONS: dict[int, str] = {
    110: "Lock / Unlock doors",
    120: "Find car (horn + lights)",
    130: "Trunk open/close",
    150: "Auto park / summon",
    160: "Sunroof control",
    161: "Sunshade control",
    170: "Climate / AC on-off",
    171: "Quick cool / Quick heat",
    180: "Send destination (navigation)",
    190: "Battery preheating",
    192: "Unlock charger connector",
    193: "Start / stop charging",
    220: "Sentry mode",
    230: "Windows",
    240: "Skylight control",
    270: "Music control",
    280: "Seat adjust",
    290: "Video",
    301: "Seat heating",
    320: "Steering wheel heating",
    340: "Charge limit",
    350: "Piloted parking / summon",
    360: "Pre-conditioning (prepare car)",
    361: "Pre-conditioning alarm",
    370: "Seat ventilation",
    380: "Fuel heating",
    390: "FOTA download",
    391: "FOTA install",
    392: "FOTA install appointment / schedule",
    410: "ON3 mode",
    430: "BLE key restart",
    460: "Windshield defrost / mirror heating",
    470: "Rear seats control",
    510: "Speed limit",
}


class VehicleAbility(IntEnum):
    """Hardware/firmware feature flag codes (abilities).

    These are CODE* constants from the international APK
    (``LocalAbilityCode.java``).  The server returns a subset
    of these codes in ``abilities`` depending on the vehicle model
    and hardware/firmware configuration.
    """

    BASE = 1
    STATUS_DATA = 2
    TRUNK = 3
    AUTOPARK = 4
    GPS = 5
    AC_ON = 6
    BATTERY_DETAIL = 7
    AC_CYCLE = 8
    AC_PRESET = 9
    LOCK_UNLOCK = 10
    FIND_CAR = 11
    WINDOWS_C10 = 12
    CHARGE_RELATED_1 = 13
    SEAT_HEATING = 14
    STEERING_WHEEL = 15
    BLE_KEY = 16
    CLIMATE_ADVANCED = 17
    WINDSHIELD_DEFROST = 18
    REAR_HEAT = 19
    WINDOWS_T03_ALT = 20
    FRONT_SEAT_HEAT = 21
    REAR_SEAT_HEAT = 22
    SCREEN_SAVER = 23
    TRUNK_SPECIAL = 24
    CYCLIC_CHARGE = 25
    CHARGE_REPEAT_WEEKLY = 26
    CAR_TPMS = 27
    WINDSHIELD_DEFROST_TRIGGER = 28
    DRIVER_COPILOT = 29
    GPS_SHARING = 30
    MILEAGE_ENERGY = 31
    CALENDAR_SYNC = 32
    CODE33 = 33
    SPEED_LIMIT = 34
    CHARGE_LIMIT = 35
    WINDOWS_T03 = 36
    AIR_CYCLE = 37
    PREPARE = 38
    CODE39 = 39
    FUEL_HEATING = 40
    CODE41 = 41
    DRIVER_SEAT_VENTILATION = 42
    PASSENGER_SEAT_VENTILATION = 43
    CODE44 = 44
    MOBILE_CONTROL = 45
    ON3_STRAIGHT_CALL = 46
    CYCLIC_CHARGE_TRIGGER = 47
    UNLOCK_CHARGE_GUN = 48
    PARKING_PHOTO = 49
    SENTINEL = 50
    WEEKLY_CHARGE_REPEAT = 51
    NAVIGATION = 52
    BLE_KEY_RESTART = 53

    @classmethod
    def _missing_(cls, value: object) -> VehicleAbility | None:
        if not isinstance(value, int):
            return None
        member = int.__new__(cls, value)
        member._name_ = f"UNKNOWN_{value}"
        member._value_ = value
        return member

    @property
    def description(self) -> str:
        return _VEHICLE_ABILITY_DESCRIPTIONS.get(self.value, f"Unknown ability ({self.value})")


_VEHICLE_ABILITY_DESCRIPTIONS: dict[int, str] = {
    1: "Vehicle base / remote state",
    2: "Vehicle status data",
    3: "Trunk control",
    4: "Auto park / summon",
    5: "GPS / positioning",
    6: "AC on ability",
    7: "Detailed battery telemetry",
    8: "AC recirculation cycle",
    9: "AC preset / scheduling",
    10: "Remote lock/unlock",
    11: "Find car",
    12: "Windows (C10/B10)",
    13: "Charge related (variant 1)",
    14: "Seat heating/ventilation",
    15: "Steering wheel heating",
    16: "BLE digital key",
    17: "Advanced climate (quick cool/heat)",
    18: "Windshield defrost",
    19: "Rear seat heating",
    20: "Windows (T03 alternate)",
    21: "Front seat heating",
    22: "Rear seat heating (ability)",
    23: "Screen saver",
    24: "Trunk special (C10/B10)",
    25: "Cyclic / timed charging",
    26: "Charge repeat weekly",
    27: "TPMS monitoring",
    28: "Windshield defrost trigger",
    29: "Driver / copilot distinction",
    30: "GPS sharing",
    31: "Mileage & energy data",
    32: "Calendar sync",
    33: "Ability 33",
    34: "Speed limit",
    35: "Charge limit",
    36: "Windows (T03)",
    37: "Air recirculation toggle",
    38: "Pre-conditioning (C10/B10)",
    39: "Ability 39",
    40: "Fuel heating",
    41: "Ability 41",
    42: "Driver seat ventilation",
    43: "Passenger seat ventilation",
    44: "Ability 44",
    45: "Mobile phone control",
    46: "ON3 / straight call",
    47: "Cyclic charge trigger",
    48: "Unlock charging gun",
    49: "Parking photo",
    50: "Sentinel / dashcam mode",
    51: "Weekly charge repeat trigger",
    52: "Navigation / send destination",
    53: "BLE key restart",
}


class GearStatus(IntEnum):
    """Gear position codes."""

    PARK = 0
    DRIVE = 1
    NEUTRAL = 2
    REVERSE = 3

    @classmethod
    def _missing_(cls, value: object) -> GearStatus | None:
        """Handle unknown gear values (e.g. 0xFFFFFF = invalid)."""
        if not isinstance(value, int):
            return None
        member = int.__new__(cls, value)
        member._name_ = f"UNKNOWN_{value}"
        member._value_ = value
        return member


class BoolStatus(IntEnum):
    """Generic boolean status represented as 0/1 in the API."""

    OFF = 0
    ON = 1


class HvacDirection(IntEnum):
    """HVAC air direction."""

    WIND = 0
    COLD = 1
    HOT = 2


class HvacMode(IntEnum):
    """Climate mode."""

    OFF = 0
    FAST_COOL = 1
    FAST_HEAT = 3


class AcOperateMode(IntEnum):
    """AC operation mode."""

    AUTO = 0
    MANUAL = 1


class RecirculationMode(IntEnum):
    """Air recirculation mode."""

    FRESH_AIR = 0
    RECIRCULATION = 1


class VehicleSecurityState(IntEnum):
    """Vehicle security / anti-theft state from signal ``$1255``.

    Values 1, 2, 3 all indicate an active anti-theft mode.
    """

    INACTIVE = 0
    ACTIVE_1 = 1
    ACTIVE_2 = 2
    ACTIVE_3 = 3


class WindshieldDefrostState(IntEnum):
    """Windshield defrost state from signal ``1945``.

    Both ``ON_1`` and ``ON_2`` mean the defrost is active.
    """

    OFF = 0
    ON_1 = 1
    ON_2 = 2


# ---------------------------------------------------------------------------
# Helpers for parsing permission strings from the API
# ---------------------------------------------------------------------------


def _parse_csv_enum(raw: str | None, enum_cls: type[IntEnum]) -> list[Any]:
    """Parse a comma-separated string of ints into a list of *enum_cls* members."""
    if not raw:
        return []
    result = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            with contextlib.suppress(ValueError):
                result.append(enum_cls(int(part)))
    return result


def _parse_list_enum(raw: list[str] | None, enum_cls: type[IntEnum]) -> list[Any]:
    """Parse a list of string ints into a list of *enum_cls* members."""
    if not raw:
        return []
    result = []
    for item in raw:
        with contextlib.suppress(ValueError):
            result.append(enum_cls(int(item)))
    return result


# ---------------------------------------------------------------------------
# Class models for API data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Vehicle:
    """Vehicle metadata from the vehicle list."""

    vin: str
    car_type: str
    email: str | None
    plate_number: str | None
    car_id: str | None
    user_nickname: str | None
    vehicle_nickname: str | None
    mobile_number: str | None = None
    out_color: str | None = None
    is_shared: bool = False
    share_time: int | None = None
    expire_time: int | None = None
    duration_type: int | None = None
    seat_layout: str | None = None
    rudder: str | None = None
    year: int | None = None
    rights: list[VehicleRight] = field(default_factory=list)
    abilities: list[VehicleAbility] = field(default_factory=list)
    module_rights: list[ModuleRight] = field(default_factory=list)
    allocation_code: str | None = None

    # -- Raw dict for debug --
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any], is_shared: bool) -> Vehicle:
        """Build a Vehicle from a raw API dict."""
        return cls(
            vin=data.get("vin", ""),
            email=data.get("email"),
            plate_number=data.get("plateNumber"),
            car_id=str(data["carId"]) if data.get("carId") is not None else None,
            car_type=str(data.get("carType")),
            user_nickname=data.get("nickName"),
            vehicle_nickname=data.get("vinNickname"),
            mobile_number=data.get("mobileNumber"),
            out_color=data.get("outColor"),
            is_shared=is_shared,
            share_time=data.get("shareTime"),
            expire_time=data.get("expireTime"),
            duration_type=data.get("durationType"),
            seat_layout=str(data["seatLayout"]) if data.get("seatLayout") is not None else None,
            rudder=str(data["rudder"]) if data.get("rudder") is not None else None,
            year=data.get("year"),
            rights=_parse_csv_enum(data.get("rightList"), VehicleRight),
            abilities=_parse_list_enum(data.get("abilities"), VehicleAbility),
            module_rights=_parse_csv_enum(data.get("moduleRights"), ModuleRight),
            allocation_code=data.get("allocationCode"),
            raw=data,
        )

    def has_ability(self, ability: VehicleAbility | int) -> bool:
        """Check if the vehicle has a specific ability."""
        code = int(ability)
        return any(int(a) == code for a in self.abilities)

    def has_right(self, right: VehicleRight | int) -> bool:
        """Check if the vehicle has a specific right."""
        code = int(right)
        return any(int(r) == code for r in self.rights)

    def has_module_right(self, module_right: ModuleRight | int) -> bool:
        """Check if the vehicle has a specific module right."""
        code = int(module_right)
        return any(int(m) == code for m in self.module_rights)


@dataclass(frozen=True, slots=True)
class TirePressure:
    """Tire pressure readings for all four wheels."""

    front_left_kpa: int | None = None
    front_right_kpa: int | None = None
    rear_left_kpa: int | None = None
    rear_right_kpa: int | None = None
    front_left_state: int | None = None
    front_right_state: int | None = None
    rear_left_state: int | None = None
    rear_right_state: int | None = None

    @property
    def front_left_bar(self) -> float | None:
        return round(self.front_left_kpa / 100.0, 2) if self.front_left_kpa is not None else None

    @property
    def front_right_bar(self) -> float | None:
        return round(self.front_right_kpa / 100.0, 2) if self.front_right_kpa is not None else None

    @property
    def rear_left_bar(self) -> float | None:
        return round(self.rear_left_kpa / 100.0, 2) if self.rear_left_kpa is not None else None

    @property
    def rear_right_bar(self) -> float | None:
        return round(self.rear_right_kpa / 100.0, 2) if self.rear_right_kpa is not None else None

    @property
    def all_bar(self) -> dict[str, float | None]:
        """All pressures in bar as a dict."""
        return {
            "front_left": self.front_left_bar,
            "front_right": self.front_right_bar,
            "rear_left": self.rear_left_bar,
            "rear_right": self.rear_right_bar,
        }

    @property
    def all_ok(self) -> bool | None:
        """True if all tire pressure states are 0 (normal). None if any state is unknown."""
        states = [self.front_left_state, self.front_right_state, self.rear_left_state, self.rear_right_state]
        if any(s is None for s in states):
            return None
        return all(s == 0 for s in states)


@dataclass(slots=True)
class ChargePlan:
    """Charge plan / schedule settings (from ``config.3`` on C10/B10)."""

    soc_setting: int | None = None
    time_setting: str | None = None
    enabled: int | None = None
    start: str | None = None
    end: str | None = None
    cycles: str | None = None
    circulation: int | None = None
    # Auto-recharge flag (0=off, 1=on): mirrors the official app's "resume charging if
    # schedule is missed" setting (resume/retry charging outside the configured window).
    recharge: int | None = None
    cancelled_once: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChargePlan:
        """Build a ChargePlan from the merged API dict."""
        return cls(
            soc_setting=data.get("chargesocSetting"),
            time_setting=data.get("chargeTimeSetting"),
            enabled=data.get("chargeScheduleEnabled"),
            start=data.get("chargeScheduleStart"),
            end=data.get("chargeScheduleEnd"),
            cycles=data.get("chargeScheduleCycles"),
            circulation=data.get("chargeScheduleCirculation"),
            recharge=data.get("chargeScheduleRecharge"),
            cancelled_once=data.get("chargeScheduleCancelledOnce"),
        )


@dataclass(slots=True)
class BatteryStatus:
    """Battery and charging status."""

    soc: int | None = None
    precise_soc: float | None = None
    charge_state: ChargeState | None = None
    charge_remain_time: int | None = None
    charge_plan: ChargePlan = field(default_factory=ChargePlan)
    charge_completed: int | None = None
    ac_input_slow_charge: int | None = None
    dc_input_fast_charge: int | None = None
    dump_energy: int | None = None
    battery_current: float | None = None
    battery_voltage: float | None = None
    expected_mileage: int | None = None
    min_battery_temp: int | None = None
    battery_thermal_request: int | None = None
    healthy_charge_enabled: int | None = None
    expected_fuel_mileage: int | None = None
    expected_combined_mileage: int | None = None

    @property
    def dump_energy_kwh(self) -> float | None:
        """Available energy in kWh (raw ``dump_energy`` is in Wh)."""
        if self.dump_energy is None:
            return None
        return round(self.dump_energy / 1000, 2)

    @property
    def battery_power(self) -> float | None:
        """Battery power in kW, computed from voltage and current."""
        if self.battery_voltage is None or self.battery_current is None:
            return None
        return round((self.battery_voltage * self.battery_current) / 1000, 3)

    @property
    def charging_power_kw(self) -> float | None:
        """Charging power in kW. Negative current."""
        if self.battery_power is None:
            return None
        return abs(self.battery_power) if self.battery_power < 0 else 0.0

    @property
    def discharging_power_kw(self) -> float | None:
        """Discharging power in kW. Positive current."""
        if self.battery_power is None:
            return None
        return self.battery_power if self.battery_power > 0 else 0.0

    @property
    def is_charging(self) -> bool | None:
        """True if the battery is actively charging.
        This property analyzes the charging status from the point of view of the battery only, not the vehicle.
            For example, it returns True if the vehicle is currently driving and the battery is charging
            due to regenerative braking.
        The vehicle's overall charging status (e.g. whether it's plugged in and charging) can be determined
        from the ``VehicleStatus.is_charging`` property, which also considers the driving status.
        """
        return bool(self.charging_power_kw is not None and self.charge_state == ChargeState.CHARGING)

    @property
    def is_discharging(self) -> bool | None:
        """True if the battery is actively discharging (e.g., driving or powering onboard systems)."""
        return bool(self.discharging_power_kw is not None and self.discharging_power_kw > 0)

    @property
    def is_charge_fast_gun_insert(self) -> bool | None:
        """True if the fast charging gun is detected as inserted (C10/B10 signal `dcInputFastCharge`)."""
        if self.dc_input_fast_charge is None:
            return None
        return self.dc_input_fast_charge == BoolStatus.ON

    @property
    def is_charge_slow_gun_insert(self) -> bool | None:
        """True if the slow charging gun is detected as inserted (C10/B10 signal `acInputSlowCharge`)."""
        if self.ac_input_slow_charge is None:
            return None
        return self.ac_input_slow_charge == BoolStatus.ON

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BatteryStatus:
        """Build a BatteryStatus from a raw API dict."""
        raw_charge_state = data.get("chargeState")
        charge_state: ChargeState | None = None
        if raw_charge_state is not None:
            try:
                charge_state = ChargeState(raw_charge_state)
            except ValueError:
                charge_state = None
        return cls(
            soc=data.get("soc"),
            precise_soc=data.get("preciseSoc"),
            charge_state=charge_state,
            charge_remain_time=data.get("chargeRemainTime"),
            charge_plan=ChargePlan.from_dict(data),
            charge_completed=data.get("chargeCompleted"),
            ac_input_slow_charge=data.get("acInputSlowCharge"),
            dc_input_fast_charge=data.get("dcInputFastCharge"),
            dump_energy=data.get("dumpEnergy"),
            battery_current=data.get("batteryCurrent"),
            battery_voltage=data.get("batteryVoltage"),
            expected_mileage=data.get("expectedMileage"),
            min_battery_temp=data.get("minBatteryTemp"),
            battery_thermal_request=data.get("batteryThermalRequest"),
            healthy_charge_enabled=data.get("healthyChargeEnabled"),
            expected_fuel_mileage=data.get("expectedFuelMileage"),
            expected_combined_mileage=data.get("expectedCombinedMileage"),
        )


@dataclass(slots=True)
class DrivingStatus:
    """Driving / motion status."""

    speed: int | None = None
    total_mileage: int | None = None
    gear_status: GearStatus | None = None
    vehicle_state: int | None = None
    speed_limit: int | None = None
    speed_limit_unit: int | None = None
    speed_limit_active: int | None = None
    live_remaining_range: int | None = None
    max_range: int | None = None
    range_mode: int | None = None
    parking_brake_state: int | None = None
    max_fuel_range: int | None = None
    max_combined_range: int | None = None

    @property
    def is_parked(self) -> bool | None:
        """True if the vehicle is stationary."""
        if self.speed is not None:
            return self.speed == 0
        if self.vehicle_state is not None:
            return self.vehicle_state in (0, 1, 3)
        return None


@dataclass(slots=True)
class LocationStatus:
    """GPS location."""

    latitude: float | None = None
    longitude: float | None = None


@dataclass(slots=True)
class ClimateStatus:
    """Climate / air conditioning status."""

    ac_switch: bool | None = None
    ac_setting: float | None = None
    ac_setting_right: float | None = None
    interior_temp: float | None = None
    ac_air_volume: int | None = None
    ac_air_volume_setting: int | None = None
    ac_wind_direction: int | None = None
    ac_temp_mode: bool | None = None
    ac_circle_mode: bool | None = None
    ac_cooling_and_heating: HvacDirection | None = None
    outdoor_temp: int | None = None
    min_single_temp: int | None = None
    ptc_state: int | None = None
    ptc_power_setting_value: int | None = None
    recirculation_mode: RecirculationMode | None = None
    windshield_defrost: WindshieldDefrostState | None = None
    rear_window_heating: int | None = None
    climate_mode: HvacMode | None = None
    rapid_cooling: int | None = None
    rapid_heating: int | None = None
    ac_operate_mode: AcOperateMode | None = None

    @property
    def is_windshield_defrost_active(self) -> bool | None:
        """True if windshield defrost is active (values 1 and 2 both mean ON)."""
        if self.windshield_defrost is None:
            return None
        return self.windshield_defrost in (1, 2)


@dataclass(slots=True)
class DoorStatus:
    """Door and lock status."""

    driver_door_lock_status: bool | None = None
    lbcm_driver_door_status: bool | None = None
    rbcm_driver_door_status: bool | None = None
    lbcm_left_rear_door_status: bool | None = None
    rbcm_right_rear_door_status: bool | None = None
    bbcm_back_door_status: bool | None = None
    bcm_door_ctrl_allow: bool | None = None

    @property
    def is_locked(self) -> bool | None:
        """True if the vehicle is locked."""
        if self.driver_door_lock_status is None:
            return None
        return bool(self.driver_door_lock_status)


@dataclass(slots=True)
class WindowStatus:
    """Window positions and status."""

    left_front_window_percent: int | None = None
    right_front_window_percent: int | None = None
    left_rear_window_percent: int | None = None
    right_rear_window_percent: int | None = None
    driver_window_status: bool | None = None
    right_front_window_status: bool | None = None
    left_rear_window_status: bool | None = None
    right_rear_window_status: bool | None = None
    sun_shade: int | None = None
    is_support_windows_remote_control: int | None = None


@dataclass(slots=True)
class ConnectivityStatus:
    """Connectivity status (Bluetooth, hotspot)."""

    bluetooth_state: bool | None = None
    bluetooth_addr: str | None = None
    hotspot_state: bool | None = None


@dataclass(slots=True)
class SeatComfortStatus:
    """Seat and comfort features status (C10/B10 only)."""

    driver_seat_heating: int | None = None
    driver_seat_ventilation: int | None = None
    passenger_seat_heating: int | None = None
    passenger_seat_ventilation: int | None = None
    steering_wheel_heating: int | None = None
    steering_wheel_heater_minutes: int | None = None


@dataclass(slots=True)
class SecurityStatus:
    """Vehicle security and exterior status."""

    vehicle_security_active: VehicleSecurityState | None = None
    sentry_mode: int | None = None
    left_mirror_heating: int | None = None
    right_mirror_heating: int | None = None
    roof_opening: int | None = None

    @property
    def is_security_active(self) -> bool | None:
        """True if anti-theft is active (values 1, 2, 3). None if unknown."""
        if self.vehicle_security_active is None:
            return None
        return self.vehicle_security_active in (
            VehicleSecurityState.ACTIVE_1,
            VehicleSecurityState.ACTIVE_2,
            VehicleSecurityState.ACTIVE_3,
        )


@dataclass(slots=True)
class IgnitionStatus:
    """Ignition / key position status."""

    bcm_key_position_on1: bool | None = None
    bcm_key_position_on2: bool | None = None
    bcm_key_position_on3: bool | None = None


@dataclass(slots=True)
class VehicleStatus:
    """Parsed vehicle status from the API.

    Fields are grouped into typed sub-objects for clarity.
    Use ``VehicleStatus.from_dict(raw)`` to build from the raw API dict.
    """

    battery: BatteryStatus = field(default_factory=BatteryStatus)
    driving: DrivingStatus = field(default_factory=DrivingStatus)
    location: LocationStatus = field(default_factory=LocationStatus)
    climate: ClimateStatus = field(default_factory=ClimateStatus)
    doors: DoorStatus = field(default_factory=DoorStatus)
    windows: WindowStatus = field(default_factory=WindowStatus)
    tires: TirePressure = field(default_factory=TirePressure)
    connectivity: ConnectivityStatus = field(default_factory=ConnectivityStatus)
    seat_comfort: SeatComfortStatus = field(default_factory=SeatComfortStatus)
    security: SecurityStatus = field(default_factory=SecurityStatus)
    ignition: IgnitionStatus = field(default_factory=IgnitionStatus)

    # -- Timestamps --
    collect_time: datetime | None = None
    create_time: datetime | None = None

    # -- Raw dict for debug --
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, status_data: dict[str, Any]) -> VehicleStatus:
        """Build a ``VehicleStatus`` from the raw API status dict.

        Handles both T03-style responses (named fields at the top level)
        and C10/B10-style responses (numeric signal IDs inside a ``signal``
        sub-dict).
        """
        # Merge signal-based fields so the existing field extractors work
        merged = _merge_signal_to_named(status_data)

        # Parse timestamps
        timestamps: dict[str, Any] = {}
        for api_key, field_name in (("collectTime", "collect_time"), ("createTime", "create_time")):
            raw_ts = merged.get(api_key)
            if isinstance(raw_ts, str):
                with contextlib.suppress(ValueError):
                    timestamps[field_name] = datetime.strptime(raw_ts, _DATETIME_FMT)  # noqa: DTZ007

        return cls(
            battery=BatteryStatus.from_dict(merged),
            driving=DrivingStatus(**_extract_fields(merged, _DRIVING_FIELDS)),
            location=LocationStatus(**_extract_fields(merged, _LOCATION_FIELDS)),
            climate=ClimateStatus(**_extract_fields(merged, _CLIMATE_FIELDS)),
            doors=DoorStatus(**_extract_fields(merged, _DOOR_FIELDS)),
            windows=WindowStatus(**_extract_fields(merged, _WINDOW_FIELDS)),
            tires=TirePressure(**_extract_fields(merged, _TIRE_FIELDS)),
            connectivity=ConnectivityStatus(**_extract_fields(merged, _CONNECTIVITY_FIELDS)),
            seat_comfort=SeatComfortStatus(**_extract_fields(merged, _SEAT_COMFORT_FIELDS)),
            security=SecurityStatus(**_extract_fields(merged, _SECURITY_FIELDS)),
            ignition=IgnitionStatus(**_extract_fields(merged, _IGNITION_FIELDS)),
            raw=status_data,
            **timestamps,
        )

    # -- Convenience properties (delegate to sub-objects) --

    @property
    def is_locked(self) -> bool | None:
        """True if the vehicle is locked."""
        return self.doors.is_locked

    @property
    def is_plugged(self) -> bool:
        """True if a gun charger is connected."""
        if self.battery.is_charge_fast_gun_insert and self.driving.is_parked:
            return True

        if self.battery.ac_input_slow_charge is None:
            # When ac_input_slow_charge is None, we don't have the data
            # to determine if it's plugged in (maybe a T03 vehicle that is missing some data).
            # So fall back to charge_state for charging status

            gun_plugged = self.battery.charge_state in (
                ChargeState.CHARGING,
                ChargeState.FINISH,
                ChargeState.ERROR,
                ChargeState.SETTING,
                ChargeState.PAUSE,
            )

            return bool(gun_plugged and self.driving.is_parked)
        else:
            return bool(self.battery.is_charge_slow_gun_insert and self.driving.is_parked)

    @property
    def is_charging(self) -> bool | None:
        """True if the vehicle is currently charger plugin connected, is parked and the charging is started."""
        return self.battery.charge_state == ChargeState.CHARGING and self.driving.is_parked and self.battery.is_charging

    @property
    def is_regening(self) -> bool | None:
        """True if the vehicle is currently regeneratively braking (i.e., driving with battery charging)."""
        return self.battery.charge_state == ChargeState.REGENING and not self.driving.is_parked

    @property
    def is_parked(self) -> bool | None:
        """True if the vehicle is not driving.

        Complementary to ``is_driving``: the vehicle is considered parked
        when ignition is off **or** gear is in Park/Neutral.  Falls back
        to the speed-based check when ignition/gear data is unavailable.
        """
        driving = self.is_driving
        if driving is None:
            return self.driving.is_parked
        return not driving

    @property
    def is_driving(self) -> bool | None:
        """True if the vehicle is currently driving.

        Requires ignition ON3 active **and** gear in Drive or Reverse.
        Returns ``None`` when ignition or gear data is unavailable.
        """
        if self.ignition.bcm_key_position_on3 is None or self.driving.gear_status is None:
            return None
        return bool(
            self.ignition.bcm_key_position_on3 and self.driving.gear_status in (GearStatus.DRIVE, GearStatus.REVERSE)
        )

    @property
    def tire_pressure(self) -> TirePressure:
        """Structured tire pressure object."""
        return self.tires

    @property
    def tire_pressure_bar(self) -> dict[str, float | None]:
        """Tire pressures converted to bar (raw values are in kPa)."""
        return self.tires.all_bar


# ---------------------------------------------------------------------------
# API key → (sub-object attr, field name) mapping
# ---------------------------------------------------------------------------


_DRIVING_FIELDS: dict[str, str] = {
    "speed": "speed",
    "totalMileage": "total_mileage",
    "gearStatus": "gear_status",
    "vehicleState": "vehicle_state",
    "speedLimit": "speed_limit",
    "speedLimitUnit": "speed_limit_unit",
    "speedLimitActive": "speed_limit_active",
    "liveRemainingRange": "live_remaining_range",
    "maxRange": "max_range",
    "rangeMode": "range_mode",
    "parkingBrakeState": "parking_brake_state",
    "maxFuelRange": "max_fuel_range",
    "maxCombinedRange": "max_combined_range",
}

_LOCATION_FIELDS: dict[str, str] = {
    "latitude": "latitude",
    "longitude": "longitude",
}

_CLIMATE_FIELDS: dict[str, str] = {
    "acSwitch": "ac_switch",
    "acSetting": "ac_setting",
    "acSettingRight": "ac_setting_right",
    "interiorTemp": "interior_temp",
    "acAirVolume": "ac_air_volume",
    "acAirVolumeSetting": "ac_air_volume_setting",
    "acWindDirection": "ac_wind_direction",
    "acTempMode": "ac_temp_mode",
    "acCircleMode": "ac_circle_mode",
    "acCoolingAndHeating": "ac_cooling_and_heating",
    "outdoorTemp": "outdoor_temp",
    "minSingleTemp": "min_single_temp",
    "ptcState": "ptc_state",
    "ptcPowerSettingValue": "ptc_power_setting_value",
    "recirculationMode": "recirculation_mode",
    "windshieldDefrost": "windshield_defrost",
    "rearWindowHeating": "rear_window_heating",
    "climateMode": "climate_mode",
    "rapidCooling": "rapid_cooling",
    "rapidHeating": "rapid_heating",
    "acOperateMode": "ac_operate_mode",
}

_DOOR_FIELDS: dict[str, str] = {
    "driverDoorLockStatus": "driver_door_lock_status",
    "lbcmDriverDoorStatus": "lbcm_driver_door_status",
    "rbcmDriverDoorStatus": "rbcm_driver_door_status",
    "lbcmLeftRearDoorStatus": "lbcm_left_rear_door_status",
    "rbcmRightRearDoorStatus": "rbcm_right_rear_door_status",
    "bbcmBackDoorStatus": "bbcm_back_door_status",
    "bcmDoorCtrlAllow": "bcm_door_ctrl_allow",
}

_WINDOW_FIELDS: dict[str, str] = {
    "leftFrontWindowPercent": "left_front_window_percent",
    "rightFrontWindowPercent": "right_front_window_percent",
    "leftRearWindowPercent": "left_rear_window_percent",
    "rightRearWindowPercent": "right_rear_window_percent",
    "driverWindowStatus": "driver_window_status",
    "rightFrontWindowStatus": "right_front_window_status",
    "leftRearWindowStatus": "left_rear_window_status",
    "rightRearWindowStatus": "right_rear_window_status",
    "sunShade": "sun_shade",
    "isSupportWindowsRemoteControl": "is_support_windows_remote_control",
}

_TIRE_FIELDS: dict[str, str] = {
    "leftFrontTirePressure": "front_left_kpa",
    "leftFrontTirePressureState": "front_left_state",
    "rightFrontTirePressure": "front_right_kpa",
    "rightFrontTirePressureState": "front_right_state",
    "leftRearTirePressure": "rear_left_kpa",
    "leftRearTirePressureState": "rear_left_state",
    "rightRearTirePressure": "rear_right_kpa",
    "rightRearTirePressureState": "rear_right_state",
}

_CONNECTIVITY_FIELDS: dict[str, str] = {
    "bluetoothState": "bluetooth_state",
    "bluetoothAddr": "bluetooth_addr",
    "hotspotState": "hotspot_state",
}

_IGNITION_FIELDS: dict[str, str] = {
    "bcmKeyPositionOn1": "bcm_key_position_on1",
    "bcmKeyPositionOn2": "bcm_key_position_on2",
    "bcmKeyPositionOn3": "bcm_key_position_on3",
}

_SEAT_COMFORT_FIELDS: dict[str, str] = {
    "driverSeatHeating": "driver_seat_heating",
    "driverSeatVentilation": "driver_seat_ventilation",
    "passengerSeatHeating": "passenger_seat_heating",
    "passengerSeatVentilation": "passenger_seat_ventilation",
    "steeringWheelHeating": "steering_wheel_heating",
    "steeringWheelHeaterMinutes": "steering_wheel_heater_minutes",
}

_SECURITY_FIELDS: dict[str, str] = {
    "vehicleSecurityActive": "vehicle_security_active",
    "sentryMode": "sentry_mode",
    "leftMirrorHeating": "left_mirror_heating",
    "rightMirrorHeating": "right_mirror_heating",
    "roofOpening": "roof_opening",
}

_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"

# ---------------------------------------------------------------------------
# Signal ID → named API field mapping (C10/B10 → T03-style fields)
# ---------------------------------------------------------------------------
# The T03 returns named fields (``soc``, ``speed``, …) directly.  The C10/B10
# returns numeric signal IDs inside a nested ``signal`` dict.  This mapping
# converts signal IDs to the named keys that the existing dataclass parsers
# expect, based on the verified APK signal table.

_SIGNAL_TO_NAMED: dict[str, str] = {
    # Battery / charging
    "47": "acInputSlowCharge",
    "1204": "soc",
    "100003": "preciseSoc",
    "1200": "chargeRemainTime",
    "1178": "batteryCurrent",
    "1177": "batteryVoltage",
    "1197": "dcInputFastCharge",
    "1149": "chargeState",
    "1182": "minBatteryTemp",
    "1186": "batteryThermalRequest",
    "3736": "chargeCompleted",
    "48": "healthyChargeEnabled",
    "3737": "chargeScheduleCancelledOnce",
    # Range
    "3259": "expectedFuelMileage",
    "3260": "expectedMileage",
    "3261": "expectedCombinedMileage",
    "2188": "liveRemainingRange",
    "3256": "maxFuelRange",
    "3257": "maxRange",
    "3258": "maxCombinedRange",
    "3262": "rangeMode",
    # Driving
    "1319": "speed",
    "1318": "totalMileage",
    "1010": "gearStatus",
    "1944": "vehicleState",
    "1480": "parkingBrakeState",
    "6048": "speedLimit",
    "6047": "speedLimitUnit",
    "12054": "speedLimitActive",
    # Location is handled explicitly in _merge_signal_to_named so the
    # signed signals "2"/"3" can take priority over the absolute-value ones.
    # Climate
    "1938": "acSwitch",
    "2183": "acSetting",
    "2184": "acSettingRight",
    "1349": "interiorTemp",
    "1943": "recirculationMode",
    "1945": "windshieldDefrost",
    "1946": "rearWindowHeating",
    "3713": "climateMode",
    "2669": "rapidCooling",
    "2681": "rapidHeating",
    "1939": "acOperateMode",
    "1941": "acAirVolume",
    # Windows (position percent)
    "3727": "leftFrontWindowPercent",
    "3728": "rightFrontWindowPercent",
    "1879": "leftRearWindowPercent",
    "1880": "rightRearWindowPercent",
    # Windows (open/closed boolean)
    "1693": "driverWindowStatus",
    "1694": "rightFrontWindowStatus",
    "1695": "leftRearWindowStatus",
    "1696": "rightRearWindowStatus",
    # Doors
    "1298": "driverDoorLockStatus",
    "1277": "lbcmDriverDoorStatus",
    "1278": "rbcmDriverDoorStatus",
    "1279": "lbcmLeftRearDoorStatus",
    "1280": "rbcmRightRearDoorStatus",
    "1281": "bbcmBackDoorStatus",
    # Tire pressure
    "2667": "leftFrontTirePressure",
    "2653": "rightFrontTirePressure",
    "2646": "leftRearTirePressure",
    "2660": "rightRearTirePressure",
    "2641": "leftFrontTirePressureState",
    "2648": "rightFrontTirePressureState",
    "2655": "leftRearTirePressureState",
    "2662": "rightRearTirePressureState",
    # Ignition
    "1256": "bcmKeyPositionOn1",
    "1257": "bcmKeyPositionOn2",
    "1258": "bcmKeyPositionOn3",
    # Seat comfort
    "2100": "driverSeatHeating",
    "2101": "driverSeatVentilation",
    "2118": "passengerSeatHeating",
    "2119": "passengerSeatVentilation",
    "1816": "steeringWheelHeating",
    "1624": "steeringWheelHeaterMinutes",
    # Security / exterior
    "1255": "vehicleSecurityActive",
    "3636": "sentryMode",
    "49": "leftMirrorHeating",
    "50": "rightMirrorHeating",
    "1724": "roofOpening",
}


def _merge_signal_to_named(status_data: dict[str, Any]) -> dict[str, Any]:
    """Convert signal-based C10/B10 responses to named fields for uniform parsing.

    Named fields already present in *status_data* take priority over
    signal-derived values so T03-style responses pass through unchanged.
    """
    signal = status_data.get("signal")
    if not isinstance(signal, dict):
        return status_data

    merged = dict(status_data)
    for signal_id, named_field in _SIGNAL_TO_NAMED.items():
        if signal_id in signal and named_field not in merged:
            merged[named_field] = signal[signal_id]

    # GPS coordinates, in priority order:
    #   signals "2"/"3"   -> SIGNED coordinates (preserve hemisphere sign)
    #   signals 3724/3725 -> absolute value (drops West/South sign)
    #   signals 2191/2190 -> absolute value fallback
    # The signed signals must win so West-longitude (Portugal/UK) and
    # South-latitude positions are not mirrored to the wrong hemisphere.
    # See https://github.com/markoceri/leapconnect/issues/21
    if "longitude" not in merged:
        for lon_signal in ("2", "3724", "2191"):
            if lon_signal in signal:
                merged["longitude"] = signal[lon_signal]
                break
    if "latitude" not in merged:
        for lat_signal in ("3", "3725", "2190"):
            if lat_signal in signal:
                merged["latitude"] = signal[lat_signal]
                break

    # Convert signal timestamp (milliseconds) to collectTime string
    if "sts" in signal and "collectTime" not in merged:
        sts = signal["sts"]
        if isinstance(sts, (int, float)):
            ts = sts / 1000 if sts > 9_999_999_999 else sts
            with contextlib.suppress(OSError, ValueError, OverflowError):
                merged["collectTime"] = datetime.fromtimestamp(ts).strftime(_DATETIME_FMT)  # noqa: DTZ006

    # Derive acCoolingAndHeating from legacy signals 1940 + 1949
    # when the newer unified signal 3713 is absent.
    # Truth table:
    #   1940=0,1949=0 → 0 (wind)  |  1940=0,1949=1 → 2 (hot)
    #   1940=1/2,1949=0 → 1 (cold)  |  1940=1/2,1949=1 → 1 (cold, priority)
    if "acCoolingAndHeating" not in merged and "3713" not in signal:
        raw_1940 = signal.get("1940")
        raw_1949 = signal.get("1949")
        s1940 = str(raw_1940) if raw_1940 is not None else ""
        s1949 = str(raw_1949) if raw_1949 is not None else ""
        if s1940 and s1949:
            if s1940 == "0" and s1949 == "1":
                merged["acCoolingAndHeating"] = 2  # hot
            elif s1940 in ("1", "2"):
                merged["acCoolingAndHeating"] = 1  # cold (cooling priority)
            else:
                merged["acCoolingAndHeating"] = 0  # wind

    # Map config.3 (charge plan) to named fields for BatteryStatus
    config = status_data.get("config")
    if isinstance(config, dict):
        charge_plan = config.get("3")
        if isinstance(charge_plan, dict):
            if "chargesocSetting" not in merged and "percent" in charge_plan:
                merged["chargesocSetting"] = charge_plan["percent"]
            if "chargeScheduleEnabled" not in merged and "isEnable" in charge_plan:
                merged["chargeScheduleEnabled"] = charge_plan["isEnable"]
            if "chargeScheduleStart" not in merged and "beginTime" in charge_plan:
                merged["chargeScheduleStart"] = charge_plan["beginTime"]
            if "chargeScheduleEnd" not in merged and "endTime" in charge_plan:
                merged["chargeScheduleEnd"] = charge_plan["endTime"]
            if "chargeScheduleCycles" not in merged and "cycles" in charge_plan:
                merged["chargeScheduleCycles"] = charge_plan["cycles"]
            if "chargeScheduleCirculation" not in merged and "circulation" in charge_plan:
                merged["chargeScheduleCirculation"] = charge_plan["circulation"]
            if "chargeScheduleRecharge" not in merged and "recharge" in charge_plan:
                merged["chargeScheduleRecharge"] = charge_plan["recharge"]

    return merged


def _extract_fields(data: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Extract fields from *data* using an API-key → field-name mapping."""
    return {field_name: data[api_key] for api_key, field_name in mapping.items() if api_key in data}


@dataclass(slots=True)
class RemoteActionSpec:
    """Base remote-control action payload."""

    cmd_id: str
    cmd_content: str
    required_right: VehicleRight | None = None
    requires_pin: bool = True


# ---------------------------------------------------------------------------
# Enums for remote-control command parameter values
# ---------------------------------------------------------------------------


class LockValue(StrEnum):
    """Values for lock/unlock command."""

    LOCK = "lock"
    UNLOCK = "unlock"


class ToggleValue(StrEnum):
    """Generic true/false toggle used by multiple commands."""

    TRUE = "true"
    FALSE = "false"


class BatteryPreheatValue(StrEnum):
    """Values for battery preheat command."""

    ON = "ptcon"
    OFF = "ptcoff"


class SentryModeValue(StrEnum):
    """Values for sentry mode (sentinel / dashcam) command."""

    ON = "1"
    OFF = "0"


class ChargeToggleValue(StrEnum):
    """Values for start/stop charging command (cmd_id=193)."""

    START = "start"
    STOP = "stop"


class SteeringWheelHeatValue(StrEnum):
    """Values for steering wheel heat command (cmd_id=320)."""

    ON = "on"
    OFF = "off"


class FuelHeatingValue(StrEnum):
    """Values for fuel heating command (cmd_id=380)."""

    ON = "1"
    OFF = "0"


class HealthyChargingValue(StrEnum):
    """Values for healthy charging command (cmd_id=480)."""

    ON = "1"
    OFF = "0"


class On3Value(StrEnum):
    """Values for ON3 command (cmd_id=410)."""

    ON = "on"
    OFF = "off"


class RearviewMirrorHeatValue(StrEnum):
    """Values for rearview mirror heat command (cmd_id=440)."""

    ON = "on"
    OFF = "off"


class SunroofValue(StrEnum):
    """Values for sunroof command (cmd_id=300)."""

    OPEN = "open"
    CLOSE = "close"


class SunshadeValue(StrEnum):
    """Convenience values for sunshade position (range: 0-10)."""

    OPEN = "10"
    CLOSE = "0"


class WindowsValue(StrEnum):
    """Convenience values for windows position (range: 0-100)."""

    OPEN = "100"
    CLOSE = "0"


class ClimateCircle(StrEnum):
    """Air circulation mode."""

    IN = "in"
    OUT = "out"


class ClimateMode(StrEnum):
    """Climate mode."""

    COLD = "cold"
    HOT = "hot"
    WIND = "wind"


class ClimateOperate(StrEnum):
    """Climate operate mode."""

    MANUAL = "manual"
    AUTO = "auto"
    CLOSE = "close"


class ClimatePosition(StrEnum):
    """Climate air position."""

    ALL = "all"


class ClimateWindshield(StrEnum):
    """Windshield defrost setting."""

    OFF = "0"
    ON = "1"


class MusicOperation(StrEnum):
    """Values for music control command (cmd_id=270)."""

    PLAY = "play"
    PAUSE = "pause"
    NEXT = "next"
    PREVIOUS = "previous"


class VideoOperation(StrEnum):
    """Values for video control command (cmd_id=290)."""

    PLAY = "play"
    PAUSE = "pause"
    NEXT = "next"
    PREVIOUS = "previous"


class ChargerOperation(StrEnum):
    """Values for charger unlock command."""

    UNLOCK = "unlock"


# ---------------------------------------------------------------------------
# Typed remote-control action subclasses
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RemoteActionCtlLock(RemoteActionSpec):
    """Lock/unlock command (cmd_id=110)."""

    value: str = LockValue.LOCK
    cmd_id: str = field(default="110", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlTrunk(RemoteActionSpec):
    """Trunk open/close command (cmd_id=130)."""

    value: str = ToggleValue.TRUE
    cmd_id: str = field(default="130", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlFindCar(RemoteActionSpec):
    """Find car command (cmd_id=120)."""

    value: str = ToggleValue.TRUE
    cmd_id: str = field(default="120", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlHotspot(RemoteActionSpec):
    """Hotspot / connectivity command (cmd_id=140)."""

    value: str = "findCar"
    cmd_id: str = field(default="140", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlAutopark(RemoteActionSpec):
    """Auto park / summon command (cmd_id=150)."""

    value: str = "findCar"
    cmd_id: str = field(default="150", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlSunshade(RemoteActionSpec):
    """Sunshade control command (cmd_id=240). Value: 0 (closed) to 10 (fully open)."""

    value: str = SunshadeValue.OPEN
    cmd_id: str = field(default="240", init=False)
    cmd_content: str = field(default="", init=False)

    _VALUE_RANGE: range = field(default=range(0, 11), init=False, repr=False)

    def __post_init__(self) -> None:
        if int(self.value) not in self._VALUE_RANGE:
            raise ValueError(f"Sunshade value must be 0-10, got {self.value!r}")
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlBatteryPreheat(RemoteActionSpec):
    """Battery preheat command (cmd_id=160)."""

    value: str = BatteryPreheatValue.ON
    cmd_id: str = field(default="160", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlSentryMode(RemoteActionSpec):
    """Sentry mode (sentinel / dashcam) command (cmd_id=220).

    Value: ``"1"`` (on) or ``"0"`` (off).
    """

    value: str = SentryModeValue.ON
    cmd_id: str = field(default="220", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlToggleCharge(RemoteActionSpec):
    """Start/stop charging command (cmd_id=193).

    Value: ``"start"`` or ``"stop"``.
    """

    value: str = ChargeToggleValue.START
    cmd_id: str = field(default="193", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlSteeringWheelHeat(RemoteActionSpec):
    """Steering wheel heat command (cmd_id=320).

    Value: ``"on"`` or ``"off"``.
    """

    value: str = SteeringWheelHeatValue.ON
    cmd_id: str = field(default="320", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlFuelHeating(RemoteActionSpec):
    """Fuel heating command (cmd_id=380).

    Value: ``"1"`` (on) or ``"0"`` (off).
    """

    value: str = FuelHeatingValue.ON
    cmd_id: str = field(default="380", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlHealthyCharging(RemoteActionSpec):
    """Healthy charging command (cmd_id=480).

    Value: ``"1"`` (on) or ``"0"`` (off).
    Toggles battery-protecting charging mode (80% SOC limit).
    """

    value: str = HealthyChargingValue.ON
    cmd_id: str = field(default="480", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlOn3(RemoteActionSpec):
    """ON3 command (cmd_id=410).

    Value: ``"on"`` or ``"off"``.
    Enables or disables ON3 mode (domestic models).
    """

    value: str = On3Value.ON
    cmd_id: str = field(default="410", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"on3": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlRearviewMirrorHeat(RemoteActionSpec):
    """Rearview mirror heat command (cmd_id=440).

    Value: ``"on"`` or ``"off"``.
    """

    value: str = RearviewMirrorHeatValue.ON
    cmd_id: str = field(default="440", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlSpeedLimit(RemoteActionSpec):
    """Speed limit command (cmd_id=510).

    Value: speed in km/h as a string (e.g. ``"80"``).
    """

    value: str = "80"
    cmd_id: str = field(default="510", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlSeatHeat(RemoteActionSpec):
    """Seat heat command (cmd_id=301).

    Value: ``"position,level"`` — e.g. ``"1,3"`` for left-front seat at level 3.
    Position: 1=left_front, 2=copilot, 3=driver, 4=right_front, 5=left_rear, 6=right_rear.
    Level: 0 (off) to 3 (max).
    """

    value: str = "1,3"
    cmd_id: str = field(default="301", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlSeatVentilation(RemoteActionSpec):
    """Seat ventilation command (cmd_id=370).

    Value: ``"position,level"`` — e.g. ``"1,3"`` for left-front seat at level 3.
    Position: 1=left_front, 2=copilot, 3=driver, 4=right_front, 5=left_rear, 6=right_rear.
    Level: 0 (off) to 3 (max).
    """

    value: str = "1,3"
    cmd_id: str = field(default="370", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlSunroof(RemoteActionSpec):
    """Sunroof command (cmd_id=300).

    Value: ``"open"`` or ``"close"``.
    """

    value: str = SunroofValue.OPEN
    cmd_id: str = field(default="300", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlWindows(RemoteActionSpec):
    """Windows open/close command (cmd_id=230). Value: 0 (closed) to 100 (fully open).

    .. note::

       The 0-100 range is the C10/T03 behaviour. A **B10** was observed on-car to use a **0-10**
       scale instead, actuating only ``0 / 2 / 5 / 10`` (closed / ~20% / ~50% / fully open) — other
       values are accepted by the cloud (``code=0``) but **ignored by the car**. Callers that want a
       uniform 0-100% UI should map it to the model's native range (B10: ``round(pct / 10)``).
    """

    value: str = WindowsValue.OPEN
    cmd_id: str = field(default="230", init=False)
    cmd_content: str = field(default="", init=False)

    _VALUE_RANGE: range = field(default=range(0, 101), init=False, repr=False)

    def __post_init__(self) -> None:
        if int(self.value) not in self._VALUE_RANGE:
            raise ValueError(f"Windows value must be 0-100, got {self.value!r}")
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlClimate(RemoteActionSpec):
    """Climate / AC command (cmd_id=170)."""

    circle: str = ClimateCircle.OUT
    mode: str = ClimateMode.WIND
    operate: str = ClimateOperate.MANUAL
    position: str = ClimatePosition.ALL
    temperature: str = "26"
    windlevel: int = 3
    wshld: str = ClimateWindshield.OFF
    cmd_id: str = field(default="170", init=False)
    cmd_content: str = field(default="", init=False)

    _WINDLEVEL_RANGE: range = field(default=range(1, 8), init=False, repr=False)

    def __post_init__(self) -> None:
        if self.windlevel not in self._WINDLEVEL_RANGE:
            raise ValueError(f"windlevel must be 1-7, got {self.windlevel!r}")
        self.cmd_content = json.dumps(
            {
                "circle": self.circle,
                "mode": self.mode,
                "operate": self.operate,
                "position": self.position,
                "temperature": self.temperature,
                "windlevel": str(self.windlevel),
                "wshld": self.wshld,
            },
            separators=(",", ":"),
        )


@dataclass(slots=True)
class RemoteActionCtlClimateSchedule(RemoteActionSpec):
    """Climate schedule command (cmd_id=171).

    Sends one or more scheduled climate activations to the vehicle.
    The ``controls`` list contains individual schedule entries.

    .. note::

       Each invocation is a **full-state replacement**: the ``controls``
       array must contain *all* active schedules.  An empty list cancels
       every existing schedule.
    """

    cmd_id: str = field(default="171", init=False)
    cmd_content: str = field(default="", init=False)
    controls: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps(
            {"controls": self.controls},
            separators=(",", ":"),
        )


@dataclass(slots=True)
class RemoteActionCtlChargePlan(RemoteActionSpec):
    """Charge plan / schedule command (cmd_id=190)."""

    charge_enable: int = 0
    chargesoc: int = 80
    circulation: int = 0
    cycles: str = ""
    endtime: str = ""
    recharge: int = 0
    starttime: str = ""
    cmd_id: str = field(default="190", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps(
            {
                "chargeEnable": self.charge_enable,
                "chargesoc": self.chargesoc,
                "circulation": self.circulation,
                "cycles": self.cycles,
                "endtime": self.endtime,
                "recharge": self.recharge,
                "starttime": self.starttime,
            },
            separators=(",", ":"),
        )


@dataclass(slots=True)
class RemoteActionCtlUnlockCharger(RemoteActionSpec):
    """Unlock charger connector command (cmd_id=192)."""

    operation: str = ChargerOperation.UNLOCK
    cmd_id: str = field(default="192", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"operation": self.operation}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlSendDestination(RemoteActionSpec):
    """Send navigation destination command (cmd_id=180)."""

    address: str = ""
    address_name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    cmd_id: str = field(default="180", init=False)
    cmd_content: str = field(default="", init=False)
    requires_pin: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps(
            {
                "address": self.address,
                "addressname": self.address_name,
                "latitude": str(self.latitude),
                "linenum": "0",
                "longitude": str(self.longitude),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )


@dataclass(slots=True)
class RemoteActionCtlBleKeyRestart(RemoteActionSpec):
    """BLE key restart command (cmd_id=430).

    Value: ``"restart"``.
    Restarts the BLE (Bluetooth Low Energy) digital key module.
    """

    value: str = "restart"
    cmd_id: str = field(default="430", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"value": self.value}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlMusic(RemoteActionSpec):
    """Music control command (cmd_id=270).

    Operation: ``"play"``, ``"pause"``, ``"next"``, ``"previous"``.
    """

    operation: str = "play"
    cmd_id: str = field(default="270", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"operation": self.operation}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlVideo(RemoteActionSpec):
    """Video control command (cmd_id=290).

    Operation: ``"play"``, ``"pause"``, ``"next"``, ``"previous"``.
    """

    operation: str = "play"
    cmd_id: str = field(default="290", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"operation": self.operation}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlFotaDownload(RemoteActionSpec):
    """FOTA download command (cmd_id=390).

    Triggers firmware-over-the-air download for the given task ID.
    """

    task_id: int = 0
    cmd_id: str = field(default="390", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"taskId": self.task_id}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlFotaInstall(RemoteActionSpec):
    """FOTA install command (cmd_id=391).

    Triggers firmware-over-the-air installation for the given task ID.
    """

    task_id: int = 0
    cmd_id: str = field(default="391", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"taskId": self.task_id}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlFotaSchedule(RemoteActionSpec):
    """FOTA scheduled install command (cmd_id=392).

    Schedules a firmware-over-the-air installation.
    The ``cmd_content`` is passed directly as a JSON string.
    """

    task_id: int = 0
    schedule_time: str = ""
    cmd_id: str = field(default="392", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps(
            {"taskId": self.task_id, "scheduleTime": self.schedule_time},
            separators=(",", ":"),
        )


@dataclass(slots=True)
class RemoteActionCtlRearSeats(RemoteActionSpec):
    """Rear seats control command (cmd_id=470).

    Controls 2nd/3rd row seat adjustments (C16 only).
    The ``seat_info`` parameter is passed as a string value.
    """

    seat_info: str = ""
    cmd_id: str = field(default="470", init=False)
    cmd_content: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps({"seatInfo": self.seat_info}, separators=(",", ":"))


@dataclass(slots=True)
class RemoteActionCtlPrepareCar(RemoteActionSpec):
    """Prepare car / pre-conditioning command (cmd_id=360).

    Activates pre-conditioning (climate, seat heat, etc.) on C10/B10 models.
    The ``cmd_content`` is the full JSON payload string.
    """

    cmd_id: str = field(default="360", init=False)
    cmd_content: str = ""


@dataclass(slots=True)
class RemoteActionCtlPrepareCarSchedule(RemoteActionSpec):
    """Prepare-car schedule command (cmd_id=361).

    Schedules one or more one-touch vehicle-preparation activations (the
    "prepare car" alarm clock) on C10/B10 models. Each ``controls`` entry
    wraps a ``datacontent`` bundle (climate, seats, steering-wheel/mirror
    heating, navigation) with ``days`` / ``start_time`` / ``set_id`` / ``enable``.

    .. note::

       Each invocation is a **full-state replacement**: the ``controls``
       array must contain *all* active schedule entries. An empty list
       cancels every existing prepare-car schedule.
    """

    cmd_id: str = field(default="361", init=False)
    cmd_content: str = field(default="", init=False)
    controls: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cmd_content = json.dumps(
            {"controls": self.controls},
            separators=(",", ":"),
        )


@dataclass(slots=True)
class RemoteActionCtlSeatAdjust(RemoteActionSpec):
    """Seat adjust command (cmd_id=280).

    Available on C10/C16 models.
    The ``cmd_content`` is the full JSON payload string.
    """

    cmd_id: str = field(default="280", init=False)
    cmd_content: str = ""


@dataclass(slots=True)
class RemoteActionCtlPilotedParking(RemoteActionSpec):
    """Piloted parking command (cmd_id=350).

    Available on C10/C16 models.
    The ``cmd_content`` is the full JSON payload string.
    """

    cmd_id: str = field(default="350", init=False)
    cmd_content: str = ""


@dataclass(slots=True)
class RemoteActionResult:
    """Result of a remote-control action."""

    action: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


# ---------------------------------------------------------------------------
# Energy consumption models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WeeklyConsumption:
    """One week of energy consumption data."""

    week_start: str
    week_end: str
    hundred_km_ec: float
    hundred_mi_kwh_ec: float
    week_start_ms: int | None = None
    week_end_ms: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeeklyConsumption:
        """Build from a raw API dict."""
        return cls(
            week_start=data.get("weekStart", ""),
            week_end=data.get("weekEnd", ""),
            hundred_km_ec=float(data.get("hundredKmEC", 0)),
            hundred_mi_kwh_ec=float(data.get("hundredMiKwhEC", 0)),
            week_start_ms=data.get("xWeekStart"),
            week_end_ms=data.get("xWeekEnd"),
        )


@dataclass(frozen=True, slots=True)
class ConsumptionRank:
    """Current consumption rank compared to other drivers."""

    result: int
    rank: str
    hundred_km_ec: float
    hundred_mi_kwh_ec: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsumptionRank:
        """Build from a raw API dict."""
        return cls(
            result=int(data.get("result", 0)),
            rank=data.get("rank", ""),
            hundred_km_ec=float(data.get("hundredKmEC", 0)),
            hundred_mi_kwh_ec=float(data.get("hundredMiKwhEC", 0)),
        )


@dataclass(frozen=True, slots=True)
class ConsumptionWeeklyRank:
    """Six-week energy consumption history with ranking."""

    rank: ConsumptionRank
    weekly: list[WeeklyConsumption]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsumptionWeeklyRank:
        """Build from the API response ``data`` field."""
        rank_data = data.get("rankResult") or {}
        weekly_data = data.get("weeklyEC") or []
        return cls(
            rank=ConsumptionRank.from_dict(rank_data),
            weekly=[WeeklyConsumption.from_dict(w) for w in weekly_data],
        )


@dataclass(frozen=True, slots=True)
class ConsumptionLastWeekBreakdown:
    """Last-week energy breakdown by category (kWh)."""

    driver_ec: float
    ac_ec: float
    other_ec: float

    @property
    def total_ec(self) -> float:
        """Total energy consumption (kWh)."""
        return round(self.driver_ec + self.ac_ec + self.other_ec, 2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsumptionLastWeekBreakdown:
        """Build from the API response ``data`` field."""
        return cls(
            driver_ec=float(data.get("driverEC", 0)),
            ac_ec=float(data.get("acEC", 0)),
            other_ec=float(data.get("otherEC", 0)),
        )


# ---------------------------------------------------------------------------
# Charging record models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChargeRecord:
    """A single charging session record."""

    start_ts: int
    end_ts: int
    charge_type: ChargeType
    energy_kwh: float
    longitude: str | None
    latitude: str | None
    timezone: str | None

    @property
    def start_datetime(self) -> datetime | None:
        """Convert start epoch ms to a datetime."""
        if not self.start_ts:
            return None
        return datetime.fromtimestamp(self.start_ts / 1000)  # noqa: DTZ006

    @property
    def end_datetime(self) -> datetime | None:
        """Convert end epoch ms to a datetime."""
        if not self.end_ts:
            return None
        return datetime.fromtimestamp(self.end_ts / 1000)  # noqa: DTZ006

    @property
    def duration_seconds(self) -> int | None:
        """Duration of the charging session in seconds."""
        if not self.start_ts or not self.end_ts:
            return None
        return (self.end_ts - self.start_ts) // 1000

    @property
    def is_fast_charge(self) -> bool:
        return self.charge_type == ChargeType.DC

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChargeRecord:
        raw_type = str(data.get("chargeType", "1"))
        try:
            charge_type = ChargeType(raw_type)
        except ValueError:
            charge_type = ChargeType.AC
        return cls(
            start_ts=int(data.get("chargeGunStartTs", 0)),
            end_ts=int(data.get("chargeGunEndTs", 0)),
            charge_type=charge_type,
            energy_kwh=float(data.get("chargeInEnergy", 0)),
            longitude=data.get("chargeStartLongitude"),
            latitude=data.get("chargeStartLatitude"),
            timezone=data.get("zone"),
        )


@dataclass(frozen=True, slots=True)
class ChargeDailyDetailPage:
    """Paginated charging daily detail response."""

    records: list[ChargeRecord]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChargeDailyDetailPage:
        return cls(
            records=[ChargeRecord.from_dict(r) for r in (data.get("list") or [])],
        )


# ---------------------------------------------------------------------------
# Message models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Message:
    """A single notification message from the message list."""

    id: int
    vin: str | None
    title: str | None
    message: str | None
    send_time: int | None  # epoch ms
    read_flag: int | None  # 0=unread, 1=read
    url: str | None
    msg_type: int | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def send_datetime(self) -> datetime | None:
        """Convert send_time epoch ms to a datetime."""
        if self.send_time is None:
            return None
        return datetime.fromtimestamp(self.send_time / 1000)  # noqa: DTZ006

    @property
    def is_read(self) -> bool:
        """True if the message has been read."""
        return self.read_flag == 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """Build a Message from a raw API dict."""
        return cls(
            id=data.get("id", 0),
            vin=data.get("vin"),
            title=data.get("title"),
            message=data.get("message"),
            send_time=data.get("sendTime"),
            read_flag=data.get("readFlag"),
            url=data.get("url"),
            msg_type=data.get("msgType"),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class MessageList:
    """Paginated message list response."""

    count: int
    messages: list[Message]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MessageList:
        """Build a MessageList from the API response 'data' field."""
        return cls(
            count=data.get("count", 0),
            messages=[Message.from_dict(m) for m in (data.get("list") or [])],
        )
