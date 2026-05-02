"""Async wrapper for the Leapmotor API client.

Wraps the synchronous ``LeapmotorApiClient`` using ``asyncio.to_thread()``
to provide a non-blocking interface for async frameworks (Home Assistant,
FastAPI, etc.).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .client import LeapmotorApiClient
    from .models import MessageList, Vehicle, VehicleStatus


class AsyncLeapmotorApiClient:
    """Async wrapper around :class:`LeapmotorApiClient`.

    All methods delegate to the sync client via ``asyncio.to_thread()``.
    """

    def __init__(self, client: LeapmotorApiClient) -> None:
        self._client = client

    @property
    def client(self) -> LeapmotorApiClient:
        """Access the underlying synchronous client."""
        return self._client

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)

    async def login(self) -> None:
        await asyncio.to_thread(self._client.login)

    async def token_refresh(self) -> None:
        await asyncio.to_thread(self._client.token_refresh)

    async def fetch_data(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.fetch_data)

    async def get_vehicle_list(self) -> list[Vehicle]:
        return await asyncio.to_thread(self._client.get_vehicle_list)

    async def get_vehicle_status(self, vehicle: Vehicle) -> VehicleStatus:
        return await asyncio.to_thread(self._client.get_vehicle_status, vehicle)

    async def get_vehicle_raw_status(self, vehicle: Vehicle) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.get_vehicle_raw_status, vehicle)

    async def get_mileage_energy_detail(self, vehicle: Vehicle) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.get_mileage_energy_detail, vehicle)

    async def get_car_picture(self, vehicle: Vehicle) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.get_car_picture, vehicle)

    async def lock_vehicle(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.lock_vehicle, vin)

    async def unlock_vehicle(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.unlock_vehicle, vin)

    async def open_trunk(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.open_trunk, vin)

    async def close_trunk(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.close_trunk, vin)

    async def find_vehicle(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.find_vehicle, vin)

    async def control_sunshade(self, vin: str, *, value: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, str] = {}
        if value is not None:
            kwargs["value"] = value
        return await asyncio.to_thread(self._client.control_sunshade, vin, **kwargs)

    async def open_sunshade(self, vin: str, *, value: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, str] = {}
        if value is not None:
            kwargs["value"] = value
        return await asyncio.to_thread(self._client.open_sunshade, vin, **kwargs)

    async def close_sunshade(self, vin: str, *, value: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, str] = {}
        if value is not None:
            kwargs["value"] = value
        return await asyncio.to_thread(self._client.close_sunshade, vin, **kwargs)

    async def battery_preheat(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.battery_preheat, vin)

    async def windows(self, vin: str, *, value: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, str] = {}
        if value is not None:
            kwargs["value"] = value
        return await asyncio.to_thread(self._client.windows, vin, **kwargs)

    async def open_windows(self, vin: str, *, value: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, str] = {}
        if value is not None:
            kwargs["value"] = value
        return await asyncio.to_thread(self._client.open_windows, vin, **kwargs)

    async def close_windows(self, vin: str, *, value: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, str] = {}
        if value is not None:
            kwargs["value"] = value
        return await asyncio.to_thread(self._client.close_windows, vin, **kwargs)

    async def ac_switch(self, vin: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if params is not None:
            kwargs["params"] = params
        return await asyncio.to_thread(self._client.ac_switch, vin, **kwargs)

    async def quick_cool(self, vin: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if params is not None:
            kwargs["params"] = params
        return await asyncio.to_thread(self._client.quick_cool, vin, **kwargs)

    async def quick_heat(self, vin: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if params is not None:
            kwargs["params"] = params
        return await asyncio.to_thread(self._client.quick_heat, vin, **kwargs)

    async def windshield_defrost(self, vin: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if params is not None:
            kwargs["params"] = params
        return await asyncio.to_thread(self._client.windshield_defrost, vin, **kwargs)

    async def set_charge_limit(self, vin: str, charge_limit_percent: int) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.set_charge_limit, vin, charge_limit_percent)

    async def send_destination(
        self,
        vin: str,
        *,
        address: str,
        address_name: str,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._client.send_destination,
            vin,
            address=address,
            address_name=address_name,
            latitude=latitude,
            longitude=longitude,
        )

    async def download_car_picture_package(self, *, picture_key: str) -> bytes:
        return await asyncio.to_thread(self._client.download_car_picture_package, picture_key=picture_key)

    async def get_message_list(self, *, page_no: int = 1, page_size: int = 10) -> MessageList:
        return await asyncio.to_thread(self._client.get_message_list, page_no=page_no, page_size=page_size)

    async def get_unread_message_count(self) -> int:
        return await asyncio.to_thread(self._client.get_unread_message_count)
