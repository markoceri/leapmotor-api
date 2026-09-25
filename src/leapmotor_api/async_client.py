"""Async wrapper for the Leapmotor API client.

Wraps the synchronous ``LeapmotorApiClient`` using ``asyncio.to_thread()``
to provide a non-blocking interface for async frameworks (Home Assistant,
FastAPI, etc.).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import date

    from .client import LeapmotorApiClient
    from .models import (
        ChargeDailyDetailPage,
        ConsumptionLastWeekBreakdown,
        ConsumptionWeeklyRank,
        MessageList,
        ShareInvitation,
        Vehicle,
        VehicleStatus,
    )


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

    async def unlock_charger(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.unlock_charger, vin)

    async def open_trunk(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.open_trunk, vin)

    async def close_trunk(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.close_trunk, vin)

    async def find_vehicle(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.find_vehicle, vin)

    async def hotspot(self, vin: str) -> dict[str, Any]:
        """Trigger hotspot / connectivity command (cmd_id=140)."""
        return await asyncio.to_thread(self._client.hotspot, vin)

    async def autopark(self, vin: str) -> dict[str, Any]:
        """Trigger auto park / summon command (cmd_id=150)."""
        return await asyncio.to_thread(self._client.autopark, vin)

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

    async def battery_preheat_off(self, vin: str) -> dict[str, Any]:
        """Turn off battery preheating."""
        return await asyncio.to_thread(self._client.battery_preheat_off, vin)

    async def sentry_mode_on(self, vin: str) -> dict[str, Any]:
        """Enable sentry mode (sentinel / dashcam)."""
        return await asyncio.to_thread(self._client.sentry_mode_on, vin)

    async def sentry_mode_off(self, vin: str) -> dict[str, Any]:
        """Disable sentry mode (sentinel / dashcam)."""
        return await asyncio.to_thread(self._client.sentry_mode_off, vin)

    async def start_charging(self, vin: str) -> dict[str, Any]:
        """Start charging (cmd_id=193)."""
        return await asyncio.to_thread(self._client.start_charging, vin)

    async def stop_charging(self, vin: str) -> dict[str, Any]:
        """Stop charging (cmd_id=193)."""
        return await asyncio.to_thread(self._client.stop_charging, vin)

    async def steering_wheel_heat_on(self, vin: str) -> dict[str, Any]:
        """Enable steering wheel heating (cmd_id=320)."""
        return await asyncio.to_thread(self._client.steering_wheel_heat_on, vin)

    async def steering_wheel_heat_off(self, vin: str) -> dict[str, Any]:
        """Disable steering wheel heating (cmd_id=320)."""
        return await asyncio.to_thread(self._client.steering_wheel_heat_off, vin)

    async def fuel_heating_on(self, vin: str) -> dict[str, Any]:
        """Enable fuel heating (cmd_id=380)."""
        return await asyncio.to_thread(self._client.fuel_heating_on, vin)

    async def fuel_heating_off(self, vin: str) -> dict[str, Any]:
        """Disable fuel heating (cmd_id=380)."""
        return await asyncio.to_thread(self._client.fuel_heating_off, vin)

    async def rearview_mirror_heat_on(self, vin: str) -> dict[str, Any]:
        """Enable rearview mirror heating (cmd_id=440)."""
        return await asyncio.to_thread(self._client.rearview_mirror_heat_on, vin)

    async def rearview_mirror_heat_off(self, vin: str) -> dict[str, Any]:
        """Disable rearview mirror heating (cmd_id=440)."""
        return await asyncio.to_thread(self._client.rearview_mirror_heat_off, vin)

    async def set_speed_limit(self, vin: str, *, value: str) -> dict[str, Any]:
        """Set speed limit in km/h (cmd_id=510)."""
        return await asyncio.to_thread(self._client.set_speed_limit, vin, value=value)

    async def seat_heat(self, vin: str, *, position: int, level: int) -> dict[str, Any]:
        """Set seat heating (cmd_id=301). Position: 1-6, level: 0-3."""
        return await asyncio.to_thread(self._client.seat_heat, vin, position=position, level=level)

    async def seat_ventilation(self, vin: str, *, position: int, level: int) -> dict[str, Any]:
        """Set seat ventilation (cmd_id=370). Position: 1-6, level: 0-3."""
        return await asyncio.to_thread(self._client.seat_ventilation, vin, position=position, level=level)

    async def open_sunroof(self, vin: str) -> dict[str, Any]:
        """Open sunroof (cmd_id=300)."""
        return await asyncio.to_thread(self._client.open_sunroof, vin)

    async def close_sunroof(self, vin: str) -> dict[str, Any]:
        """Close sunroof (cmd_id=300)."""
        return await asyncio.to_thread(self._client.close_sunroof, vin)

    async def healthy_charging_on(self, vin: str) -> dict[str, Any]:
        """Enable healthy charging mode (cmd_id=480)."""
        return await asyncio.to_thread(self._client.healthy_charging_on, vin)

    async def healthy_charging_off(self, vin: str) -> dict[str, Any]:
        """Disable healthy charging mode (cmd_id=480)."""
        return await asyncio.to_thread(self._client.healthy_charging_off, vin)

    async def on3_on(self, vin: str) -> dict[str, Any]:
        """Enable ON3 mode (cmd_id=410)."""
        return await asyncio.to_thread(self._client.on3_on, vin)

    async def on3_off(self, vin: str) -> dict[str, Any]:
        """Disable ON3 mode (cmd_id=410)."""
        return await asyncio.to_thread(self._client.on3_off, vin)

    async def ble_key_restart(self, vin: str) -> dict[str, Any]:
        """Restart BLE digital key module (cmd_id=430)."""
        return await asyncio.to_thread(self._client.ble_key_restart, vin)

    async def music(self, vin: str, *, operation: str) -> dict[str, Any]:
        """Send music control command (cmd_id=270)."""
        return await asyncio.to_thread(self._client.music, vin, operation=operation)

    async def video(self, vin: str, *, operation: str) -> dict[str, Any]:
        """Send video control command (cmd_id=290)."""
        return await asyncio.to_thread(self._client.video, vin, operation=operation)

    async def fota_download(self, vin: str, *, task_id: int) -> dict[str, Any]:
        """Trigger FOTA download (cmd_id=390)."""
        return await asyncio.to_thread(self._client.fota_download, vin, task_id=task_id)

    async def fota_install(self, vin: str, *, task_id: int) -> dict[str, Any]:
        """Trigger FOTA install (cmd_id=391)."""
        return await asyncio.to_thread(self._client.fota_install, vin, task_id=task_id)

    async def fota_schedule(self, vin: str, *, task_id: int, schedule_time: str) -> dict[str, Any]:
        """Schedule FOTA install (cmd_id=392)."""
        return await asyncio.to_thread(self._client.fota_schedule, vin, task_id=task_id, schedule_time=schedule_time)

    async def rear_seats(self, vin: str, *, seat_info: str) -> dict[str, Any]:
        """Control rear seats (cmd_id=470). C16 only."""
        return await asyncio.to_thread(self._client.rear_seats, vin, seat_info=seat_info)

    async def prepare_car(self, vin: str, *, params: dict[str, Any]) -> dict[str, Any]:
        """Activate pre-conditioning (cmd_id=360). C10/B10 only."""
        return await asyncio.to_thread(self._client.prepare_car, vin, params=params)

    async def seat_adjust(self, vin: str, *, params: dict[str, Any]) -> dict[str, Any]:
        """Seat adjust (cmd_id=280). C10/C16 only."""
        return await asyncio.to_thread(self._client.seat_adjust, vin, params=params)

    async def piloted_parking(self, vin: str, *, params: dict[str, Any]) -> dict[str, Any]:
        """Piloted parking (cmd_id=350). C10/C16 only."""
        return await asyncio.to_thread(self._client.piloted_parking, vin, params=params)

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

    async def ac_on(self, vin: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if params is not None:
            kwargs["params"] = params
        return await asyncio.to_thread(self._client.ac_on, vin, **kwargs)

    async def ac_off(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.ac_off, vin)

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

    async def set_climate_schedule(
        self,
        vin: str,
        *,
        controls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.set_climate_schedule, vin, controls=controls)

    async def cancel_climate_schedule(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.cancel_climate_schedule, vin)

    async def set_prepare_car_schedule(
        self,
        vin: str,
        *,
        controls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.set_prepare_car_schedule, vin, controls=controls)

    async def cancel_prepare_car_schedule(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.cancel_prepare_car_schedule, vin)

    async def get_climate_schedule(self, vin: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._client.get_climate_schedule, vin)

    async def get_ptc_heating_schedule(self, vin: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._client.get_ptc_heating_schedule, vin)

    async def get_charge_schedule(self, vin: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.get_charge_schedule, vin)

    async def get_prepare_car_schedule(self, vin: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._client.get_prepare_car_schedule, vin)

    async def get_fota_schedule(self, vin: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._client.get_fota_schedule, vin)

    async def set_charge_limit(self, vin: str, charge_limit_percent: int) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.set_charge_limit, vin, charge_limit_percent)

    async def set_charge_schedule(
        self,
        vin: str,
        *,
        enabled: bool,
        soc_limit: int = 80,
        start_time: str,
        end_time: str,
        cycles: str,
        circulation: int = 0,
        recharge: int = 0,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._client.set_charge_schedule,
            vin,
            enabled=enabled,
            soc_limit=soc_limit,
            start_time=start_time,
            end_time=end_time,
            cycles=cycles,
            circulation=circulation,
            recharge=recharge,
        )

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

    async def get_share_invitations(self) -> list[ShareInvitation]:
        return await asyncio.to_thread(self._client.get_share_invitations)

    async def accept_share_invitation(self, invitation: ShareInvitation) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.accept_share_invitation, invitation)

    async def reject_share_invitation(self, invitation: ShareInvitation) -> dict[str, Any]:
        return await asyncio.to_thread(self._client.reject_share_invitation, invitation)

    async def get_consumption_weekly_rank(self, vehicle: Vehicle) -> ConsumptionWeeklyRank:
        """Fetch six-week energy consumption and ranking data."""
        return await asyncio.to_thread(self._client.get_consumption_weekly_rank, vehicle)

    async def get_consumption_last_week_breakdown(self, vehicle: Vehicle) -> ConsumptionLastWeekBreakdown:
        """Fetch last-week energy split by driving, A/C, and other."""
        return await asyncio.to_thread(self._client.get_consumption_last_week_breakdown, vehicle)

    async def get_charging_daily_detail(
        self,
        vin: str,
        *,
        start_time: date,
        end_time: date,
        timezone: str = "GMT+00:00",
        page_num: int = 1,
        page_size: int = 10,
    ) -> ChargeDailyDetailPage:
        return await asyncio.to_thread(
            self._client.get_charging_daily_detail,
            vin,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone,
            page_num=page_num,
            page_size=page_size,
        )
