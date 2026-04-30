"""Tests for leapmotor_api.models module."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from leapmotor_api.models import (
    BatteryStatus,
    DoorStatus,
    DrivingStatus,
    RemoteActionResult,
    RemoteActionSpec,
    TirePressure,
    Vehicle,
    VehicleStatus,
)


# ---------------------------------------------------------------------------
# Vehicle
# ---------------------------------------------------------------------------


class TestVehicle:
    def test_basic_creation(self) -> None:
        v = Vehicle(
            vin="WLMTEST123456",
            car_id="42",
            car_type="C10",
            nickname="MyCar",
            is_shared=False,
            year=2024,
        )
        assert v.vin == "WLMTEST123456"
        assert v.car_id == "42"
        assert v.car_type == "C10"
        assert v.nickname == "MyCar"
        assert v.is_shared is False
        assert v.year == 2024

    def test_optional_fields_default_none(self) -> None:
        v = Vehicle(vin="VIN1", car_id=None, car_type="C11", nickname=None, is_shared=True)
        assert v.year is None
        assert v.rights is None
        assert v.abilities is None
        assert v.module_rights is None

    def test_shared_vehicle(self) -> None:
        v = Vehicle(vin="VIN2", car_id="10", car_type="C10", nickname="Shared", is_shared=True)
        assert v.is_shared is True


# ---------------------------------------------------------------------------
# TirePressure
# ---------------------------------------------------------------------------


class TestTirePressure:
    def test_bar_conversion(self) -> None:
        tp = TirePressure(
            front_left_kpa=250,
            front_right_kpa=255,
            rear_left_kpa=260,
            rear_right_kpa=245,
        )
        assert tp.front_left_bar == 2.5
        assert tp.front_right_bar == 2.55
        assert tp.rear_left_bar == 2.6
        assert tp.rear_right_bar == 2.45

    def test_bar_conversion_none(self) -> None:
        tp = TirePressure()
        assert tp.front_left_bar is None
        assert tp.front_right_bar is None
        assert tp.rear_left_bar is None
        assert tp.rear_right_bar is None

    def test_all_bar_dict(self) -> None:
        tp = TirePressure(front_left_kpa=250, rear_right_kpa=260)
        result = tp.all_bar
        assert result["front_left"] == 2.5
        assert result["front_right"] is None
        assert result["rear_left"] is None
        assert result["rear_right"] == 2.6

    def test_all_ok_true(self) -> None:
        tp = TirePressure(
            front_left_state=0, front_right_state=0,
            rear_left_state=0, rear_right_state=0,
        )
        assert tp.all_ok is True

    def test_all_ok_false(self) -> None:
        tp = TirePressure(
            front_left_state=0, front_right_state=1,
            rear_left_state=0, rear_right_state=0,
        )
        assert tp.all_ok is False

    def test_all_ok_unknown(self) -> None:
        tp = TirePressure(front_left_state=0, front_right_state=0)
        assert tp.all_ok is None

    def test_frozen(self) -> None:
        tp = TirePressure(front_left_kpa=250)
        with pytest.raises(AttributeError):
            tp.front_left_kpa = 300  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BatteryStatus
# ---------------------------------------------------------------------------


class TestBatteryStatus:
    def test_dump_energy_kwh(self) -> None:
        bs = BatteryStatus(dump_energy=45000)
        assert bs.dump_energy_kwh == 45.0

    def test_dump_energy_kwh_none(self) -> None:
        bs = BatteryStatus()
        assert bs.dump_energy_kwh is None

    def test_battery_power(self) -> None:
        bs = BatteryStatus(battery_voltage=400.0, battery_current=50.0)
        assert bs.battery_power == 20.0

    def test_battery_power_none_voltage(self) -> None:
        bs = BatteryStatus(battery_current=50.0)
        assert bs.battery_power is None

    def test_battery_power_none_current(self) -> None:
        bs = BatteryStatus(battery_voltage=400.0)
        assert bs.battery_power is None

    def test_charging_power_kw(self) -> None:
        bs = BatteryStatus(battery_voltage=400.0, battery_current=10.0)
        assert bs.charging_power_kw == 4.0

    def test_charging_power_kw_below_threshold(self) -> None:
        bs = BatteryStatus(battery_voltage=400.0, battery_current=2.0)
        assert bs.charging_power_kw is None

    def test_charging_power_kw_none(self) -> None:
        bs = BatteryStatus()
        assert bs.charging_power_kw is None

    def test_is_charging_by_current(self) -> None:
        bs = BatteryStatus(battery_current=10.0, charge_remain_time=60)
        assert bs.is_charging is True

    def test_is_charging_low_current(self) -> None:
        bs = BatteryStatus(battery_current=0.5, charge_remain_time=60)
        assert bs.is_charging is False

    def test_is_charging_legacy_state(self) -> None:
        bs = BatteryStatus(charge_state=1, charge_remain_time=60)
        assert bs.is_charging is True

    def test_is_charging_legacy_not_charging(self) -> None:
        bs = BatteryStatus(charge_state=0, charge_remain_time=60)
        assert bs.is_charging is False

    def test_is_charging_none(self) -> None:
        bs = BatteryStatus()
        assert bs.is_charging is None

    def test_is_charging_no_remain_time(self) -> None:
        bs = BatteryStatus(charge_state=1)
        assert bs.is_charging is False


# ---------------------------------------------------------------------------
# DrivingStatus
# ---------------------------------------------------------------------------


class TestDrivingStatus:
    def test_is_parked_true(self) -> None:
        ds = DrivingStatus(speed=0)
        assert ds.is_parked is True

    def test_is_parked_false(self) -> None:
        ds = DrivingStatus(speed=60)
        assert ds.is_parked is False

    def test_is_parked_none(self) -> None:
        ds = DrivingStatus()
        assert ds.is_parked is None


# ---------------------------------------------------------------------------
# DoorStatus
# ---------------------------------------------------------------------------


class TestDoorStatus:
    def test_is_locked_true(self) -> None:
        ds = DoorStatus(driver_door_lock_status=True)
        assert ds.is_locked is True

    def test_is_locked_false(self) -> None:
        ds = DoorStatus(driver_door_lock_status=False)
        assert ds.is_locked is False

    def test_is_locked_none(self) -> None:
        ds = DoorStatus()
        assert ds.is_locked is None


# ---------------------------------------------------------------------------
# VehicleStatus.from_dict
# ---------------------------------------------------------------------------


class TestVehicleStatusFromDict:
    def test_empty_dict(self) -> None:
        vs = VehicleStatus.from_dict({})
        assert vs.battery.soc is None
        assert vs.driving.speed is None
        assert vs.location.latitude is None
        assert vs.climate.ac_switch is None
        assert vs.doors.driver_door_lock_status is None
        assert vs.collect_time is None

    def test_battery_fields(self) -> None:
        data: dict[str, Any] = {
            "soc": 85,
            "chargeState": 1,
            "chargeRemainTime": 120,
            "chargesocSetting": 80,
            "dumpEnergy": 50000,
            "batteryCurrent": 15.5,
            "batteryVoltage": 400.0,
            "expectedMileage": 300,
        }
        vs = VehicleStatus.from_dict(data)
        assert vs.battery.soc == 85
        assert vs.battery.charge_state == 1
        assert vs.battery.charge_remain_time == 120
        assert vs.battery.charge_soc_setting == 80
        assert vs.battery.dump_energy == 50000
        assert vs.battery.battery_current == 15.5
        assert vs.battery.battery_voltage == 400.0
        assert vs.battery.expected_mileage == 300

    def test_driving_fields(self) -> None:
        data: dict[str, Any] = {"speed": 80, "totalMileage": 15000, "gearStatus": 3}
        vs = VehicleStatus.from_dict(data)
        assert vs.driving.speed == 80
        assert vs.driving.total_mileage == 15000
        assert vs.driving.gear_status == 3

    def test_location_fields(self) -> None:
        data: dict[str, Any] = {"latitude": 45.123, "longitude": 7.456}
        vs = VehicleStatus.from_dict(data)
        assert vs.location.latitude == 45.123
        assert vs.location.longitude == 7.456

    def test_climate_fields(self) -> None:
        data: dict[str, Any] = {
            "acSwitch": True,
            "acSetting": 22.0,
            "outdoorTemp": 28,
            "acAirVolume": 3,
        }
        vs = VehicleStatus.from_dict(data)
        assert vs.climate.ac_switch is True
        assert vs.climate.ac_setting == 22.0
        assert vs.climate.outdoor_temp == 28
        assert vs.climate.ac_air_volume == 3

    def test_door_fields(self) -> None:
        data: dict[str, Any] = {
            "driverDoorLockStatus": True,
            "lbcmDriverDoorStatus": False,
            "bbcmBackDoorStatus": True,
        }
        vs = VehicleStatus.from_dict(data)
        assert vs.doors.driver_door_lock_status is True
        assert vs.doors.lbcm_driver_door_status is False
        assert vs.doors.bbcm_back_door_status is True

    def test_window_fields(self) -> None:
        data: dict[str, Any] = {
            "leftFrontWindowPercent": 50,
            "rightFrontWindowPercent": 0,
            "sunShade": 10,
        }
        vs = VehicleStatus.from_dict(data)
        assert vs.windows.left_front_window_percent == 50
        assert vs.windows.right_front_window_percent == 0
        assert vs.windows.sun_shade == 10

    def test_tire_fields(self) -> None:
        data: dict[str, Any] = {
            "leftFrontTirePressure": 250,
            "rightFrontTirePressure": 255,
            "leftRearTirePressure": 260,
            "rightRearTirePressure": 245,
            "leftFrontTirePressureState": 0,
            "rightFrontTirePressureState": 0,
            "leftRearTirePressureState": 0,
            "rightRearTirePressureState": 0,
        }
        vs = VehicleStatus.from_dict(data)
        assert vs.tires.front_left_kpa == 250
        assert vs.tires.front_right_kpa == 255
        assert vs.tires.all_ok is True
        assert vs.tire_pressure_bar["front_left"] == 2.5

    def test_connectivity_fields(self) -> None:
        data: dict[str, Any] = {
            "bluetoothState": True,
            "bluetoothAddr": "AA:BB:CC:DD:EE:FF",
            "hotspotState": False,
        }
        vs = VehicleStatus.from_dict(data)
        assert vs.connectivity.bluetooth_state is True
        assert vs.connectivity.bluetooth_addr == "AA:BB:CC:DD:EE:FF"
        assert vs.connectivity.hotspot_state is False

    def test_ignition_fields(self) -> None:
        data: dict[str, Any] = {"bcmKeyPositionOn1": True, "bcmKeyPositionOn3": False}
        vs = VehicleStatus.from_dict(data)
        assert vs.ignition.bcm_key_position_on1 is True
        assert vs.ignition.bcm_key_position_on3 is False

    def test_timestamps(self) -> None:
        data: dict[str, Any] = {
            "collectTime": "2024-12-25 10:30:00",
            "createTime": "2024-12-25 10:30:05",
        }
        vs = VehicleStatus.from_dict(data)
        assert vs.collect_time == datetime(2024, 12, 25, 10, 30, 0)
        assert vs.create_time == datetime(2024, 12, 25, 10, 30, 5)

    def test_invalid_timestamp_ignored(self) -> None:
        data: dict[str, Any] = {"collectTime": "not-a-date"}
        vs = VehicleStatus.from_dict(data)
        assert vs.collect_time is None

    def test_raw_preserved(self) -> None:
        data: dict[str, Any] = {"soc": 50, "custom_field": "value"}
        vs = VehicleStatus.from_dict(data)
        assert vs.raw == data

    def test_convenience_is_locked(self) -> None:
        data: dict[str, Any] = {"driverDoorLockStatus": True}
        vs = VehicleStatus.from_dict(data)
        assert vs.is_locked is True

    def test_convenience_is_charging(self) -> None:
        data: dict[str, Any] = {"batteryCurrent": 10.0, "chargeRemainTime": 60}
        vs = VehicleStatus.from_dict(data)
        assert vs.is_charging is True

    def test_convenience_is_parked(self) -> None:
        data: dict[str, Any] = {"speed": 0}
        vs = VehicleStatus.from_dict(data)
        assert vs.is_parked is True

    def test_tire_pressure_property(self) -> None:
        data: dict[str, Any] = {"leftFrontTirePressure": 250}
        vs = VehicleStatus.from_dict(data)
        assert vs.tire_pressure.front_left_kpa == 250


# ---------------------------------------------------------------------------
# RemoteActionSpec & RemoteActionResult
# ---------------------------------------------------------------------------


class TestRemoteActionSpec:
    def test_frozen(self) -> None:
        spec = RemoteActionSpec(cmd_id="110", cmd_content='{"value":"lock"}')
        assert spec.cmd_id == "110"
        assert spec.cmd_content == '{"value":"lock"}'
        with pytest.raises(AttributeError):
            spec.cmd_id = "999"  # type: ignore[misc]


class TestRemoteActionResult:
    def test_success(self) -> None:
        r = RemoteActionResult(action="lock", success=True, data={"remoteCtlId": "abc"})
        assert r.action == "lock"
        assert r.success is True
        assert r.error is None

    def test_failure(self) -> None:
        r = RemoteActionResult(action="unlock", success=False, error="timeout")
        assert r.success is False
        assert r.error == "timeout"
        assert r.data == {}
