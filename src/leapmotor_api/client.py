"""Leapmotor cloud API client."""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import os
import tempfile
import time
import uuid
from datetime import date  # noqa: TCH003 - used at runtime (.isoformat())
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar
from urllib.parse import quote

import requests
import urllib3

from .const import (
    DEFAULT_BASE_URL,
    DEFAULT_LANGUAGE,
    DEFAULT_POLICY_ID,
    DEFAULT_TIMEOUT,
    KNOWN_ACCOUNT_P12_PASSWORDS,
    REMOTE_CTL_AC_OFF,
    REMOTE_CTL_AC_ON,
    REMOTE_CTL_AC_SCHEDULE,
    REMOTE_CTL_AC_SWITCH,
    REMOTE_CTL_AUTOPARK,
    REMOTE_CTL_BATTERY_PREHEAT,
    REMOTE_CTL_BATTERY_PREHEAT_OFF,
    REMOTE_CTL_BLE_KEY_RESTART,
    REMOTE_CTL_CHARGE_LIMIT,
    REMOTE_CTL_CHARGE_SCHEDULE,
    REMOTE_CTL_CHARGE_START,
    REMOTE_CTL_CHARGE_STOP,
    REMOTE_CTL_FIND_CAR,
    REMOTE_CTL_FOTA_DOWNLOAD,
    REMOTE_CTL_FOTA_INSTALL,
    REMOTE_CTL_FOTA_SCHEDULE,
    REMOTE_CTL_FUEL_HEATING_OFF,
    REMOTE_CTL_FUEL_HEATING_ON,
    REMOTE_CTL_HEALTHY_CHARGING_OFF,
    REMOTE_CTL_HEALTHY_CHARGING_ON,
    REMOTE_CTL_HOTSPOT,
    REMOTE_CTL_LOCK,
    REMOTE_CTL_MUSIC,
    REMOTE_CTL_ON3_OFF,
    REMOTE_CTL_ON3_ON,
    REMOTE_CTL_PILOTED_PARKING,
    REMOTE_CTL_PREPARE_CAR,
    REMOTE_CTL_PREPARE_CAR_SCHEDULE,
    REMOTE_CTL_QUICK_COOL,
    REMOTE_CTL_QUICK_HEAT,
    REMOTE_CTL_REAR_SEATS,
    REMOTE_CTL_REARVIEW_MIRROR_HEAT_OFF,
    REMOTE_CTL_REARVIEW_MIRROR_HEAT_ON,
    REMOTE_CTL_SEAT_ADJUST,
    REMOTE_CTL_SEAT_HEAT,
    REMOTE_CTL_SEAT_VENTILATION,
    REMOTE_CTL_SEND_DESTINATION,
    REMOTE_CTL_SENTRY_MODE_OFF,
    REMOTE_CTL_SENTRY_MODE_ON,
    REMOTE_CTL_SPEED_LIMIT,
    REMOTE_CTL_STEERING_WHEEL_HEAT_OFF,
    REMOTE_CTL_STEERING_WHEEL_HEAT_ON,
    REMOTE_CTL_SUNROOF_CLOSE,
    REMOTE_CTL_SUNROOF_OPEN,
    REMOTE_CTL_SUNSHADE,
    REMOTE_CTL_SUNSHADE_CLOSE,
    REMOTE_CTL_SUNSHADE_OPEN,
    REMOTE_CTL_TRUNK,
    REMOTE_CTL_TRUNK_CLOSE,
    REMOTE_CTL_UNLOCK,
    REMOTE_CTL_UNLOCK_CHARGER,
    REMOTE_CTL_VIDEO,
    REMOTE_CTL_WINDOWS,
    REMOTE_CTL_WINDOWS_CLOSE,
    REMOTE_CTL_WINDOWS_OPEN,
    REMOTE_CTL_WINDSHIELD_DEFROST,
)
from .crypto import (
    build_car_picture_headers,
    build_car_picture_package_headers,
    build_consumption_last_week_headers,
    build_consumption_weekly_rank_headers,
    build_login_headers,
    build_operpwd_verify_headers,
    build_remote_ctl_result_headers,
    build_remote_ctl_write_headers,
    build_remote_ctl_write_headers_without_pin,
    build_signed_headers,
    derive_account_p12_password,
    derive_session_device_id,
    derive_sign_key,
    encrypt_operate_password,
    load_account_cert_from_p12,
)
from .exceptions import (
    LeapmotorAccountCertError,
    LeapmotorApiError,
    LeapmotorAuthError,
    LeapmotorMissingAppCertError,
)
from .mappings import CAR_TYPE_PATH_MAP, REMOTE_ACTION_SPECS
from .models import (
    ChargeDailyDetailPage,
    ConsumptionLastWeekBreakdown,
    ConsumptionWeeklyRank,
    MessageList,
    RemoteActionCtlChargePlan,
    RemoteActionCtlClimateSchedule,
    RemoteActionCtlPrepareCarSchedule,
    RemoteActionCtlSendDestination,
    Vehicle,
    VehicleStatus,
)
from .utils import previous_week_window_seconds

if TYPE_CHECKING:
    from collections.abc import Callable

_T = TypeVar("_T")

_LOGGER = logging.getLogger(__name__)


def _vehicle_status_car_type_path(car_type: str) -> str:
    """Return the backend status path segment for a vehicle model."""
    normalized = car_type.strip().lower()
    return CAR_TYPE_PATH_MAP.get(normalized, normalized)


class LeapmotorApiClient:
    """Client for the Leapmotor vehicle cloud API.

    Uses ``requests.Session`` with mutual TLS (client certificate) for all
    API communication. TLS server certificate verification is disabled by
    default because Leapmotor's API servers use self-signed certificates
    that are not trusted by any public CA.
    """

    def __init__(
        self,
        *,
        username: str,
        password: str,
        app_cert_path: str | Path,
        app_key_path: str | Path,
        operation_password: str | None = None,
        account_p12_password: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        device_id: str | None = None,
        verify_ssl: bool = False,  # Leapmotor servers use self-signed certs
        language: str = DEFAULT_LANGUAGE,
    ) -> None:
        self.username = username
        self.password = password
        self.app_cert_path = str(app_cert_path)
        self.app_key_path = str(app_key_path)
        self.operation_password = operation_password.strip() if operation_password else None
        self.account_p12_password = account_p12_password
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.device_id = device_id or uuid.uuid4().hex
        self.verify_ssl = verify_ssl
        self.language = language

        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.session = requests.Session()
        self.user_id: str | None = None
        self.token: str | None = None
        self.sign_ikm: str | None = None
        self.sign_salt: str | None = None
        self.sign_info: str | None = None
        self.refresh_token: str | None = None
        self.account_cert_file: str | None = None
        self.account_key_file: str | None = None
        self.account_p12_password_used: str | None = None
        self.account_p12_password_source: str | None = None
        self.remote_cert_synced = False
        self.last_api_results: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close HTTP resources and remove temporary account cert files."""
        self.session.close()
        self._clear_account_cert_files()

    def _clear_account_cert_files(self) -> None:
        for file_name in (self.account_cert_file, self.account_key_file):
            if file_name:
                with contextlib.suppress(OSError):
                    Path(file_name).unlink(missing_ok=True)
        self.account_cert_file = None
        self.account_key_file = None

    def _clear_auth(self) -> None:
        self.token = None
        self.user_id = None
        self.sign_ikm = None
        self.sign_salt = None
        self.sign_info = None
        self.refresh_token = None
        self.account_p12_password_used = None
        self.account_p12_password_source = None
        self.remote_cert_synced = False
        self._clear_account_cert_files()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def account_cert(self) -> tuple[str, str]:
        if not self.account_cert_file or not self.account_key_file:
            raise LeapmotorAuthError("No account certificate loaded.")
        return (self.account_cert_file, self.account_key_file)

    @property
    def sign_key(self) -> bytes:
        if self.sign_ikm is None or self.sign_salt is None or self.sign_info is None:
            raise LeapmotorAuthError("No account sign material loaded.")
        return derive_sign_key(self.sign_ikm, self.sign_salt, self.sign_info)

    # ------------------------------------------------------------------
    # Public API — Authentication & Data
    # ------------------------------------------------------------------

    def login(self) -> None:
        """Login with the static app cert and load the account cert from the response."""
        self._ensure_static_cert_files()
        headers = build_login_headers(
            device_id=self.device_id,
            username=self.username,
            password=self.password,
            language=self.language,
        ).to_dict()
        body = self._build_login_form_body()
        response = self._post(
            path="/carownerservice/oversea/acct/v1/login",
            headers=headers,
            data=body,
            cert=(self.app_cert_path, self.app_key_path),
        )
        data = self._parse_api_body(response["status_code"], response["body"], "login")
        login_data = data.get("data") or {}
        self.user_id = str(login_data.get("id"))
        self.token = str(login_data.get("token"))
        self.device_id = derive_session_device_id(self.token, self.device_id)
        self.sign_ikm = str(login_data.get("signIkm"))
        self.sign_salt = str(login_data.get("signSalt"))
        self.sign_info = str(login_data.get("signInfo"))
        self.refresh_token = str(login_data.get("refreshToken") or "")
        self._load_account_cert(login_data)
        self.remote_cert_synced = False

    def token_refresh(self) -> None:
        """Refresh the access token using the stored refresh token.

        Reuses the existing sign material and account certificate from login.
        """
        if not self.refresh_token:
            raise LeapmotorAuthError("No refresh token available; a full login is required.")

        body_params = {"refreshToken": self.refresh_token}
        headers = build_signed_headers(
            sign_key=self.sign_key,
            device_id=self.device_id,
            language=self.language,
            body_params=body_params,
        ).to_dict()
        headers.update(self._auth_headers())
        data = f"refreshToken={quote(self.refresh_token, safe='')}"
        response = self._post(
            path="/carownerservice/oversea/acct/v1/token/refresh",
            headers=headers,
            data=data,
            cert=self.account_cert,
        )
        result = self._parse_api_body(response["status_code"], response["body"], "token refresh")
        refresh_data = result.get("data") or {}
        self.token = str(refresh_data.get("token"))
        self.refresh_token = str(refresh_data.get("refreshToken") or "")
        _LOGGER.debug("Leapmotor token refreshed successfully")

    def _ensure_token(self) -> None:
        """Ensure a valid token is available, refreshing or re-logging in as needed."""
        if not self.token:
            self._ensure_static_cert_files()
            self.login()

    def _retry_on_token_expiry(self, func: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
        """Call *func* and retry once with token refresh (or full login) on auth failure."""
        try:
            return func(*args, **kwargs)
        except LeapmotorApiError as exc:
            if "token" not in str(exc).lower():
                raise
            _LOGGER.debug("Token appears expired, attempting refresh: %s", exc)
            try:
                self.token_refresh()
            except LeapmotorApiError:
                _LOGGER.debug("Token refresh failed, falling back to full login")
                self._clear_auth()
                self._ensure_static_cert_files()
                self.login()
            return func(*args, **kwargs)

    def get_vehicle_list(self) -> list[Vehicle]:
        """Fetch the account vehicle list."""
        self._ensure_token()
        return self._retry_on_token_expiry(self._get_vehicle_list)

    def _get_vehicle_list(self) -> list[Vehicle]:
        headers = build_signed_headers(
            sign_key=self.sign_key, device_id=self.device_id, language=self.language
        ).to_dict()
        headers.update(self._auth_headers())
        response = self._post(
            path="/carownerservice/oversea/vehicle/v1/list",
            headers=headers,
            data="",
            cert=self.account_cert,
        )
        body = self._parse_api_body(response["status_code"], response["body"], "vehicle list")
        list_data = body.get("data") or {}
        vehicles: list[Vehicle] = []
        for bucket, is_shared in (("bindcars", False), ("sharedcars", True)):
            for item in list_data.get(bucket, []) or []:
                vin = item.get("vin")
                if not vin:
                    continue
                vehicles.append(Vehicle.from_dict(data=item, is_shared=is_shared))
        return vehicles

    def get_vehicle_status(self, vehicle: Vehicle) -> VehicleStatus:
        """Fetch status for one vehicle as a typed ``VehicleStatus`` object."""
        self._ensure_token()
        return self._retry_on_token_expiry(self._get_vehicle_status, vehicle)

    def _get_vehicle_status(self, vehicle: Vehicle) -> VehicleStatus:
        raw = self._get_vehicle_raw_status(vehicle)
        return VehicleStatus.from_dict(raw.get("data") or {})

    def get_vehicle_raw_status(self, vehicle: Vehicle) -> dict[str, Any]:
        """Fetch raw status dict for one vehicle (for debug / forward-compatibility)."""
        self._ensure_token()
        return self._retry_on_token_expiry(self._get_vehicle_raw_status, vehicle)

    def _get_vehicle_raw_status(self, vehicle: Vehicle) -> dict[str, Any]:
        car_type_path = _vehicle_status_car_type_path(vehicle.car_type)
        headers = build_signed_headers(
            sign_key=self.sign_key, device_id=self.device_id, vin=vehicle.vin, language=self.language
        ).to_dict()
        headers.update(self._auth_headers())
        response = self._post(
            path=f"/carownerservice/oversea/vehicle/v1/status/get/{car_type_path}",
            headers=headers,
            data=f"vin={quote(vehicle.vin, safe='')}",
            cert=self.account_cert,
        )
        return self._parse_api_body(response["status_code"], response["body"], "vehicle status")

    def get_mileage_energy_detail(self, vehicle: Vehicle) -> dict[str, Any]:
        """Fetch read-only mileage and energy history summary."""
        self._ensure_token()
        return self._retry_on_token_expiry(self._get_mileage_energy_detail, vehicle)

    def _get_mileage_energy_detail(self, vehicle: Vehicle) -> dict[str, Any]:
        headers = build_signed_headers(
            sign_key=self.sign_key, device_id=self.device_id, vin=vehicle.vin, language=self.language
        ).to_dict()
        headers.update(self._auth_headers())
        response = self._post(
            path="/carownerservice/oversea/drivingRecord/v1/mileage/energy/detail",
            headers=headers,
            data=f"vin={quote(vehicle.vin, safe='')}",
            cert=self.account_cert,
        )
        return self._parse_api_body(response["status_code"], response["body"], "mileage energy detail")

    def get_car_picture(self, vehicle: Vehicle) -> dict[str, Any]:
        """Fetch read-only car picture metadata."""
        self._ensure_token()
        return self._retry_on_token_expiry(self._get_car_picture, vehicle)

    def _get_car_picture(self, vehicle: Vehicle) -> dict[str, Any]:
        headers = build_car_picture_headers(
            sign_key=self.sign_key, device_id=self.device_id, vin=vehicle.vin, language=self.language
        ).to_dict()
        headers.update(self._auth_headers())
        body = f"deviceID={quote(self.device_id, safe='')}&vin={quote(vehicle.vin, safe='')}"
        response = self._post(
            path="/carownerservice/oversea/vehicle/v1/carpicture/key",
            headers=headers,
            data=body,
            cert=self.account_cert,
        )
        return self._parse_api_body(response["status_code"], response["body"], "car picture")

    # ------------------------------------------------------------------
    # Public API — Messages
    # ------------------------------------------------------------------

    def get_message_list(self, *, page_no: int = 1, page_size: int = 10) -> MessageList:
        """Fetch the paginated message list."""
        self._ensure_token()
        return self._retry_on_token_expiry(self._get_message_list, page_no=page_no, page_size=page_size)

    def _get_message_list(self, *, page_no: int = 1, page_size: int = 10) -> MessageList:
        body_params = {"pageNo": str(page_no), "pageSize": str(page_size)}
        headers = build_signed_headers(
            sign_key=self.sign_key,
            device_id=self.device_id,
            language=self.language,
            body_params=body_params,
        ).to_dict()
        headers.update(self._auth_headers())
        data = f"pageNo={page_no}&pageSize={page_size}"
        response = self._post(
            path="/carownerservice/oversea/message/v1/list",
            headers=headers,
            data=data,
            cert=self.account_cert,
        )
        body = self._parse_api_body(response["status_code"], response["body"], "message list")
        return MessageList.from_dict(body.get("data") or {})

    def get_unread_message_count(self) -> int:
        """Fetch the unread message count."""
        self._ensure_token()
        return self._retry_on_token_expiry(self._get_unread_message_count)

    def _get_unread_message_count(self) -> int:
        headers = build_signed_headers(
            sign_key=self.sign_key,
            device_id=self.device_id,
            language=self.language,
        ).to_dict()
        headers.update(self._auth_headers())
        response = self._post(
            path="/carownerservice/oversea/message/v1/unread/count",
            headers=headers,
            data="",
            cert=self.account_cert,
        )
        body = self._parse_api_body(response["status_code"], response["body"], "unread message count")
        return int((body.get("data") or {}).get("unread", 0))

    # ------------------------------------------------------------------
    # Public API — Remote Control
    # ------------------------------------------------------------------

    def lock_vehicle(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_LOCK)

    def unlock_vehicle(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_UNLOCK)

    def unlock_charger(self, vin: str) -> dict[str, Any]:
        """Unlock the charging connector before unplugging."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_UNLOCK_CHARGER)

    def open_trunk(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_TRUNK)

    def close_trunk(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_TRUNK_CLOSE)

    def find_vehicle(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_FIND_CAR)

    def hotspot(self, vin: str) -> dict[str, Any]:
        """Trigger hotspot / connectivity command (cmd_id=140)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_HOTSPOT)

    def autopark(self, vin: str) -> dict[str, Any]:
        """Trigger auto park / summon command (cmd_id=150)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_AUTOPARK)

    def control_sunshade(self, vin: str, *, value: str | None = None) -> dict[str, Any]:
        cmd_content = json.dumps({"value": value}, separators=(",", ":")) if value is not None else None
        return self._remote_control(vin=vin, action=REMOTE_CTL_SUNSHADE, cmd_content=cmd_content)

    def open_sunshade(self, vin: str, *, value: str | None = None) -> dict[str, Any]:
        cmd_content = json.dumps({"value": value}, separators=(",", ":")) if value is not None else None
        return self._remote_control(vin=vin, action=REMOTE_CTL_SUNSHADE_OPEN, cmd_content=cmd_content)

    def close_sunshade(self, vin: str, *, value: str | None = None) -> dict[str, Any]:
        cmd_content = json.dumps({"value": value}, separators=(",", ":")) if value is not None else None
        return self._remote_control(vin=vin, action=REMOTE_CTL_SUNSHADE_CLOSE, cmd_content=cmd_content)

    def battery_preheat(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_BATTERY_PREHEAT)

    def battery_preheat_off(self, vin: str) -> dict[str, Any]:
        """Turn off battery preheating."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_BATTERY_PREHEAT_OFF)

    def sentry_mode_on(self, vin: str) -> dict[str, Any]:
        """Enable sentry mode (sentinel / dashcam)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_SENTRY_MODE_ON)

    def sentry_mode_off(self, vin: str) -> dict[str, Any]:
        """Disable sentry mode (sentinel / dashcam)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_SENTRY_MODE_OFF)

    def start_charging(self, vin: str) -> dict[str, Any]:
        """Start charging (cmd_id=193)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_CHARGE_START)

    def stop_charging(self, vin: str) -> dict[str, Any]:
        """Stop charging (cmd_id=193)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_CHARGE_STOP)

    def steering_wheel_heat_on(self, vin: str) -> dict[str, Any]:
        """Enable steering wheel heating (cmd_id=320)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_STEERING_WHEEL_HEAT_ON)

    def steering_wheel_heat_off(self, vin: str) -> dict[str, Any]:
        """Disable steering wheel heating (cmd_id=320)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_STEERING_WHEEL_HEAT_OFF)

    def fuel_heating_on(self, vin: str) -> dict[str, Any]:
        """Enable fuel heating (cmd_id=380)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_FUEL_HEATING_ON)

    def fuel_heating_off(self, vin: str) -> dict[str, Any]:
        """Disable fuel heating (cmd_id=380)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_FUEL_HEATING_OFF)

    def rearview_mirror_heat_on(self, vin: str) -> dict[str, Any]:
        """Enable rearview mirror heating (cmd_id=440)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_REARVIEW_MIRROR_HEAT_ON)

    def rearview_mirror_heat_off(self, vin: str) -> dict[str, Any]:
        """Disable rearview mirror heating (cmd_id=440)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_REARVIEW_MIRROR_HEAT_OFF)

    def set_speed_limit(self, vin: str, *, value: str) -> dict[str, Any]:
        """Set speed limit in km/h (cmd_id=510)."""
        cmd_content = json.dumps({"value": value}, separators=(",", ":"))
        return self._remote_control(vin=vin, action=REMOTE_CTL_SPEED_LIMIT, cmd_content=cmd_content)

    def seat_heat(self, vin: str, *, position: int, level: int) -> dict[str, Any]:
        """Set seat heating (cmd_id=301). Position: 1-6, level: 0-3."""
        cmd_content = json.dumps({"value": f"{position},{level}"}, separators=(",", ":"))
        return self._remote_control(vin=vin, action=REMOTE_CTL_SEAT_HEAT, cmd_content=cmd_content)

    def seat_ventilation(self, vin: str, *, position: int, level: int) -> dict[str, Any]:
        """Set seat ventilation (cmd_id=370). Position: 1-6, level: 0-3."""
        cmd_content = json.dumps({"value": f"{position},{level}"}, separators=(",", ":"))
        return self._remote_control(vin=vin, action=REMOTE_CTL_SEAT_VENTILATION, cmd_content=cmd_content)

    def open_sunroof(self, vin: str) -> dict[str, Any]:
        """Open sunroof (cmd_id=300)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_SUNROOF_OPEN)

    def close_sunroof(self, vin: str) -> dict[str, Any]:
        """Close sunroof (cmd_id=300)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_SUNROOF_CLOSE)

    def healthy_charging_on(self, vin: str) -> dict[str, Any]:
        """Enable healthy charging mode (cmd_id=480)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_HEALTHY_CHARGING_ON)

    def healthy_charging_off(self, vin: str) -> dict[str, Any]:
        """Disable healthy charging mode (cmd_id=480)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_HEALTHY_CHARGING_OFF)

    def on3_on(self, vin: str) -> dict[str, Any]:
        """Enable ON3 mode (cmd_id=410)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_ON3_ON)

    def on3_off(self, vin: str) -> dict[str, Any]:
        """Disable ON3 mode (cmd_id=410)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_ON3_OFF)

    def ble_key_restart(self, vin: str) -> dict[str, Any]:
        """Restart BLE digital key module (cmd_id=430)."""
        return self._remote_control(vin=vin, action=REMOTE_CTL_BLE_KEY_RESTART)

    def music(self, vin: str, *, operation: str) -> dict[str, Any]:
        """Send music control command (cmd_id=270)."""
        cmd_content = json.dumps({"operation": operation}, separators=(",", ":"))
        return self._remote_control(vin=vin, action=REMOTE_CTL_MUSIC, cmd_content=cmd_content)

    def video(self, vin: str, *, operation: str) -> dict[str, Any]:
        """Send video control command (cmd_id=290)."""
        cmd_content = json.dumps({"operation": operation}, separators=(",", ":"))
        return self._remote_control(vin=vin, action=REMOTE_CTL_VIDEO, cmd_content=cmd_content)

    def fota_download(self, vin: str, *, task_id: int) -> dict[str, Any]:
        """Trigger FOTA download (cmd_id=390)."""
        cmd_content = json.dumps({"taskId": task_id}, separators=(",", ":"))
        return self._remote_control(vin=vin, action=REMOTE_CTL_FOTA_DOWNLOAD, cmd_content=cmd_content)

    def fota_install(self, vin: str, *, task_id: int) -> dict[str, Any]:
        """Trigger FOTA install (cmd_id=391)."""
        cmd_content = json.dumps({"taskId": task_id}, separators=(",", ":"))
        return self._remote_control(vin=vin, action=REMOTE_CTL_FOTA_INSTALL, cmd_content=cmd_content)

    def fota_schedule(self, vin: str, *, task_id: int, schedule_time: str) -> dict[str, Any]:
        """Schedule FOTA install (cmd_id=392)."""
        cmd_content = json.dumps({"taskId": task_id, "scheduleTime": schedule_time}, separators=(",", ":"))
        return self._remote_control(vin=vin, action=REMOTE_CTL_FOTA_SCHEDULE, cmd_content=cmd_content)

    def rear_seats(self, vin: str, *, seat_info: str) -> dict[str, Any]:
        """Control rear seats (cmd_id=470). C16 only."""
        cmd_content = json.dumps({"seatInfo": seat_info}, separators=(",", ":"))
        return self._remote_control(vin=vin, action=REMOTE_CTL_REAR_SEATS, cmd_content=cmd_content)

    def prepare_car(self, vin: str, *, params: dict[str, Any]) -> dict[str, Any]:
        """Activate pre-conditioning (cmd_id=360). C10/B10 only."""
        cmd_content = json.dumps(params, separators=(",", ":"))
        return self._remote_control(vin=vin, action=REMOTE_CTL_PREPARE_CAR, cmd_content=cmd_content)

    def seat_adjust(self, vin: str, *, params: dict[str, Any]) -> dict[str, Any]:
        """Seat adjust (cmd_id=280). C10/C16 only."""
        cmd_content = json.dumps(params, separators=(",", ":"))
        return self._remote_control(vin=vin, action=REMOTE_CTL_SEAT_ADJUST, cmd_content=cmd_content)

    def piloted_parking(self, vin: str, *, params: dict[str, Any]) -> dict[str, Any]:
        """Piloted parking (cmd_id=350). C10/C16 only."""
        cmd_content = json.dumps(params, separators=(",", ":"))
        return self._remote_control(vin=vin, action=REMOTE_CTL_PILOTED_PARKING, cmd_content=cmd_content)

    def windows(self, vin: str, *, value: str | None = None) -> dict[str, Any]:
        """Set the window position (cmd_id=230). ``value`` is 0 (closed) to 100 (fully open) on
        C10/T03. A **B10** was observed to use a 0-10 scale instead, actuating only ``0/2/5/10`` —
        see :class:`~leapmotor_api.models.RemoteActionCtlWindows`."""
        cmd_content = json.dumps({"value": value}, separators=(",", ":")) if value is not None else None
        return self._remote_control(vin=vin, action=REMOTE_CTL_WINDOWS, cmd_content=cmd_content)

    def open_windows(self, vin: str, *, value: str | None = None) -> dict[str, Any]:
        cmd_content = json.dumps({"value": value}, separators=(",", ":")) if value is not None else None
        return self._remote_control(vin=vin, action=REMOTE_CTL_WINDOWS_OPEN, cmd_content=cmd_content)

    def close_windows(self, vin: str, *, value: str | None = None) -> dict[str, Any]:
        cmd_content = json.dumps({"value": value}, separators=(",", ":")) if value is not None else None
        return self._remote_control(vin=vin, action=REMOTE_CTL_WINDOWS_CLOSE, cmd_content=cmd_content)

    def ac_switch(self, vin: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        cmd_content = json.dumps(params, separators=(",", ":")) if params is not None else None
        return self._remote_control(vin=vin, action=REMOTE_CTL_AC_SWITCH, cmd_content=cmd_content)

    def ac_on(self, vin: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        cmd_content = json.dumps(params, separators=(",", ":")) if params is not None else None
        return self._remote_control(vin=vin, action=REMOTE_CTL_AC_ON, cmd_content=cmd_content)

    def ac_off(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_AC_OFF)

    def quick_cool(self, vin: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        cmd_content = json.dumps(params, separators=(",", ":")) if params is not None else None
        return self._remote_control(vin=vin, action=REMOTE_CTL_QUICK_COOL, cmd_content=cmd_content)

    def quick_heat(self, vin: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        cmd_content = json.dumps(params, separators=(",", ":")) if params is not None else None
        return self._remote_control(vin=vin, action=REMOTE_CTL_QUICK_HEAT, cmd_content=cmd_content)

    def windshield_defrost(self, vin: str, *, params: dict[str, str] | None = None) -> dict[str, Any]:
        cmd_content = json.dumps(params, separators=(",", ":")) if params is not None else None
        return self._remote_control(vin=vin, action=REMOTE_CTL_WINDSHIELD_DEFROST, cmd_content=cmd_content)

    def set_climate_schedule(
        self,
        vin: str,
        *,
        controls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Set climate schedule (cmd_id=171).

        Each invocation is a **full-state replacement**: the ``controls``
        list must contain *all* active schedules.  Pass an empty list to
        cancel every existing schedule.

        Args:
            vin: Vehicle identification number.
            controls: List of schedule entries. Each entry is a dict with:
                - mode: "cold", "hot", or "wind"
                - on: "1" (enabled) or "0" (disabled)
                - operate: "manual" or "auto"
                - set_id: unique id (format: "air_set" + phoneId + epochMs)
                - start_time: "yyyy-MM-dd HH:mm:00" in vehicle timezone
                - temperature: "18"–"32"
                - update_time: epoch milliseconds as string
                - windlevel: "1"–"7"
                - days: list of ints (0=Sun, 1=Mon...6=Sat), empty=once
                - circle: "in", "out", or None (if unsupported)
                - position: "all"
                - wshld: "0" or "1"
        """
        schedule_spec = RemoteActionCtlClimateSchedule(controls=controls)
        _LOGGER.info("Climate schedule cmd_content: %s", schedule_spec.cmd_content)
        return self._remote_control(
            vin=vin,
            action=REMOTE_CTL_AC_SCHEDULE,
            cmd_content=schedule_spec.cmd_content,
        )

    def cancel_climate_schedule(self, vin: str) -> dict[str, Any]:
        """Cancel all climate schedules (sends empty controls array)."""
        return self.set_climate_schedule(vin, controls=[])

    def set_prepare_car_schedule(
        self,
        vin: str,
        *,
        controls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Set the one-touch prepare-car schedule (cmd_id=361).

        The schedule counterpart of :meth:`prepare_car` (cmd_id=360): instead
        of pre-conditioning the car right now, it programs one or more
        alarm-clock activations. Available on C10/B10 models.

        Each invocation is a **full-state replacement**: the ``controls``
        list must contain *all* active entries. Pass an empty list (or use
        :meth:`cancel_prepare_car_schedule`) to cancel every existing entry.

        Args:
            vin: Vehicle identification number.
            controls: List of schedule entries. Each entry is a dict with:
                - datacontent: the preparation bundle — only the ENABLED
                  dimensions are present. Known keys:
                  - air_condition: same vocabulary as the climate schedule
                    (mode "cold"/"hot"/"nohotcold", circle, windlevel, wshld,
                    operate, temperature) plus position "all" and enable.
                  - seat_setting: front seats — per seat "3"=heat, "13"=vent,
                    "0"=off, plus enable.
                  - steeringWheelHeatCtrl: {enable, level}.
                  - rearMirrorHeating: {enable, value}.
                  - syn_path: a navigation destination synced to the car
                    (latitude/longitude as strings, address, config).
                - days: list of ints (0=Sun..6=Sat), empty = one-time.
                - enable: bool.
                - set_id: opaque id; reuse the same id to edit an entry.
                - start_time: "yyyy-MM-dd HH:mm:ss" in the vehicle timezone.

        The gateway auto-stops the preparation after ~20 minutes.
        """
        schedule_spec = RemoteActionCtlPrepareCarSchedule(controls=controls)
        _LOGGER.info("Prepare-car schedule cmd_content: %s", schedule_spec.cmd_content)
        return self._remote_control(
            vin=vin,
            action=REMOTE_CTL_PREPARE_CAR_SCHEDULE,
            cmd_content=schedule_spec.cmd_content,
        )

    def cancel_prepare_car_schedule(self, vin: str) -> dict[str, Any]:
        """Cancel all prepare-car schedules (sends empty controls array)."""
        return self.set_prepare_car_schedule(vin, controls=[])

    def get_climate_schedule(self, vin: str) -> list[dict[str, Any]]:
        """Retrieve active climate schedules (cmdId=171).

        Returns the ``controls`` list (may be empty if no schedules are set).
        Each entry has the same structure used by :meth:`set_climate_schedule`.
        """
        return self._get_appointment(vin, cmd_id="171")

    def get_ptc_heating_schedule(self, vin: str) -> list[dict[str, Any]]:
        """Retrieve active PTC battery heating schedules (cmdId=161).

        Returns the ``controls`` list. Each entry contains:
        on, set_id, start_time, update_time, days.
        """
        return self._get_appointment(vin, cmd_id="161")

    def get_charge_schedule(self, vin: str) -> dict[str, Any]:
        """Retrieve the charge schedule (cmdId=190).

        Unlike other schedule types, the charge schedule is a flat object
        (not wrapped in a ``controls`` array). Returns the parsed dict
        or an empty dict if no schedule is set.

        The ``recharge`` field reflects the official app's "resume charging
        if schedule is missed" toggle — see ``set_charge_schedule`` for details.
        """
        self._ensure_token()
        return self._retry_on_token_expiry(self._get_charge_appointment, vin)

    def get_prepare_car_schedule(self, vin: str) -> list[dict[str, Any]]:
        """Retrieve active prepare-car schedules (cmdId=361).

        Returns the ``controls`` list. Each entry contains:
        name, desc, enable, set_id, start_time, update_time, days, datacontent.
        """
        return self._get_appointment(vin, cmd_id="361")

    def get_fota_schedule(self, vin: str) -> list[dict[str, Any]]:
        """Retrieve active FOTA install schedules (cmdId=392).

        Returns the ``controls`` list. Each entry contains: pid, start_time.
        """
        return self._get_appointment(vin, cmd_id="392")

    # ------------------------------------------------------------------
    # Private — getAppointment
    # ------------------------------------------------------------------

    def _get_appointment(self, vin: str, *, cmd_id: str) -> list[dict[str, Any]]:
        """Generic retrieval for schedule types that use ``controls`` array wrapper."""
        self._ensure_token()
        return self._retry_on_token_expiry(self._get_appointment_raw, vin, cmd_id)

    def _get_appointment_raw(self, vin: str, cmd_id: str) -> list[dict[str, Any]]:
        parsed = self._fetch_appointment(vin, cmd_id)
        if not parsed:
            return []
        controls: list[dict[str, Any]] = parsed.get("controls", []) if isinstance(parsed, dict) else []
        return controls

    def _get_charge_appointment(self, vin: str) -> dict[str, Any]:
        parsed = self._fetch_appointment(vin, "190")
        if not parsed or not isinstance(parsed, dict):
            return {}
        return parsed

    def _fetch_appointment(self, vin: str, cmd_id: str) -> dict[str, Any] | None:
        """Call getAppointment and double-parse the response data string."""
        headers = build_signed_headers(
            sign_key=self.sign_key,
            device_id=self.device_id,
            vin=vin,
            body_params={"cmdId": cmd_id},
            language=self.language,
        ).to_dict()
        headers.update(self._auth_headers())
        data = f"vin={quote(vin, safe='')}&cmdId={quote(cmd_id, safe='')}"
        response = self._post(
            path="/carownerservice/oversea/vehicle/v1/app/remote/ctl/getAppointment",
            headers=headers,
            data=data,
            cert=self.account_cert,
        )
        try:
            resp_body: dict[str, Any] = json.loads(response["body"])
        except ValueError as exc:
            raise LeapmotorApiError(f"getAppointment returned non-JSON: {response['body'][:200]}") from exc

        result_code = resp_body.get("result", resp_body.get("code"))
        if response["status_code"] != 200 or result_code != 0:
            msg = resp_body.get("message") or response["body"][:200]
            # "No such permission" means the vehicle doesn't support this schedule type
            if "permission" in (msg or "").lower():
                _LOGGER.debug("getAppointment(cmdId=%s): vehicle lacks permission", cmd_id)
                return None
            raise LeapmotorApiError(f"getAppointment(cmdId={cmd_id}) failed: {msg}")

        # data is a JSON *string* — double-parse
        raw_data = resp_body.get("data")
        if not raw_data:
            return None
        if isinstance(raw_data, str):
            try:
                result: dict[str, Any] = json.loads(raw_data)
                return result
            except ValueError:
                return None
        return dict(raw_data)

    def set_charge_limit(self, vin: str, charge_limit_percent: int) -> dict[str, Any]:
        """Set the charge limit while preserving the current charging plan values."""
        # Use the dedicated schedule API instead of vehicle status,
        # which may not include charge plan fields on some models (e.g. T03).
        schedule = self.get_charge_schedule(vin)

        if schedule:
            # The cloud omits fields that aren't set for the current plan
            # (an enabled start-time-only plan returns no cycles/endtime/recharge).
            # Preserve every field the response *does* include — especially
            # starttime and chargeEnable — and fall back per-field only for the
            # ones that are genuinely absent. Guarding on cycles here would route
            # such plans into the all-defaults branch below, resetting the start
            # time to 00:00 and disabling the schedule (issue #18).
            charge_spec = RemoteActionCtlChargePlan(
                charge_enable=schedule.get("chargeEnable", 0),
                chargesoc=int(charge_limit_percent),
                circulation=schedule.get("circulation", 0),
                cycles=schedule.get("cycles") or "1,2,3,4,5,6,7",
                endtime=schedule.get("endtime") or "08:00",
                recharge=schedule.get("recharge", 0),
                starttime=schedule.get("starttime") or "00:00",
            )
        else:
            # No existing schedule — use defaults with schedule disabled
            charge_spec = RemoteActionCtlChargePlan(
                charge_enable=0,
                chargesoc=int(charge_limit_percent),
                circulation=0,
                cycles="1,2,3,4,5,6,7",
                endtime="08:00",
                recharge=0,
                starttime="00:00",
            )

        return self._remote_control(
            vin=vin,
            action=REMOTE_CTL_CHARGE_LIMIT,
            cmd_content=charge_spec.cmd_content,
        )

    def set_charge_schedule(
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
        """Set the full charging schedule.

        Args:
            vin: Vehicle identification number.
            enabled: Whether the schedule is active.
            soc_limit: Target SOC percentage (default 80).
            start_time: Schedule start time (e.g. "23:00").
            end_time: Schedule end time (e.g. "07:00").
            cycles: Days of the week (e.g. "1,2,3,4,5,6,7").
            circulation: Repeat mode (0=once, 1=repeat).
            recharge: Auto-recharge flag (0=off, 1=on). Mirrors the official
                app's "resume charging if schedule is missed" setting: when
                on, the vehicle resumes/retries charging if it is unplugged
                or falls outside the configured time window, instead of
                waiting for the next scheduled cycle. Confirmed empirically:
                toggling that app setting changes only this field
                (``chargeScheduleRecharge`` / ``recharge``) in the schedule
                returned by ``get_charge_schedule``.
        """
        charge_spec = RemoteActionCtlChargePlan(
            charge_enable=1 if enabled else 0,
            chargesoc=soc_limit,
            circulation=circulation,
            cycles=cycles,
            endtime=end_time,
            recharge=recharge,
            starttime=start_time,
        )
        return self._remote_control(
            vin=vin,
            action=REMOTE_CTL_CHARGE_SCHEDULE,
            cmd_content=charge_spec.cmd_content,
        )

    def send_destination(
        self,
        vin: str,
        *,
        address: str,
        address_name: str,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        """Send a navigation destination to the vehicle (does not require PIN)."""
        dest_spec = RemoteActionCtlSendDestination(
            address=address,
            address_name=address_name,
            latitude=latitude,
            longitude=longitude,
        )
        return self._remote_control(
            vin=vin,
            action=REMOTE_CTL_SEND_DESTINATION,
            cmd_content=dest_spec.cmd_content,
        )

    def download_car_picture_package(self, *, picture_key: str) -> bytes:
        """Download the picture package ZIP for one already-resolved picture key."""
        headers = build_car_picture_package_headers(
            sign_key=self.sign_key,
            device_id=self.device_id,
            picture_key=picture_key,
            language=self.language,
        ).to_dict()
        headers.update(self._auth_headers())
        response = self._post_binary(
            path="/carownerservice/oversea/vehicle/v1/carpicture/package",
            headers=headers,
            data=f"key={quote(picture_key, safe='')}",
            cert=self.account_cert,
        )
        if response["status_code"] != 200:
            raise LeapmotorApiError(f"car picture package failed with HTTP {response['status_code']}")
        return bytes(response["body"])

    def get_consumption_weekly_rank(self, vehicle: Vehicle) -> ConsumptionWeeklyRank:
        """Fetch six-week energy consumption and ranking data."""
        self._ensure_token()
        return self._retry_on_token_expiry(self._get_consumption_weekly_rank, vehicle)

    def _get_consumption_weekly_rank(self, vehicle: Vehicle) -> ConsumptionWeeklyRank:
        headers = build_consumption_weekly_rank_headers(
            sign_key=self.sign_key, device_id=self.device_id, carvin=vehicle.vin, language=self.language
        ).to_dict()
        headers.update(self._auth_headers())
        response = self._post(
            path="/carownerservice/oversea/drivingRecord/v1/getLastNweeks100kmECAndRank",
            headers=headers,
            data=f"carvin={quote(vehicle.vin, safe='')}",
            cert=self.account_cert,
        )
        body = self._parse_api_body(response["status_code"], response["body"], "consumption weekly rank")
        return ConsumptionWeeklyRank.from_dict(body.get("data") or {})

    def get_consumption_last_week_breakdown(self, vehicle: Vehicle) -> ConsumptionLastWeekBreakdown:
        """Fetch last-week energy split by driving, A/C, and other."""
        self._ensure_token()
        return self._retry_on_token_expiry(self._get_consumption_last_week_breakdown, vehicle)

    def _get_consumption_last_week_breakdown(self, vehicle: Vehicle) -> ConsumptionLastWeekBreakdown:
        begintime, endtime = previous_week_window_seconds()
        headers = build_consumption_last_week_headers(
            sign_key=self.sign_key,
            device_id=self.device_id,
            carvin=vehicle.vin,
            begintime=str(begintime),
            endtime=str(endtime),
            language=self.language,
        ).to_dict()
        headers.update(self._auth_headers())
        body = f"endtime={endtime}&begintime={begintime}&carvin={quote(vehicle.vin, safe='')}"
        response = self._post(
            path="/carownerservice/oversea/drivingRecord/v1/getLastweekEC",
            headers=headers,
            data=body,
            cert=self.account_cert,
        )
        result = self._parse_api_body(response["status_code"], response["body"], "consumption last week breakdown")
        return ConsumptionLastWeekBreakdown.from_dict(result.get("data") or {})

    def get_charging_daily_detail(
        self,
        vin: str,
        *,
        start_time: date,
        end_time: date,
        timezone: str = "GMT+00:00",
        page_num: int = 1,
        page_size: int = 10,
    ) -> ChargeDailyDetailPage:
        """Fetch paginated daily charging detail for a vehicle."""
        self._ensure_token()
        return self._retry_on_token_expiry(
            self._get_charging_daily_detail,
            vin,
            start_time.isoformat(),
            end_time.isoformat(),
            timezone,
            page_num,
            page_size,
        )

    def _get_charging_daily_detail(
        self, vin: str, start_time: str, end_time: str, timezone: str, page_num: int, page_size: int
    ) -> ChargeDailyDetailPage:
        body_params = {
            "vin": vin,
            "timeZone": timezone,
            "startTime": start_time,
            "endTime": end_time,
            "pageNum": str(page_num),
            "pageSize": str(page_size),
        }
        headers = build_signed_headers(
            sign_key=self.sign_key,
            device_id=self.device_id,
            language=self.language,
            body_params=body_params,
        ).to_dict()
        headers.update(self._auth_headers())
        headers["Content-Type"] = "application/json"
        response = self._post_json(
            path="/carownerservice/charge/daily/detail/page",
            headers=headers,
            json_body={
                "vin": vin,
                "timeZone": timezone,
                "startTime": start_time,
                "endTime": end_time,
                "pageNum": page_num,
                "pageSize": page_size,
            },
            cert=self.account_cert,
        )
        body = self._parse_api_body(response["status_code"], response["body"], "charging daily detail")
        return ChargeDailyDetailPage.from_dict(body.get("data") or {})

    # ------------------------------------------------------------------
    # Private — Data fetching
    # ------------------------------------------------------------------

    def _fetch_optional_read(self, label: str, fetcher: Any, vehicle: Vehicle) -> dict[str, Any] | None:
        try:
            result: dict[str, Any] = fetcher(vehicle)
        except LeapmotorApiError as exc:
            _LOGGER.debug("Leapmotor optional read failed for %s: %s", label, exc)
            return None
        return result

    # ------------------------------------------------------------------
    # Private — Remote control
    # ------------------------------------------------------------------

    def _remote_control(self, *, vin: str, action: str, cmd_content: str | None = None) -> dict[str, Any]:
        if not self.token:
            self.login()
        if action not in REMOTE_ACTION_SPECS:
            raise LeapmotorApiError(f"Remote action not configured: {action}")

        spec = REMOTE_ACTION_SPECS[action]

        if spec.requires_pin and not self.operation_password:
            raise LeapmotorAuthError(
                "No vehicle PIN configured. Read-only data works without a PIN, but remote-control actions require it."
            )

        vehicle = self._find_vehicle_by_vin(vin)
        if spec.required_right is not None and not vehicle.has_right(spec.required_right):
            _LOGGER.warning(
                "Vehicle %s may lack permission for '%s' (requires right %s=%d). "
                "Proceeding anyway — the server will enforce permissions.",
                vin,
                action,
                spec.required_right.name,
                spec.required_right.value,
            )

        resolved_content = cmd_content if cmd_content is not None else spec.cmd_content

        if not spec.requires_pin:
            return self._remote_control_without_pin_raw(
                vin=vehicle.vin,
                cmd_id=spec.cmd_id,
                cmd_content=resolved_content,
                action_label=action,
            )

        if not self.operation_password:
            raise LeapmotorAuthError(
                "No vehicle PIN configured. Read-only data works without a PIN, but remote-control actions require it."
            )
        return self._remote_control_raw(
            vin=vehicle.vin,
            cmd_id=spec.cmd_id,
            cmd_content=resolved_content,
            action_label=action,
            vehicle=vehicle,
        )

    def _remote_control_raw(
        self,
        *,
        vin: str,
        cmd_id: str,
        cmd_content: str,
        action_label: str,
        vehicle: Vehicle | None = None,
    ) -> dict[str, Any]:
        """Execute one raw remote-control command with the verified write flow."""
        _LOGGER.info("Starting Leapmotor remote action %s for VIN %s", action_label, vin)
        if not self.token:
            self.login()
        if not self.operation_password:
            raise LeapmotorAuthError(
                "No vehicle PIN configured. Read-only data works without a PIN, but remote-control actions require it."
            )
        if vehicle is None:
            vehicle = self._find_vehicle_by_vin(vin)

        operate_password = encrypt_operate_password(self.operation_password, self.token)
        self._ensure_remote_cert_sync()

        # Step 1: Verify operation password
        verify_headers = build_operpwd_verify_headers(
            sign_key=self.sign_key,
            device_id=self.device_id,
            vin=vin,
            operation_password=operate_password,
            language=self.language,
        ).to_dict()
        verify_headers.update(self._auth_headers())
        verify_body = f"operatePassword={quote(operate_password, safe='')}&vin={quote(vin, safe='')}"
        verify_response = self._post(
            path="/carownerservice/oversea/vehicle/v1/operPwd/verify",
            headers=verify_headers,
            data=verify_body,
            cert=self.account_cert,
        )
        _LOGGER.debug(
            "Leapmotor remote verify response for %s: HTTP %s %s",
            action_label,
            verify_response["status_code"],
            verify_response["body"],
        )
        self._parse_api_body(verify_response["status_code"], verify_response["body"], "remote verify")

        # Step 2: Execute remote command
        headers = build_remote_ctl_write_headers(
            sign_key=self.sign_key,
            device_id=self.device_id,
            vin=vin,
            cmd_content=cmd_content,
            cmd_id=cmd_id,
            operation_password=operate_password,
            language=self.language,
        ).to_dict()
        headers.update(self._auth_headers())
        body = (
            f"cmdContent={quote(cmd_content, safe='')}"
            f"&vin={quote(vin, safe='')}"
            f"&cmdId={quote(cmd_id, safe='')}"
            f"&operatePassword={quote(operate_password, safe='')}"
        )
        response = self._post(
            path="/carownerservice/oversea/vehicle/v1/app/remote/ctl",
            headers=headers,
            data=body,
            cert=self.account_cert,
        )
        _LOGGER.info(
            "Leapmotor remote ctl response for %s: HTTP %s %s",
            action_label,
            response["status_code"],
            response["body"],
        )
        _LOGGER.info("Leapmotor remote ctl request body for %s: %s", action_label, body)
        result = self._parse_api_body(response["status_code"], response["body"], f"remote {action_label}")

        # Step 3: Poll for result
        remote_data = result.get("data") or {}
        remote_ctl_id = remote_data.get("remoteCtlId")
        if remote_ctl_id:
            self._poll_remote_control_result(
                vin=vehicle.vin,
                car_id=vehicle.car_id,
                remote_ctl_id=str(remote_ctl_id),
                timeout_ms=int(remote_data.get("queryRemoteCtlResultTimeout") or 30000),
                interval_ms=int(remote_data.get("queryInterval") or 2000),
            )
        return result

    def _remote_control_without_pin_raw(
        self,
        *,
        vin: str,
        cmd_id: str,
        cmd_content: str,
        action_label: str,
    ) -> dict[str, Any]:
        """Execute a remote-control command that does not use operatePassword."""
        _LOGGER.info("Starting Leapmotor remote action %s for VIN %s", action_label, vin)
        if not self.token:
            self.login()

        headers = build_remote_ctl_write_headers_without_pin(
            sign_key=self.sign_key,
            device_id=self.device_id,
            vin=vin,
            cmd_content=cmd_content,
            cmd_id=cmd_id,
            language=self.language,
        ).to_dict()
        headers.update(self._auth_headers())
        body = f"cmdContent={quote(cmd_content, safe='')}&vin={quote(vin, safe='')}&cmdId={quote(cmd_id, safe='')}"
        response = self._post(
            path="/carownerservice/oversea/vehicle/v1/app/remote/ctl",
            headers=headers,
            data=body,
            cert=self.account_cert,
        )
        _LOGGER.debug(
            "Leapmotor remote ctl response for %s: HTTP %s %s",
            action_label,
            response["status_code"],
            response["body"],
        )
        return self._parse_api_body(
            response["status_code"],
            response["body"],
            f"remote {action_label}",
        )

    def _ensure_remote_cert_sync(self) -> None:
        if self.remote_cert_synced:
            return
        headers = build_signed_headers(
            sign_key=self.sign_key, device_id=self.device_id, language=self.language
        ).to_dict()
        headers.update(self._auth_headers())
        response = self._post(
            path="/carownerservice/oversea/vehicle/v1/cert/sync",
            headers=headers,
            data="",
            cert=(self.app_cert_path, self.app_key_path),
        )
        self._parse_api_body(response["status_code"], response["body"], "cert sync")
        self.remote_cert_synced = True

    def _poll_remote_control_result(
        self,
        *,
        vin: str,
        car_id: str | None,
        remote_ctl_id: str,
        timeout_ms: int,
        interval_ms: int,
    ) -> dict[str, Any]:
        del vin, car_id
        data = f"remoteCtlId={quote(remote_ctl_id, safe='')}"
        deadline = time.monotonic() + max(timeout_ms, 1000) / 1000.0
        last_result: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            headers = build_remote_ctl_result_headers(
                sign_key=self.sign_key,
                device_id=self.device_id,
                remote_ctl_id=remote_ctl_id,
                language=self.language,
            ).to_dict()
            headers.update(self._auth_headers())
            response = self._post(
                path="/carownerservice/oversea/vehicle/v1/app/remote/ctl/result/query",
                headers=headers,
                data=data,
                cert=self.account_cert,
            )
            _LOGGER.debug(
                "Leapmotor remote poll response: HTTP %s %s",
                response["status_code"],
                response["body"],
            )
            last_result = self._parse_api_body(response["status_code"], response["body"], "remote control result")
            if (last_result.get("data")) == 1:
                return last_result
            sleep_seconds = max(interval_ms, 250) / 1000.0
            if time.monotonic() + sleep_seconds >= deadline:
                break
            time.sleep(sleep_seconds)
        raise LeapmotorApiError(f"Timed out waiting for remote control result: {last_result}")

    def _find_vehicle_by_vin(self, vin: str) -> Vehicle:
        for vehicle in self.get_vehicle_list():
            if vehicle.vin == vin:
                return vehicle
        raise LeapmotorApiError(f"Vehicle not found for VIN {vin}")

    # ------------------------------------------------------------------
    # Private — HTTP & cert management
    # ------------------------------------------------------------------

    def _ensure_static_cert_files(self) -> None:
        missing = [
            name
            for name, path in [
                ("app_cert", self.app_cert_path),
                ("app_key", self.app_key_path),
            ]
            if not Path(path).exists()
        ]
        if missing:
            raise LeapmotorMissingAppCertError("Missing local app certificate material: " + ", ".join(missing))

    def _post(
        self,
        *,
        path: str,
        headers: dict[str, str],
        data: str,
        cert: tuple[str, str],
    ) -> dict[str, Any]:
        """Send a POST request using requests.Session with mutual TLS."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            resp = self.session.post(
                url,
                headers=headers,
                data=data.encode("utf-8") if data else b"",
                cert=cert,
                verify=self.verify_ssl,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LeapmotorApiError(f"HTTP request failed: {exc}") from exc

        _LOGGER.debug(
            "Leapmotor remote response for %s: HTTP %s %s",
            path,
            resp.status_code,
            resp.text,
        )

        return {
            "status_code": resp.status_code,
            "body": resp.text,
            "headers": dict(resp.headers),
        }

    def _get(
        self,
        *,
        path: str,
        headers: dict[str, str],
        params: dict[str, str],
        cert: tuple[str, str],
    ) -> dict[str, Any]:
        """Send a GET request using requests.Session with mutual TLS."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            resp = self.session.get(
                url,
                headers=headers,
                params=params,
                cert=cert,
                verify=self.verify_ssl,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LeapmotorApiError(f"HTTP request failed: {exc}") from exc

        _LOGGER.debug(
            "Leapmotor remote response for %s: HTTP %s %s",
            path,
            resp.status_code,
            resp.text,
        )

        return {
            "status_code": resp.status_code,
            "body": resp.text,
            "headers": dict(resp.headers),
        }

    def _post_json(
        self,
        *,
        path: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        cert: tuple[str, str],
    ) -> dict[str, Any]:
        """Send a POST request with a JSON body using requests.Session with mutual TLS."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            resp = self.session.post(
                url,
                headers=headers,
                json=json_body,
                cert=cert,
                verify=self.verify_ssl,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LeapmotorApiError(f"HTTP request failed: {exc}") from exc

        _LOGGER.debug(
            "Leapmotor remote response for %s: HTTP %s %s",
            path,
            resp.status_code,
            resp.text,
        )

        return {
            "status_code": resp.status_code,
            "body": resp.text,
            "headers": dict(resp.headers),
        }

    def _post_binary(
        self,
        *,
        path: str,
        headers: dict[str, str],
        data: str,
        cert: tuple[str, str],
    ) -> dict[str, Any]:
        """Send a POST request and return the raw response body as bytes."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            resp = self.session.post(
                url,
                headers=headers,
                data=data.encode("utf-8") if data else b"",
                cert=cert,
                verify=self.verify_ssl,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LeapmotorApiError(f"HTTP request failed: {exc}") from exc

        _LOGGER.debug(
            "Leapmotor binary response for %s: HTTP %s (%d bytes)",
            path,
            resp.status_code,
            len(resp.content),
        )

        return {
            "status_code": resp.status_code,
            "body": resp.content,
            "headers": dict(resp.headers),
        }

    def _load_account_cert(self, login_data: dict[str, Any]) -> None:
        base64_cert = str(login_data.get("base64Cert", ""))
        p12_bytes = base64.b64decode(base64_cert)

        candidates: list[tuple[str, str]] = []
        if self.account_p12_password:
            candidates.append(("provided", self.account_p12_password))
        try:
            derived_password = derive_account_p12_password(login_data["id"], str(login_data["uid"]))
        except (KeyError, TypeError, ValueError):
            derived_password = None
        if derived_password and all(password != derived_password for _, password in candidates):
            candidates.append(("derived", derived_password))
        candidates.extend(
            ("fallback", password)
            for password in KNOWN_ACCOUNT_P12_PASSWORDS
            if all(candidate != password for _, candidate in candidates)
        )

        last_error: Exception | None = None
        for source, password in candidates:
            try:
                cert_pem, key_pem = load_account_cert_from_p12(p12_bytes, password)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue

            # Write cert files with restricted permissions (fix: SECURITY_AUDIT #3)
            cert_fd, cert_path = tempfile.mkstemp(suffix="-leapmotor-cert.pem")
            key_fd, key_path = tempfile.mkstemp(suffix="-leapmotor-key.pem")
            try:
                os.chmod(cert_path, 0o600)
                os.chmod(key_path, 0o600)
                os.write(cert_fd, cert_pem)
                os.write(key_fd, key_pem)
            finally:
                os.close(cert_fd)
                os.close(key_fd)

            self.account_cert_file = cert_path
            self.account_key_file = key_path
            self.account_p12_password_used = password
            self.account_p12_password_source = source
            return

        raise LeapmotorAccountCertError(f"Could not open account certificate: {last_error}")

    def _build_login_form_body(self) -> str:
        return (
            "isRecoverAcct=0"
            f"&password={quote(self.password, safe='')}"
            f"&policyId={DEFAULT_POLICY_ID}"
            "&loginMethod=1"
            f"&email={quote(self.username, safe='')}"
        )

    def _auth_headers(self) -> dict[str, str]:
        if not self.user_id or not self.token:
            raise LeapmotorAuthError("Not authenticated.")
        return {
            "userId": self.user_id,
            "token": self.token,
        }

    def _parse_api_body(self, status_code: int, body: str, label: str) -> dict[str, Any]:
        try:
            data: dict[str, Any] = json.loads(body)
        except ValueError as exc:
            self._record_api_result(label, status_code=status_code, code=None, message="non_json")
            raise LeapmotorApiError(f"{label} returned non-JSON response: {body[:200]}") from exc
        self._record_api_result(
            label,
            status_code=status_code,
            code=data.get("code"),
            message=data.get("message"),
        )
        if status_code != 200 or data.get("code") != 0:
            message = data.get("message") or body[:200]
            if label == "login":
                raise LeapmotorAuthError(f"Leapmotor login failed: {message}")
            if label == "remote verify":
                raise LeapmotorAuthError(
                    f"Leapmotor remote verify failed: {message}. "
                    "The backend currently rejects the verification request "
                    "before any vehicle action is sent."
                )
            raise LeapmotorApiError(f"Leapmotor {label} failed: {message}")
        return data

    def _record_api_result(self, label: str, *, status_code: int, code: Any, message: Any) -> None:
        self.last_api_results[label] = {
            "http_status": status_code,
            "code": code,
            "message": message,
            "updated_at": time.time(),
        }
