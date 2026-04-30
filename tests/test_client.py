"""Tests for leapmotor_api.client module."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from leapmotor_api.client import (
    LeapmotorApiClient,
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
