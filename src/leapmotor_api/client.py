"""Leapmotor cloud API client."""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
import urllib3

from .const import (
    DEFAULT_BASE_URL,
    DEFAULT_LANGUAGE,
    KNOWN_ACCOUNT_P12_PASSWORDS,
    REMOTE_ACTION_SPECS,
    REMOTE_CTL_AC_SWITCH,
    REMOTE_CTL_BATTERY_PREHEAT,
    REMOTE_CTL_FIND_CAR,
    REMOTE_CTL_LOCK,
    REMOTE_CTL_QUICK_COOL,
    REMOTE_CTL_QUICK_HEAT,
    REMOTE_CTL_SUNSHADE,
    REMOTE_CTL_SUNSHADE_CLOSE,
    REMOTE_CTL_SUNSHADE_OPEN,
    REMOTE_CTL_TRUNK,
    REMOTE_CTL_TRUNK_CLOSE,
    REMOTE_CTL_TRUNK_OPEN,
    REMOTE_CTL_UNLOCK,
    REMOTE_CTL_WINDSHIELD_DEFROST,
    REMOTE_CTL_WINDOWS,
    REMOTE_CTL_WINDOWS_CLOSE,
    REMOTE_CTL_WINDOWS_OPEN,
)
from .crypto import (
    build_car_picture_headers,
    build_car_picture_package_headers,
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
from .models import Vehicle, VehicleStatus

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


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
                try:
                    Path(file_name).unlink(missing_ok=True)
                except OSError:
                    pass
        self.account_cert_file = None
        self.account_key_file = None

    def _clear_auth(self) -> None:
        self.token = None
        self.user_id = None
        self.sign_ikm = None
        self.sign_salt = None
        self.sign_info = None
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

    def fetch_data(self) -> dict[str, Any]:
        """Authenticate if needed and fetch all read-only vehicle data."""
        if not self.token:
            self._ensure_static_cert_files()
            self.login()

        try:
            return self._fetch_authenticated_data()
        except LeapmotorApiError:
            self._clear_auth()
            self._ensure_static_cert_files()
            self.login()
            return self._fetch_authenticated_data()

    def login(self) -> None:
        """Login with the static app cert and load the account cert from the response."""
        self._ensure_static_cert_files()
        headers = build_login_headers(
            device_id=self.device_id,
            username=self.username,
            password=self.password,
            language=self.language,
        )
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
        self._load_account_cert(login_data)
        self.remote_cert_synced = False

    def get_vehicle_list(self) -> list[Vehicle]:
        """Fetch the account vehicle list."""
        headers = build_signed_headers(sign_key=self.sign_key, device_id=self.device_id, language=self.language)
        headers.update(self._auth_headers(content_type="application/x-www-form-urlencoded"))
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
                vehicles.append(
                    Vehicle(
                        vin=str(vin),
                        car_id=str(item["carId"]) if item.get("carId") is not None else None,
                        car_type=str(item.get("carType") or "C10"),
                        nickname=item.get("nickName"),
                        is_shared=is_shared,
                        year=_safe_int(item.get("year")),
                        rights=item.get("rightList"),
                        abilities=[str(value) for value in item.get("abilities") or []],
                        module_rights=item.get("moduleRights"),
                    )
                )
        return vehicles

    def get_vehicle_status(self, vehicle: Vehicle) -> VehicleStatus:
        """Fetch status for one vehicle as a typed ``VehicleStatus`` object."""
        raw = self.get_vehicle_raw_status(vehicle)
        return VehicleStatus.from_dict(raw.get("data") or {})

    def get_vehicle_raw_status(self, vehicle: Vehicle) -> dict[str, Any]:
        """Fetch raw status dict for one vehicle (for debug / forward-compatibility)."""
        car_type_path = vehicle.car_type.lower()
        headers = build_signed_headers(sign_key=self.sign_key, device_id=self.device_id, vin=vehicle.vin, language=self.language)
        headers.update(self._auth_headers(content_type="application/x-www-form-urlencoded"))
        response = self._post(
            path=f"/carownerservice/oversea/vehicle/v1/status/get/{car_type_path}",
            headers=headers,
            data=f"vin={quote(vehicle.vin, safe='')}",
            cert=self.account_cert,
        )
        return self._parse_api_body(response["status_code"], response["body"], "vehicle status")

    def get_mileage_energy_detail(self, vehicle: Vehicle) -> dict[str, Any]:
        """Fetch read-only mileage and energy history summary."""
        headers = build_signed_headers(sign_key=self.sign_key, device_id=self.device_id, vin=vehicle.vin, language=self.language)
        headers.update(self._auth_headers(content_type="application/x-www-form-urlencoded"))
        response = self._post(
            path="/carownerservice/oversea/drivingRecord/v1/mileage/energy/detail",
            headers=headers,
            data=f"vin={quote(vehicle.vin, safe='')}",
            cert=self.account_cert,
        )
        return self._parse_api_body(response["status_code"], response["body"], "mileage energy detail")

    def get_car_picture(self, vehicle: Vehicle) -> dict[str, Any]:
        """Fetch read-only car picture metadata."""
        headers = build_car_picture_headers(sign_key=self.sign_key, device_id=self.device_id, vin=vehicle.vin, language=self.language)
        headers.update(self._auth_headers(content_type="application/x-www-form-urlencoded"))
        body = (
            f"deviceID={quote(self.device_id, safe='')}"
            f"&vin={quote(vehicle.vin, safe='')}"
        )
        response = self._post(
            path="/carownerservice/oversea/vehicle/v1/carpicture/key",
            headers=headers,
            data=body,
            cert=self.account_cert,
        )
        return self._parse_api_body(response["status_code"], response["body"], "car picture")

    # ------------------------------------------------------------------
    # Public API — Remote Control
    # ------------------------------------------------------------------

    def lock_vehicle(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_LOCK)

    def unlock_vehicle(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_UNLOCK)

    def open_trunk(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_TRUNK)

    def close_trunk(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_TRUNK_CLOSE)

    def find_vehicle(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_FIND_CAR)

    def control_sunshade(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_SUNSHADE)

    def open_sunshade(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_SUNSHADE_OPEN)

    def close_sunshade(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_SUNSHADE_CLOSE)

    def battery_preheat(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_BATTERY_PREHEAT)

    def windows(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_WINDOWS)

    def open_windows(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_WINDOWS_OPEN)

    def close_windows(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_WINDOWS_CLOSE)

    def ac_switch(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_AC_SWITCH)

    def quick_cool(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_QUICK_COOL)

    def quick_heat(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_QUICK_HEAT)

    def windshield_defrost(self, vin: str) -> dict[str, Any]:
        return self._remote_control(vin=vin, action=REMOTE_CTL_WINDSHIELD_DEFROST)

    def set_charge_limit(self, vin: str, charge_limit_percent: int) -> dict[str, Any]:
        """Set the charge limit while preserving the current charging plan values."""
        vehicle = self._find_vehicle_by_vin(vin)
        status_json = self.get_vehicle_raw_status(vehicle)
        charge_plan = (((status_json.get("data") or {}).get("config") or {}).get("3") or {})

        start_time = charge_plan.get("beginTime")
        end_time = charge_plan.get("endTime")
        cycles = charge_plan.get("cycles")
        if not start_time or not end_time or not cycles:
            raise LeapmotorApiError(
                "Current charging plan is incomplete, cannot safely update charge limit."
            )

        cmd_content = json.dumps(
            {
                "chargeEnable": 1 if _safe_int(charge_plan.get("isEnable")) else 0,
                "chargesoc": int(charge_limit_percent),
                "circulation": _safe_int(charge_plan.get("circulation")) or 0,
                "cycles": str(cycles),
                "endtime": str(end_time),
                "recharge": _safe_int(charge_plan.get("recharge")) or 0,
                "starttime": str(start_time),
            },
            separators=(",", ":"),
        )
        return self._remote_control_raw(
            vin=vin,
            cmd_id="190",
            cmd_content=cmd_content,
            action_label="set_charge_limit",
            vehicle=vehicle,
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
        vehicle = self._find_vehicle_by_vin(vin)
        cmd_content = json.dumps(
            {
                "address": address,
                "addressname": address_name,
                "latitude": str(latitude),
                "linenum": "0",
                "longitude": str(longitude),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return self._remote_control_without_pin_raw(
            vin=vehicle.vin,
            cmd_id="180",
            cmd_content=cmd_content,
            action_label="send_destination",
        )

    def download_car_picture_package(self, *, picture_key: str) -> bytes:
        """Download the picture package ZIP for one already-resolved picture key."""
        headers = build_car_picture_package_headers(
            sign_key=self.sign_key, device_id=self.device_id, picture_key=picture_key,
            language=self.language,
        )
        headers.update(self._auth_headers(content_type="application/x-www-form-urlencoded"))
        response = self._post_binary(
            path="/carownerservice/oversea/vehicle/v1/carpicture/package",
            headers=headers,
            data=f"key={quote(picture_key, safe='')}",
            cert=self.account_cert,
        )
        if response["status_code"] != 200:
            raise LeapmotorApiError(
                f"car picture package failed with HTTP {response['status_code']}"
            )
        return response["body"]

    # ------------------------------------------------------------------
    # Private — Data fetching
    # ------------------------------------------------------------------

    def _fetch_authenticated_data(self) -> dict[str, Any]:
        vehicles = self.get_vehicle_list()
        result: dict[str, Any] = {
            "user_id": self.user_id,
            "vehicles": {},
            "account_p12_password_source": self.account_p12_password_source,
        }
        for vehicle in vehicles:
            status = self.get_vehicle_raw_status(vehicle)
            mileage = self._fetch_optional_read("mileage energy detail", self.get_mileage_energy_detail, vehicle)
            picture = self._fetch_optional_read("car picture", self.get_car_picture, vehicle)
            result["vehicles"][vehicle.vin] = normalize_vehicle(
                vehicle, status, self.user_id,
                mileage_json=mileage, picture_json=picture,
            )
        return result

    def _fetch_optional_read(self, label: str, fetcher: Any, vehicle: Vehicle) -> dict[str, Any] | None:
        try:
            return fetcher(vehicle)
        except LeapmotorApiError as exc:
            _LOGGER.debug("Leapmotor optional read failed for %s: %s", label, exc)
            return None

    # ------------------------------------------------------------------
    # Private — Remote control
    # ------------------------------------------------------------------

    def _remote_control(self, *, vin: str, action: str) -> dict[str, Any]:
        if not self.token:
            self.login()
        if not self.operation_password:
            raise LeapmotorAuthError(
                "No vehicle PIN configured. Read-only data works without a PIN, "
                "but remote-control actions require it."
            )
        if action not in REMOTE_ACTION_SPECS:
            raise LeapmotorApiError(f"Remote action not configured: {action}")

        vehicle = self._find_vehicle_by_vin(vin)
        spec = REMOTE_ACTION_SPECS[action]
        return self._remote_control_raw(
            vin=vehicle.vin,
            cmd_id=spec.cmd_id,
            cmd_content=spec.cmd_content,
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
                "No vehicle PIN configured. Read-only data works without a PIN, "
                "but remote-control actions require it."
            )
        if vehicle is None:
            vehicle = self._find_vehicle_by_vin(vin)

        operate_password = encrypt_operate_password(self.operation_password, self.token)
        self._ensure_remote_cert_sync()

        # Step 1: Verify operation password
        verify_headers = build_operpwd_verify_headers(
            sign_key=self.sign_key, device_id=self.device_id, vin=vin, operation_password=operate_password,
            language=self.language,
        )
        verify_headers.update(self._auth_headers(content_type="application/x-www-form-urlencoded"))
        verify_body = (
            f"operatePassword={quote(operate_password, safe='')}"
            f"&vin={quote(vin, safe='')}"
        )
        verify_response = self._post(
            path="/carownerservice/oversea/vehicle/v1/operPwd/verify",
            headers=verify_headers, data=verify_body, cert=self.account_cert,
        )
        _LOGGER.debug(
            "Leapmotor remote verify response for %s: HTTP %s %s",
            action_label, verify_response["status_code"], verify_response["body"],
        )
        self._parse_api_body(verify_response["status_code"], verify_response["body"], "remote verify")

        # Step 2: Execute remote command
        headers = build_remote_ctl_write_headers(
            sign_key=self.sign_key, device_id=self.device_id, vin=vin,
            cmd_content=cmd_content, cmd_id=cmd_id, operation_password=operate_password,
            language=self.language,
        )
        headers.update(self._auth_headers(content_type="application/x-www-form-urlencoded"))
        body = (
            f"cmdContent={quote(cmd_content, safe='')}"
            f"&vin={quote(vin, safe='')}"
            f"&cmdId={quote(cmd_id, safe='')}"
            f"&operatePassword={quote(operate_password, safe='')}"
        )
        response = self._post(
            path="/carownerservice/oversea/vehicle/v1/app/remote/ctl",
            headers=headers, data=body, cert=self.account_cert,
        )
        _LOGGER.debug(
            "Leapmotor remote ctl response for %s: HTTP %s %s",
            action_label, response["status_code"], response["body"],
        )
        result = self._parse_api_body(response["status_code"], response["body"], f"remote {action_label}")

        # Step 3: Poll for result
        remote_data = result.get("data") or {}
        remote_ctl_id = remote_data.get("remoteCtlId")
        if remote_ctl_id:
            self._poll_remote_control_result(
                vin=vehicle.vin, car_id=vehicle.car_id,
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
            sign_key=self.sign_key, device_id=self.device_id, vin=vin,
            cmd_content=cmd_content, cmd_id=cmd_id,
            language=self.language,
        )
        headers.update(self._auth_headers(content_type="application/x-www-form-urlencoded"))
        body = (
            f"cmdContent={quote(cmd_content, safe='')}"
            f"&vin={quote(vin, safe='')}"
            f"&cmdId={quote(cmd_id, safe='')}"
        )
        response = self._post(
            path="/carownerservice/oversea/vehicle/v1/app/remote/ctl",
            headers=headers, data=body, cert=self.account_cert,
        )
        _LOGGER.debug(
            "Leapmotor remote ctl response for %s: HTTP %s %s",
            action_label, response["status_code"], response["body"],
        )
        return self._parse_api_body(
            response["status_code"], response["body"], f"remote {action_label}",
        )

    def _ensure_remote_cert_sync(self) -> None:
        if self.remote_cert_synced:
            return
        headers = build_signed_headers(sign_key=self.sign_key, device_id=self.device_id, language=self.language)
        headers.update(self._auth_headers(content_type="application/x-www-form-urlencoded"))
        response = self._post(
            path="/carownerservice/oversea/vehicle/v1/cert/sync",
            headers=headers, data="",
            cert=(self.app_cert_path, self.app_key_path),
        )
        self._parse_api_body(response["status_code"], response["body"], "cert sync")
        self.remote_cert_synced = True

    def _poll_remote_control_result(
        self, *, vin: str, car_id: str | None,
        remote_ctl_id: str, timeout_ms: int, interval_ms: int,
    ) -> dict[str, Any]:
        del vin, car_id
        data = f"remoteCtlId={quote(remote_ctl_id, safe='')}"
        deadline = time.monotonic() + max(timeout_ms, 1000) / 1000.0
        last_result: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            headers = build_remote_ctl_result_headers(
                sign_key=self.sign_key, device_id=self.device_id, remote_ctl_id=remote_ctl_id,
                language=self.language,
            )
            headers.update(self._auth_headers(content_type="application/x-www-form-urlencoded"))
            response = self._post(
                path="/carownerservice/oversea/vehicle/v1/app/remote/ctl/result/query",
                headers=headers, data=data, cert=self.account_cert,
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
            name for name, path in [
                ("app_cert", self.app_cert_path),
                ("app_key", self.app_key_path),
            ]
            if not Path(path).exists()
        ]
        if missing:
            raise LeapmotorMissingAppCertError(
                "Missing local app certificate material: " + ", ".join(missing)
            )

    def _post(
        self, *, path: str, headers: dict[str, str],
        data: str, cert: tuple[str, str],
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

        return {
            "status_code": resp.status_code,
            "body": resp.text,
            "headers": dict(resp.headers),
        }

    def _post_binary(
        self, *, path: str, headers: dict[str, str],
        data: str, cert: tuple[str, str],
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
            "&policyId=20260204"
            "&loginMethod=1"
            f"&email={quote(self.username, safe='')}"
        )

    def _auth_headers(self, *, content_type: str) -> dict[str, str]:
        if not self.user_id or not self.token:
            raise LeapmotorAuthError("Not authenticated.")
        return {
            "Content-Type": content_type,
            "userId": self.user_id,
            "token": self.token,
        }

    def _parse_api_body(self, status_code: int, body: str, label: str) -> dict[str, Any]:
        try:
            data = json.loads(body)
        except ValueError as exc:
            self._record_api_result(label, status_code=status_code, code=None, message="non_json")
            raise LeapmotorApiError(f"{label} returned non-JSON response: {body[:200]}") from exc
        self._record_api_result(
            label, status_code=status_code,
            code=data.get("code"), message=data.get("message"),
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


# ---------------------------------------------------------------------------
# Data normalization (pure functions, no side effects)
# ---------------------------------------------------------------------------

def normalize_vehicle(
    vehicle: Vehicle,
    status_json: dict[str, Any],
    user_id: str | None,
    *,
    mileage_json: dict[str, Any] | None = None,
    picture_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize Leapmotor status payload into a structured dict."""
    status_data = status_json.get("data") or {}
    signal = status_data.get("signal") or {}
    config = status_data.get("config") or {}
    charge_plan = config.get("3") or {}
    mileage_data = (mileage_json or {}).get("data") or {}
    picture_data = (picture_json or {}).get("data") or {}
    vehicle_state = _derive_vehicle_state(signal)

    return {
        "vehicle": {
            "vin": vehicle.vin,
            "user_id": user_id,
            "car_id": vehicle.car_id,
            "car_type": vehicle.car_type,
            "nickname": vehicle.nickname,
            "is_shared": vehicle.is_shared,
            "year": vehicle.year,
            "rights": vehicle.rights,
            "abilities": vehicle.abilities or [],
            "module_rights": vehicle.module_rights,
        },
        "status": {
            "battery_percent": signal.get("1204"),
            "remaining_range_km": signal.get("3260"),
            "odometer_km": signal.get("1318"),
            "is_locked": _safe_int(signal.get("47")) == 0 if signal.get("47") is not None else None,
            "raw_lock_status_code": signal.get("47"),
            "is_parked": vehicle_state == "parked" if vehicle_state is not None else None,
            "vehicle_state": vehicle_state,
            "vehicle_state_source": "raw_signal",
            "raw_charge_status_code": signal.get("1939"),
            "raw_drive_status_code": signal.get("1941"),
            "raw_vehicle_state_code": signal.get("1944"),
            "raw_parked_status_code": signal.get("1298"),
            "interior_temp_c": signal.get("1349"),
            "climate_set_temp_left_c": signal.get("2183"),
            "climate_set_temp_right_c": signal.get("2184"),
            "last_vehicle_timestamp": signal.get("sts"),
        },
        "location": {
            "latitude": signal.get("3725", signal.get("2190")),
            "longitude": signal.get("3724", signal.get("2191")),
            "privacy_gps": status_data.get("privacyGPS"),
            "privacy_data": status_data.get("privacyData"),
            "last_vehicle_timestamp": signal.get("sts"),
        },
        "charging": {
            "is_charging": _is_charging(signal),
            "charge_limit_percent": charge_plan.get("percent"),
            "remaining_charge_minutes": _safe_int(signal.get("1200")),
            "charging_power_kw": _charging_power_kw(signal),
            "charging_current_a": _safe_float(signal.get("1178")),
            "charging_voltage_v": _safe_float(signal.get("1177")),
            "charging_planned_enabled": charge_plan.get("isEnable"),
            "charging_planned_start": charge_plan.get("beginTime"),
            "charging_planned_end": charge_plan.get("endTime"),
            "charging_planned_cycles": charge_plan.get("cycles"),
            "charging_planned_circulation": charge_plan.get("circulation"),
            "charging_plan_updated_at": charge_plan.get("updateTime"),
        },
        "history": {
            "total_mileage_km": mileage_data.get("totalmileage"),
            "total_mileage_mi": _safe_float(mileage_data.get("totalmileageMile")),
            "delivery_days": mileage_data.get("deliveryDays"),
        },
        "media": {
            "car_picture_status": "available" if picture_data.get("key") else "unavailable",
            "car_picture_url": picture_data.get("shareBindUrl"),
            "car_picture_key": picture_data.get("key"),
            "car_picture_whole": picture_data.get("whole"),
            "car_picture_key_present": bool(picture_data.get("key")),
            "car_picture_whole_present": bool(picture_data.get("whole")),
        },
        "diagnostics": {
            "tire_pressure_front_left_bar": _to_bar(signal.get("2667")),
            "tire_pressure_front_right_bar": _to_bar(signal.get("2653")),
            "tire_pressure_rear_left_bar": _to_bar(signal.get("2646")),
            "tire_pressure_rear_right_bar": _to_bar(signal.get("2660")),
            "raw_signal_1256": signal.get("1256"),
            "raw_signal_1257": signal.get("1257"),
            "raw_signal_1258": signal.get("1258"),
            "raw_signal_1277": signal.get("1277"),
            "raw_signal_1278": signal.get("1278"),
            "raw_signal_1279": signal.get("1279"),
            "raw_signal_1280": signal.get("1280"),
            "raw_signal_1281": signal.get("1281"),
            "raw_signal_1693": signal.get("1693"),
            "raw_signal_1694": signal.get("1694"),
            "raw_signal_1695": signal.get("1695"),
            "raw_signal_1696": signal.get("1696"),
        },
        "raw_updated_at": time.time(),
    }


def _safe_int(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _safe_float(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _to_bar(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return round(float(raw) / 100.0, 2)
    except (TypeError, ValueError):
        return None


def _derive_vehicle_state(signal: dict[str, Any]) -> str | None:
    """Return the movement state independent from charging state."""
    parked = _safe_int(signal.get("1298"))
    if parked == 1:
        return "parked"
    if parked == 0:
        return "driving"

    drive_status = _safe_int(signal.get("1941"))
    vehicle_state = _safe_int(signal.get("1944"))
    if drive_status in (1, 2, 4) or vehicle_state in (0, 1, 3):
        return "parked"
    if drive_status in (3, 5) or vehicle_state in (2, 4, 5):
        return "driving"

    return None


def _is_charging(signal: dict[str, Any]) -> bool:
    """Return whether the vehicle is currently charging."""
    remaining_charge_minutes = _safe_int(signal.get("1200"))
    charging_current_a = _safe_float(signal.get("1178"))
    if charging_current_a is not None and remaining_charge_minutes is not None:
        return abs(charging_current_a) >= 1.0

    charging_power_kw = _charging_power_kw(signal)
    if charging_power_kw is not None:
        return charging_power_kw >= 1.0 and remaining_charge_minutes is not None

    charge_status = _safe_int(signal.get("1939"))
    drive_status = _safe_int(signal.get("1941"))
    vehicle_state = _safe_int(signal.get("1944"))
    return charge_status in (1, 2, 3) and (
        remaining_charge_minutes is not None and (drive_status == 2 or vehicle_state == 0)
    )


def _charging_power_kw(signal: dict[str, Any]) -> float | None:
    """Return charging power derived from voltage and current signals."""
    current = _safe_float(signal.get("1178"))
    voltage = _safe_float(signal.get("1177"))
    if current is None or voltage is None:
        return None
    if abs(current) < 3.0:
        return None
    return round(abs(current * voltage) / 1000.0, 3)
