"""Leapmotor API data models."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any

# ---------------------------------------------------------------------------
# Enums and data classes for structured vehicle status and metadata.
# ---------------------------------------------------------------------------


class ChargeState(IntEnum):
    """Charging state codes reported by the vehicle."""

    NOT_CONNECTED = 0
    AC_CONNECTED = 1
    DC_CONNECTED = 2  # ???


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
    rights: str | None = None
    abilities: list[str] | None = None
    module_rights: str | None = None
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
            user_nickname=data.get("userNickname"),
            vehicle_nickname=data.get("vehicleNickname"),
            mobile_number=data.get("mobileNumber"),
            out_color=data.get("outColor"),
            is_shared=is_shared,
            share_time=data.get("shareTime"),
            expire_time=data.get("expireTime"),
            duration_type=data.get("durationType"),
            seat_layout=data.get("seatLayout"),
            rudder=data.get("rudder"),
            year=data.get("year"),
            rights=data.get("rights"),
            abilities=data.get("abilities"),
            module_rights=data.get("moduleRights"),
            allocation_code=data.get("allocationCode"),
            raw=data,
        )


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
class BatteryStatus:
    """Battery and charging status."""

    soc: int | None = None
    charge_state: ChargeState | None = None
    charge_remain_time: int | None = None
    charge_soc_setting: int | None = None
    charge_time_setting: str | None = None
    dc_input_fast_charge: int | None = None
    dump_energy: int | None = None
    battery_current: float | None = None
    battery_voltage: float | None = None
    expected_mileage: int | None = None

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
        return bool(self.charging_power_kw is not None and self.charge_remain_time is not None)

    @property
    def is_discharging(self) -> bool | None:
        """True if the battery is actively discharging (e.g., driving or powering onboard systems)."""
        return bool(self.discharging_power_kw is not None and self.discharging_power_kw > 0)

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
            charge_state=charge_state,
            charge_remain_time=data.get("chargeRemainTime"),
            charge_soc_setting=data.get("chargesocSetting"),
            charge_time_setting=data.get("chargeTimeSetting"),
            dc_input_fast_charge=data.get("dcInputFastCharge"),
            dump_energy=data.get("dumpEnergy"),
            battery_current=data.get("batteryCurrent"),
            battery_voltage=data.get("batteryVoltage"),
            expected_mileage=data.get("expectedMileage"),
        )


@dataclass(slots=True)
class DrivingStatus:
    """Driving / motion status."""

    speed: int | None = None
    total_mileage: int | None = None
    gear_status: int | None = None

    @property
    def is_parked(self) -> bool | None:
        """True if the vehicle is stationary."""
        if self.speed is None:
            return None
        return self.speed == 0


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
    ac_air_volume: int | None = None
    ac_air_volume_setting: int | None = None
    ac_wind_direction: int | None = None
    ac_temp_mode: bool | None = None
    ac_circle_mode: bool | None = None
    ac_cooling_and_heating: int | None = None
    outdoor_temp: int | None = None
    min_single_temp: int | None = None
    ptc_state: int | None = None
    ptc_power_setting_value: int | None = None


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
class IgnitionStatus:
    """Ignition / key position status."""

    bcm_key_position_on1: bool | None = None
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
    ignition: IgnitionStatus = field(default_factory=IgnitionStatus)

    # -- Timestamps --
    collect_time: datetime | None = None
    create_time: datetime | None = None

    # -- Raw dict for debug --
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, status_data: dict[str, Any]) -> VehicleStatus:
        """Build a ``VehicleStatus`` from the raw API status dict."""
        # Parse timestamps
        timestamps: dict[str, Any] = {}
        for api_key, field_name in (("collectTime", "collect_time"), ("createTime", "create_time")):
            raw_ts = status_data.get(api_key)
            if isinstance(raw_ts, str):
                with contextlib.suppress(ValueError):
                    timestamps[field_name] = datetime.strptime(raw_ts, _DATETIME_FMT)  # noqa: DTZ007

        return cls(
            battery=BatteryStatus.from_dict(status_data),
            driving=DrivingStatus(**_extract_fields(status_data, _DRIVING_FIELDS)),
            location=LocationStatus(**_extract_fields(status_data, _LOCATION_FIELDS)),
            climate=ClimateStatus(**_extract_fields(status_data, _CLIMATE_FIELDS)),
            doors=DoorStatus(**_extract_fields(status_data, _DOOR_FIELDS)),
            windows=WindowStatus(**_extract_fields(status_data, _WINDOW_FIELDS)),
            tires=TirePressure(**_extract_fields(status_data, _TIRE_FIELDS)),
            connectivity=ConnectivityStatus(**_extract_fields(status_data, _CONNECTIVITY_FIELDS)),
            ignition=IgnitionStatus(**_extract_fields(status_data, _IGNITION_FIELDS)),
            raw=status_data,
            **timestamps,
        )

    # -- Convenience properties (delegate to sub-objects) --

    @property
    def is_locked(self) -> bool | None:
        """True if the vehicle is locked."""
        return self.doors.is_locked

    @property
    def is_charging(self) -> bool | None:
        """True if the vehicle is currently charger plugin connected, is parked and the charging is started."""
        return (
            self.battery.charge_state in (ChargeState.AC_CONNECTED, ChargeState.DC_CONNECTED)
            and self.driving.is_parked
            and self.battery.is_charging
        )

    @property
    def is_regening(self) -> bool | None:
        """True if the vehicle is currently regeneratively braking (i.e., driving with battery charging)."""
        return (
            self.battery.is_charging
            and not self.driving.is_parked
            and self.battery.charge_state == ChargeState.NOT_CONNECTED
        )

    @property
    def is_parked(self) -> bool | None:
        """True if the vehicle is stationary."""
        return self.driving.is_parked

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
}

_LOCATION_FIELDS: dict[str, str] = {
    "latitude": "latitude",
    "longitude": "longitude",
}

_CLIMATE_FIELDS: dict[str, str] = {
    "acSwitch": "ac_switch",
    "acSetting": "ac_setting",
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
    "bcmKeyPositionOn3": "bcm_key_position_on3",
}

_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def _extract_fields(data: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Extract fields from *data* using an API-key → field-name mapping."""
    return {field_name: data[api_key] for api_key, field_name in mapping.items() if api_key in data}


@dataclass(frozen=True, slots=True)
class RemoteActionSpec:
    """Verified remote-control action payload."""

    cmd_id: str
    cmd_content: str


@dataclass(slots=True)
class RemoteActionResult:
    """Result of a remote-control action."""

    action: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


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
