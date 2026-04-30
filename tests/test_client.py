"""Tests for leapmotor_api.client module."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from leapmotor_api.client import (
    LeapmotorApiClient,
    _charging_power_kw,
    _derive_vehicle_state,
    _is_charging,
    _safe_float,
    _safe_int,
    _to_bar,
    normalize_vehicle,
)
from leapmotor_api.exceptions import (
    LeapmotorApiError,
    LeapmotorAuthError,
    LeapmotorMissingAppCertError,
)
from leapmotor_api.models import Vehicle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cert_files() -> tuple[str, str]:
    """Create dummy cert/key files for testing."""
    cert_fd, cert_path = tempfile.mkstemp(suffix=".pem")
    key_fd, key_path = tempfile.mkstemp(suffix=".pem")
    os.write(cert_fd, b"-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
    os.close(cert_fd)
    os.write(key_fd, b"-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n")
    os.close(key_fd)
    return cert_path, key_path


def _make_client(**kwargs: Any) -> LeapmotorApiClient:
    cert_path, key_path = _make_cert_files()
    defaults = {
        "username": "test@test.com",
        "password": "testpass",
        "app_cert_path": cert_path,
        "app_key_path": key_path,
    }
    defaults.update(kwargs)
    return LeapmotorApiClient(**defaults)


# ---------------------------------------------------------------------------
# Client construction
# ---------------------------------------------------------------------------

class TestClientInit:

    def test_default_device_id_is_uuid(self) -> None:
        client = _make_client()
        assert len(client.device_id) == 32  # UUID4 hex without dashes
        client.close()

    def test_custom_device_id(self) -> None:
        client = _make_client(device_id="custom123")
        assert client.device_id == "custom123"
        client.close()

    def test_operation_password_stripped(self) -> None:
        client = _make_client(operation_password="  1234  ")
        assert client.operation_password == "1234"
        client.close()

    def test_missing_cert_raises(self) -> None:
        client = _make_client(app_cert_path="/nonexistent/cert.pem")
        with pytest.raises(LeapmotorMissingAppCertError):
            client.fetch_data()
        client.close()


class TestClientClose:

    def test_close_cleans_temp_files(self) -> None:
        client = _make_client()
        # Simulate loaded account cert
        fd, path = tempfile.mkstemp(suffix="-leapmotor-cert.pem")
        os.close(fd)
        client.account_cert_file = path
        fd2, path2 = tempfile.mkstemp(suffix="-leapmotor-key.pem")
        os.close(fd2)
        client.account_key_file = path2

        client.close()
        assert not Path(path).exists()
        assert not Path(path2).exists()


# ---------------------------------------------------------------------------
# Normalize vehicle
# ---------------------------------------------------------------------------

class TestNormalizeVehicle:

    def _vehicle(self) -> Vehicle:
        return Vehicle(
            vin="WLMTEST123",
            car_id="42",
            car_type="C10",
            nickname="MyCar",
            is_shared=False,
            year=2024,
        )

    def test_basic_structure(self) -> None:
        status_json: dict[str, Any] = {
            "data": {
                "signal": {"1204": 85, "3260": 300, "47": 0},
                "config": {},
            }
        }
        result = normalize_vehicle(self._vehicle(), status_json, "user1")
        assert result["vehicle"]["vin"] == "WLMTEST123"
        assert result["status"]["battery_percent"] == 85
        assert result["status"]["remaining_range_km"] == 300
        assert result["status"]["is_locked"] is True

    def test_unlocked(self) -> None:
        status_json: dict[str, Any] = {"data": {"signal": {"47": 1}, "config": {}}}
        result = normalize_vehicle(self._vehicle(), status_json, "user1")
        assert result["status"]["is_locked"] is False

    def test_lock_status_none(self) -> None:
        status_json: dict[str, Any] = {"data": {"signal": {}, "config": {}}}
        result = normalize_vehicle(self._vehicle(), status_json, "user1")
        assert result["status"]["is_locked"] is None

    def test_with_mileage(self) -> None:
        status_json: dict[str, Any] = {"data": {"signal": {}, "config": {}}}
        mileage_json = {"data": {"totalmileage": 15000, "deliveryDays": 365}}
        result = normalize_vehicle(
            self._vehicle(), status_json, "user1", mileage_json=mileage_json,
        )
        assert result["history"]["total_mileage_km"] == 15000
        assert result["history"]["delivery_days"] == 365

    def test_with_picture(self) -> None:
        status_json: dict[str, Any] = {"data": {"signal": {}, "config": {}}}
        picture_json = {"data": {"shareBindUrl": "https://example.com/pic.jpg", "key": "k"}}
        result = normalize_vehicle(
            self._vehicle(), status_json, "user1", picture_json=picture_json,
        )
        assert result["media"]["car_picture_status"] == "available"
        assert result["media"]["car_picture_url"] == "https://example.com/pic.jpg"

    def test_empty_data(self) -> None:
        result = normalize_vehicle(self._vehicle(), {}, "user1")
        assert result["status"]["battery_percent"] is None
        assert result["location"]["latitude"] is None


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestSafeInt:
    def test_valid(self) -> None:
        assert _safe_int(42) == 42
        assert _safe_int("123") == 123

    def test_none(self) -> None:
        assert _safe_int(None) is None

    def test_invalid(self) -> None:
        assert _safe_int("abc") is None


class TestSafeFloat:
    def test_valid(self) -> None:
        assert _safe_float(3.14) == 3.14
        assert _safe_float("2.5") == 2.5

    def test_none(self) -> None:
        assert _safe_float(None) is None


class TestToBar:
    def test_converts(self) -> None:
        assert _to_bar(250) == 2.5

    def test_none(self) -> None:
        assert _to_bar(None) is None


class TestVehicleState:
    def test_parked_primary(self) -> None:
        assert _derive_vehicle_state({"1298": 1}) == "parked"

    def test_driving_primary(self) -> None:
        assert _derive_vehicle_state({"1298": 0}) == "driving"

    def test_parked_fallback_drive_status(self) -> None:
        assert _derive_vehicle_state({"1941": 2}) == "parked"
        assert _derive_vehicle_state({"1941": 4}) == "parked"

    def test_driving_fallback_drive_status(self) -> None:
        assert _derive_vehicle_state({"1941": 3}) == "driving"
        assert _derive_vehicle_state({"1941": 5}) == "driving"

    def test_parked_fallback_vehicle_state(self) -> None:
        assert _derive_vehicle_state({"1944": 0}) == "parked"
        assert _derive_vehicle_state({"1944": 1}) == "parked"
        assert _derive_vehicle_state({"1944": 3}) == "parked"

    def test_driving_fallback_vehicle_state(self) -> None:
        assert _derive_vehicle_state({"1944": 2}) == "driving"
        assert _derive_vehicle_state({"1944": 4}) == "driving"
        assert _derive_vehicle_state({"1944": 5}) == "driving"

    def test_none(self) -> None:
        assert _derive_vehicle_state({}) is None


class TestIsCharging:
    def test_charging_by_current(self) -> None:
        assert _is_charging({"1178": -5.0, "1200": 120}) is True
        assert _is_charging({"1178": 10.0, "1200": 60}) is True

    def test_not_charging_low_current(self) -> None:
        assert _is_charging({"1178": 0.5, "1200": 120}) is False

    def test_charging_by_power(self) -> None:
        assert _is_charging({"1178": 5.0, "1177": 400.0, "1200": 90}) is True

    def test_charging_legacy_fallback(self) -> None:
        assert _is_charging({"1939": 1, "1941": 2, "1200": 60}) is True
        assert _is_charging({"1939": 2, "1944": 0, "1200": 30}) is True

    def test_not_charging_legacy_without_remaining_time(self) -> None:
        assert _is_charging({"1939": 1, "1941": 2}) is False

    def test_not_charging(self) -> None:
        assert _is_charging({"1939": 0}) is False
        assert _is_charging({}) is False


# ---------------------------------------------------------------------------
# Charging power helper
# ---------------------------------------------------------------------------


class TestChargingPowerKw:
    def test_valid_power(self) -> None:
        # 400V * 10A = 4000W = 4.0 kW
        assert _charging_power_kw({"1178": 10.0, "1177": 400.0}) == 4.0

    def test_negative_current(self) -> None:
        # abs(-10) * 400 = 4000W = 4.0 kW
        assert _charging_power_kw({"1178": -10.0, "1177": 400.0}) == 4.0

    def test_low_current_returns_none(self) -> None:
        assert _charging_power_kw({"1178": 2.0, "1177": 400.0}) is None

    def test_missing_current_returns_none(self) -> None:
        assert _charging_power_kw({"1177": 400.0}) is None

    def test_missing_voltage_returns_none(self) -> None:
        assert _charging_power_kw({"1178": 10.0}) is None

    def test_empty_signal_returns_none(self) -> None:
        assert _charging_power_kw({}) is None


# ---------------------------------------------------------------------------
# Normalize vehicle — additional edge cases
# ---------------------------------------------------------------------------


class TestNormalizeVehicleExtended:

    def _vehicle(self) -> Vehicle:
        return Vehicle(
            vin="WLMTEST123",
            car_id="42",
            car_type="C10",
            nickname="MyCar",
            is_shared=False,
            year=2024,
        )

    def test_charging_info(self) -> None:
        status_json: dict[str, Any] = {
            "data": {
                "signal": {"1178": 10.0, "1177": 400.0, "1200": 60, "1204": 50},
                "config": {
                    "3": {
                        "percent": 80,
                        "isEnable": 1,
                        "beginTime": "22:00",
                        "endTime": "06:00",
                        "cycles": "1,2,3,4,5,6,7",
                        "circulation": 1,
                        "updateTime": "2024-01-01 00:00:00",
                    }
                },
            }
        }
        result = normalize_vehicle(self._vehicle(), status_json, "user1")
        assert result["charging"]["is_charging"] is True
        assert result["charging"]["charge_limit_percent"] == 80
        assert result["charging"]["remaining_charge_minutes"] == 60
        assert result["charging"]["charging_power_kw"] == 4.0
        assert result["charging"]["charging_current_a"] == 10.0
        assert result["charging"]["charging_voltage_v"] == 400.0
        assert result["charging"]["charging_planned_enabled"] == 1
        assert result["charging"]["charging_planned_start"] == "22:00"
        assert result["charging"]["charging_planned_end"] == "06:00"

    def test_diagnostics_tire_pressure(self) -> None:
        status_json: dict[str, Any] = {
            "data": {
                "signal": {
                    "2667": 250,
                    "2653": 255,
                    "2646": 260,
                    "2660": 245,
                },
                "config": {},
            }
        }
        result = normalize_vehicle(self._vehicle(), status_json, "user1")
        assert result["diagnostics"]["tire_pressure_front_left_bar"] == 2.5
        assert result["diagnostics"]["tire_pressure_front_right_bar"] == 2.55
        assert result["diagnostics"]["tire_pressure_rear_left_bar"] == 2.6
        assert result["diagnostics"]["tire_pressure_rear_right_bar"] == 2.45

    def test_location_fallback_coordinates(self) -> None:
        """Should fall back to signal 2190/2191 if 3725/3724 not present."""
        status_json: dict[str, Any] = {
            "data": {
                "signal": {"2190": 45.123, "2191": 7.456},
                "config": {},
            }
        }
        result = normalize_vehicle(self._vehicle(), status_json, "user1")
        assert result["location"]["latitude"] == 45.123
        assert result["location"]["longitude"] == 7.456

    def test_location_primary_coordinates(self) -> None:
        """Primary coordinates (3725/3724) take precedence."""
        status_json: dict[str, Any] = {
            "data": {
                "signal": {"3725": 46.0, "3724": 8.0, "2190": 45.0, "2191": 7.0},
                "config": {},
            }
        }
        result = normalize_vehicle(self._vehicle(), status_json, "user1")
        assert result["location"]["latitude"] == 46.0
        assert result["location"]["longitude"] == 8.0

    def test_vehicle_abilities_empty(self) -> None:
        v = Vehicle(
            vin="VIN1", car_id="1", car_type="C10",
            nickname="N", is_shared=False, abilities=None,
        )
        result = normalize_vehicle(v, {}, "user1")
        assert result["vehicle"]["abilities"] == []

    def test_vehicle_abilities_populated(self) -> None:
        v = Vehicle(
            vin="VIN1", car_id="1", car_type="C10",
            nickname="N", is_shared=False, abilities=["remote", "charge"],
        )
        result = normalize_vehicle(v, {}, "user1")
        assert result["vehicle"]["abilities"] == ["remote", "charge"]

    def test_raw_updated_at_present(self) -> None:
        result = normalize_vehicle(self._vehicle(), {}, "user1")
        assert "raw_updated_at" in result
        assert isinstance(result["raw_updated_at"], float)


# ---------------------------------------------------------------------------
# Client — _parse_api_body
# ---------------------------------------------------------------------------


class TestParseApiBody:
    def test_success(self) -> None:
        client = _make_client()
        body = json.dumps({"code": 0, "message": "success", "data": {"id": 1}})
        result = client._parse_api_body(200, body, "test")
        assert result["code"] == 0
        assert result["data"]["id"] == 1
        client.close()

    def test_non_json_raises(self) -> None:
        client = _make_client()
        with pytest.raises(LeapmotorApiError, match="non-JSON"):
            client._parse_api_body(200, "not json", "test")
        client.close()

    def test_http_error_raises(self) -> None:
        client = _make_client()
        body = json.dumps({"code": 500, "message": "internal error"})
        with pytest.raises(LeapmotorApiError, match="internal error"):
            client._parse_api_body(500, body, "test")
        client.close()

    def test_api_code_nonzero_raises(self) -> None:
        client = _make_client()
        body = json.dumps({"code": 1001, "message": "token expired"})
        with pytest.raises(LeapmotorApiError, match="token expired"):
            client._parse_api_body(200, body, "test")
        client.close()

    def test_login_failure_raises_auth_error(self) -> None:
        client = _make_client()
        body = json.dumps({"code": 401, "message": "invalid credentials"})
        with pytest.raises(LeapmotorAuthError, match="login failed"):
            client._parse_api_body(200, body, "login")
        client.close()

    def test_remote_verify_failure_raises_auth_error(self) -> None:
        client = _make_client()
        body = json.dumps({"code": 403, "message": "pin wrong"})
        with pytest.raises(LeapmotorAuthError, match="remote verify failed"):
            client._parse_api_body(200, body, "remote verify")
        client.close()

    def test_records_api_result(self) -> None:
        client = _make_client()
        body = json.dumps({"code": 0, "message": "ok"})
        client._parse_api_body(200, body, "test_label")
        assert "test_label" in client.last_api_results
        assert client.last_api_results["test_label"]["code"] == 0
        assert client.last_api_results["test_label"]["http_status"] == 200
        client.close()


# ---------------------------------------------------------------------------
# Client — Remote control errors
# ---------------------------------------------------------------------------


class TestRemoteControlErrors:
    def test_no_pin_raises(self) -> None:
        client = _make_client()
        client.token = "fake_token"
        client.operation_password = None
        with pytest.raises(LeapmotorAuthError, match="No vehicle PIN"):
            client._remote_control(vin="VIN123", action="lock")
        client.close()

    def test_unknown_action_raises(self) -> None:
        client = _make_client(operation_password="1234")
        client.token = "fake_token"
        with pytest.raises(LeapmotorApiError, match="not configured"):
            client._remote_control(vin="VIN123", action="nonexistent_action")
        client.close()


# ---------------------------------------------------------------------------
# Client — Properties
# ---------------------------------------------------------------------------


class TestClientProperties:
    def test_account_cert_raises_when_not_loaded(self) -> None:
        client = _make_client()
        with pytest.raises(LeapmotorAuthError, match="No account certificate"):
            _ = client.account_cert
        client.close()

    def test_sign_key_raises_when_not_loaded(self) -> None:
        client = _make_client()
        with pytest.raises(LeapmotorAuthError, match="No account sign material"):
            _ = client.sign_key
        client.close()

    def test_account_cert_returns_tuple(self) -> None:
        client = _make_client()
        client.account_cert_file = "/tmp/cert.pem"
        client.account_key_file = "/tmp/key.pem"
        assert client.account_cert == ("/tmp/cert.pem", "/tmp/key.pem")
        client.close()


# ---------------------------------------------------------------------------
# Client — _clear_auth
# ---------------------------------------------------------------------------


class TestClearAuth:
    def test_clears_all_state(self) -> None:
        client = _make_client()
        client.token = "tok"
        client.user_id = "uid"
        client.sign_ikm = "ikm"
        client.sign_salt = "salt"
        client.sign_info = "info"
        client.account_p12_password_used = "pass"
        client.account_p12_password_source = "derived"
        client.remote_cert_synced = True

        client._clear_auth()

        assert client.token is None
        assert client.user_id is None
        assert client.sign_ikm is None
        assert client.sign_salt is None
        assert client.sign_info is None
        assert client.account_p12_password_used is None
        assert client.account_p12_password_source is None
        assert client.remote_cert_synced is False
        client.close()


# ---------------------------------------------------------------------------
# Client — _auth_headers
# ---------------------------------------------------------------------------


class TestAuthHeaders:
    def test_raises_when_not_authenticated(self) -> None:
        client = _make_client()
        with pytest.raises(LeapmotorAuthError, match="Not authenticated"):
            client._auth_headers(content_type="application/json")
        client.close()

    def test_returns_headers_when_authenticated(self) -> None:
        client = _make_client()
        client.user_id = "123"
        client.token = "abc"
        headers = client._auth_headers(content_type="application/json")
        assert headers["Content-Type"] == "application/json"
        assert headers["userId"] == "123"
        assert headers["token"] == "abc"
        client.close()


# ---------------------------------------------------------------------------
# Client — _build_login_form_body
# ---------------------------------------------------------------------------


class TestBuildLoginFormBody:
    def test_encodes_credentials(self) -> None:
        client = _make_client(username="user@example.com", password="p@ss!word")
        body = client._build_login_form_body()
        assert "email=user%40example.com" in body
        assert "password=p%40ss%21word" in body
        assert "isRecoverAcct=0" in body
        assert "loginMethod=1" in body
        client.close()


# ---------------------------------------------------------------------------
# Client — _find_vehicle_by_vin (via mock)
# ---------------------------------------------------------------------------


class TestFindVehicleByVin:
    def test_found(self) -> None:
        client = _make_client()
        client.token = "tok"
        client.user_id = "uid"
        client.sign_ikm = "ikm"
        client.sign_salt = "salt"
        client.sign_info = "info"
        vehicle = Vehicle(vin="VIN1", car_id="1", car_type="C10", nickname="N", is_shared=False)
        with patch.object(client, "get_vehicle_list", return_value=[vehicle]):
            result = client._find_vehicle_by_vin("VIN1")
            assert result.vin == "VIN1"
        client.close()

    def test_not_found_raises(self) -> None:
        client = _make_client()
        client.token = "tok"
        client.user_id = "uid"
        client.sign_ikm = "ikm"
        client.sign_salt = "salt"
        client.sign_info = "info"
        with patch.object(client, "get_vehicle_list", return_value=[]):
            with pytest.raises(LeapmotorApiError, match="Vehicle not found"):
                client._find_vehicle_by_vin("NONEXISTENT")
        client.close()
