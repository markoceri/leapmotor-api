"""Leapmotor API data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Vehicle:
    """Vehicle metadata from the vehicle list."""

    vin: str
    car_id: str | None
    car_type: str
    nickname: str | None
    is_shared: bool
    year: int | None = None
    rights: str | None = None
    abilities: list[str] | None = None
    module_rights: str | None = None


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


# ---------------------------------------------------------------------------
# Sub-objects for VehicleStatus
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class BatteryStatus:
    """Battery and charging status."""

    soc: int | None = None
    charge_state: int | None = None
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
        return round(abs(self.battery_voltage * self.battery_current) / 1000, 2)

    @property
    def charging_power_kw(self) -> float | None:
        """Charging power in kW (None when current below meaningful threshold)."""
        if self.battery_current is None or self.battery_voltage is None:
            return None
        if abs(self.battery_current) < 3.0:
            return None
        return round(abs(self.battery_current * self.battery_voltage) / 1000.0, 3)

    @property
    def is_charging(self) -> bool | None:
        """True if the vehicle is currently charging (3-level detection)."""
        # Level 1: current + remaining time both available
        if self.battery_current is not None and self.charge_remain_time is not None:
            return abs(self.battery_current) >= 1.0
        # Level 2: power (with min-current threshold) available
        power = self.charging_power_kw
        if power is not None:
            return power >= 1.0 and self.charge_remain_time is not None
        # Level 3: legacy fallback using charge_state
        if self.charge_state is None:
            return None
        return self.charge_state in (1, 2, 3) and self.charge_remain_time is not None


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


# ---------------------------------------------------------------------------
# API key → (sub-object attr, field name) mapping
# ---------------------------------------------------------------------------

_BATTERY_FIELDS: dict[str, str] = {
    "soc": "soc",
    "chargeState": "charge_state",
    "chargeRemainTime": "charge_remain_time",
    "chargesocSetting": "charge_soc_setting",
    "chargeTimeSetting": "charge_time_setting",
    "dcInputFastCharge": "dc_input_fast_charge",
    "dumpEnergy": "dump_energy",
    "batteryCurrent": "battery_current",
    "batteryVoltage": "battery_voltage",
    "expectedMileage": "expected_mileage",
}

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

    # -- Raw dict for forward-compatibility --
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, status_data: dict[str, Any]) -> VehicleStatus:
        """Build a ``VehicleStatus`` from the raw API status dict."""
        # Parse timestamps
        timestamps: dict[str, Any] = {}
        for api_key, field_name in (("collectTime", "collect_time"), ("createTime", "create_time")):
            raw_ts = status_data.get(api_key)
            if isinstance(raw_ts, str):
                try:
                    timestamps[field_name] = datetime.strptime(raw_ts, _DATETIME_FMT)
                except ValueError:
                    pass

        return cls(
            battery=BatteryStatus(**_extract_fields(status_data, _BATTERY_FIELDS)),
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
        """True if the vehicle is currently charging."""
        return self.battery.is_charging

    @property
    def is_parked(self) -> bool:
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
