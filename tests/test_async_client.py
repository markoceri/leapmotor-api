"""Tests for leapmotor_api.async_client module."""

from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Any
from unittest.mock import patch

from leapmotor_api.async_client import AsyncLeapmotorApiClient
from leapmotor_api.client import LeapmotorApiClient
from leapmotor_api.models import Vehicle, VehicleStatus


def _make_cert_files() -> tuple[str, str]:
    """Create dummy cert/key files for testing."""
    cert_fd, cert_path = tempfile.mkstemp(suffix=".pem")
    key_fd, key_path = tempfile.mkstemp(suffix=".pem")
    os.write(cert_fd, b"-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
    os.close(cert_fd)
    os.write(key_fd, b"-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n")
    os.close(key_fd)
    return cert_path, key_path


def _make_sync_client(**kwargs: Any) -> LeapmotorApiClient:
    cert_path, key_path = _make_cert_files()
    defaults = {
        "username": "test@test.com",
        "password": "testpass",
        "app_cert_path": cert_path,
        "app_key_path": key_path,
    }
    defaults.update(kwargs)
    return LeapmotorApiClient(**defaults)


def _make_vehicle() -> Vehicle:
    return Vehicle(
        vin="WLMTEST123",
        car_id="42",
        car_type="C10",
        nickname="TestCar",
        is_shared=False,
        year=2024,
    )


class TestAsyncClientInit:
    def test_wraps_sync_client(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        assert async_client.client is sync
        sync.close()


class TestAsyncClientClose:
    def test_close_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        with patch.object(sync, "close") as mock_close:
            asyncio.run(async_client.close())
            mock_close.assert_called_once()


class TestAsyncClientLogin:
    def test_login_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        with patch.object(sync, "login") as mock_login:
            asyncio.run(async_client.login())
            mock_login.assert_called_once()
        sync.close()


class TestAsyncClientFetchData:
    def test_fetch_data_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        expected = {"user_id": "1", "vehicles": {}}
        with patch.object(sync, "fetch_data", return_value=expected) as mock:
            result = asyncio.run(async_client.fetch_data())
            mock.assert_called_once()
            assert result == expected
        sync.close()


class TestAsyncClientVehicleList:
    def test_get_vehicle_list_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        vehicles = [_make_vehicle()]
        with patch.object(sync, "get_vehicle_list", return_value=vehicles) as mock:
            result = asyncio.run(async_client.get_vehicle_list())
            mock.assert_called_once()
            assert result == vehicles
        sync.close()


class TestAsyncClientVehicleStatus:
    def test_get_vehicle_status_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        vehicle = _make_vehicle()
        status = VehicleStatus()
        with patch.object(sync, "get_vehicle_status", return_value=status) as mock:
            result = asyncio.run(async_client.get_vehicle_status(vehicle))
            mock.assert_called_once_with(vehicle)
            assert result is status
        sync.close()

    def test_get_vehicle_raw_status_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        vehicle = _make_vehicle()
        raw = {"data": {"soc": 80}}
        with patch.object(sync, "get_vehicle_raw_status", return_value=raw) as mock:
            result = asyncio.run(async_client.get_vehicle_raw_status(vehicle))
            mock.assert_called_once_with(vehicle)
            assert result == raw
        sync.close()


class TestAsyncClientRemoteControl:
    def test_lock_vehicle_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        expected = {"code": 0, "data": {"remoteCtlId": "abc"}}
        with patch.object(sync, "lock_vehicle", return_value=expected) as mock:
            result = asyncio.run(async_client.lock_vehicle("VIN123"))
            mock.assert_called_once_with("VIN123")
            assert result == expected
        sync.close()

    def test_unlock_vehicle_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        expected = {"code": 0}
        with patch.object(sync, "unlock_vehicle", return_value=expected) as mock:
            result = asyncio.run(async_client.unlock_vehicle("VIN123"))
            mock.assert_called_once_with("VIN123")
            assert result == expected
        sync.close()

    def test_open_trunk_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        expected = {"code": 0}
        with patch.object(sync, "open_trunk", return_value=expected) as mock:
            result = asyncio.run(async_client.open_trunk("VIN123"))
            mock.assert_called_once_with("VIN123")
            assert result == expected
        sync.close()

    def test_find_vehicle_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        expected = {"code": 0}
        with patch.object(sync, "find_vehicle", return_value=expected) as mock:
            result = asyncio.run(async_client.find_vehicle("VIN123"))
            mock.assert_called_once_with("VIN123")
            assert result == expected
        sync.close()

    def test_ac_switch_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        expected = {"code": 0}
        with patch.object(sync, "ac_switch", return_value=expected) as mock:
            result = asyncio.run(async_client.ac_switch("VIN123"))
            mock.assert_called_once_with("VIN123")
            assert result == expected
        sync.close()

    def test_quick_cool_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        expected = {"code": 0}
        with patch.object(sync, "quick_cool", return_value=expected) as mock:
            result = asyncio.run(async_client.quick_cool("VIN123"))
            mock.assert_called_once_with("VIN123")
            assert result == expected
        sync.close()

    def test_quick_heat_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        expected = {"code": 0}
        with patch.object(sync, "quick_heat", return_value=expected) as mock:
            result = asyncio.run(async_client.quick_heat("VIN123"))
            mock.assert_called_once_with("VIN123")
            assert result == expected
        sync.close()

    def test_windshield_defrost_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        expected = {"code": 0}
        with patch.object(sync, "windshield_defrost", return_value=expected) as mock:
            result = asyncio.run(async_client.windshield_defrost("VIN123"))
            mock.assert_called_once_with("VIN123")
            assert result == expected
        sync.close()


class TestAsyncClientMileage:
    def test_get_mileage_energy_detail_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        vehicle = _make_vehicle()
        expected = {"data": {"totalmileage": 5000}}
        with patch.object(sync, "get_mileage_energy_detail", return_value=expected) as mock:
            result = asyncio.run(async_client.get_mileage_energy_detail(vehicle))
            mock.assert_called_once_with(vehicle)
            assert result == expected
        sync.close()


class TestAsyncClientCarPicture:
    def test_get_car_picture_delegates(self) -> None:
        sync = _make_sync_client()
        async_client = AsyncLeapmotorApiClient(sync)
        vehicle = _make_vehicle()
        expected = {"data": {"key": "abc", "shareBindUrl": "https://example.com/pic.jpg"}}
        with patch.object(sync, "get_car_picture", return_value=expected) as mock:
            result = asyncio.run(async_client.get_car_picture(vehicle))
            mock.assert_called_once_with(vehicle)
            assert result == expected
        sync.close()
