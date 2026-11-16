"""Tests for leapmotor_api.client module."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qsl

import pytest
import requests

from leapmotor_api.client import (
    LeapmotorApiClient,
    _vehicle_status_car_type_path,
)
from leapmotor_api.exceptions import (
    LeapmotorApiError,
    LeapmotorAuthError,
    LeapmotorMissingAppCertError,
    LeapmotorPermissionError,
)
from leapmotor_api.hemisphere import HemisphereGuard
from leapmotor_api.models import (
    CarType,
    ConsumptionBreakdown,
    MessageList,
    MileageEnergyHistory,
    ShareInvitation,
    SoftwareInfo,
    SoftwarePackage,
    SoftwareVersion,
    Vehicle,
)

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
            client.login()
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
# Car-type path mapping
# ---------------------------------------------------------------------------


class TestVehicleStatusCarTypePath:
    def test_b10_maps_to_c10(self) -> None:
        assert _vehicle_status_car_type_path("B10") == "c10"
        assert _vehicle_status_car_type_path("b10") == "c10"

    def test_b11_maps_to_c10(self) -> None:
        assert _vehicle_status_car_type_path("B11") == "c10"
        assert _vehicle_status_car_type_path("b11") == "c10"

    def test_b05_maps_to_c10(self) -> None:
        # /status/get/b05 is answered with "No message available" (HTTP 404);
        # the C10 segment returns the full signal set for a B05.
        assert _vehicle_status_car_type_path("B05") == "c10"
        assert _vehicle_status_car_type_path("b05") == "c10"

    def test_c10_unchanged(self) -> None:
        assert _vehicle_status_car_type_path("C10") == "c10"

    def test_other_types_lowered(self) -> None:
        assert _vehicle_status_car_type_path("T03") == "t03"
        assert _vehicle_status_car_type_path("C11") == "c11"

    def test_unknown_type_lowered(self) -> None:
        assert _vehicle_status_car_type_path(" X99 ") == "x99"

    def test_matches_car_type_status_path(self) -> None:
        for member in CarType:
            assert _vehicle_status_car_type_path(member.value.upper()) == member.status_path


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
            client._auth_headers()
        client.close()

    def test_returns_headers_when_authenticated(self) -> None:
        client = _make_client()
        client.user_id = "123"
        client.token = "abc"
        headers = client._auth_headers()
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
        vehicle = Vehicle(
            vin="VIN1",
            car_type="C10",
            email=None,
            plate_number=None,
            car_id="1",
            user_nickname="N",
            vehicle_nickname="N",
            is_shared=False,
        )
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


# ---------------------------------------------------------------------------
# Client — Message endpoints
# ---------------------------------------------------------------------------


class TestMessageEndpoints:
    def _setup_auth(self, client: LeapmotorApiClient) -> None:
        client.token = "tok"
        client.user_id = "uid"
        client.sign_ikm = "ikm"
        client.sign_salt = "salt"
        client.sign_info = "info"
        client.account_cert_file = "/tmp/cert.pem"
        client.account_key_file = "/tmp/key.pem"

    def test_get_message_list(self) -> None:
        client = _make_client()
        self._setup_auth(client)
        api_response = {
            "status_code": 200,
            "body": json.dumps(
                {
                    "code": 0,
                    "data": {
                        "count": 1,
                        "list": [{"id": 100, "vin": "VIN1", "title": "Test", "readFlag": 0, "msgType": 14}],
                    },
                }
            ),
        }
        with patch.object(client, "_post", return_value=api_response):
            result = client.get_message_list(page_no=1, page_size=5)
        assert isinstance(result, MessageList)
        assert result.count == 1
        assert len(result.messages) == 1
        assert result.messages[0].id == 100
        assert result.messages[0].vin == "VIN1"
        assert result.messages[0].is_read is False
        client.close()

    def test_get_message_list_empty(self) -> None:
        client = _make_client()
        self._setup_auth(client)
        api_response = {
            "status_code": 200,
            "body": json.dumps({"code": 0, "data": {"count": 0, "list": []}}),
        }
        with patch.object(client, "_post", return_value=api_response):
            result = client.get_message_list()
        assert result.count == 0
        assert result.messages == []
        client.close()

    def test_get_unread_message_count(self) -> None:
        client = _make_client()
        self._setup_auth(client)
        api_response = {
            "status_code": 200,
            "body": json.dumps({"code": 0, "data": {"unread": 3}}),
        }
        with patch.object(client, "_post", return_value=api_response):
            result = client.get_unread_message_count()
        assert result == 3
        client.close()

    def test_get_unread_message_count_zero(self) -> None:
        client = _make_client()
        self._setup_auth(client)
        api_response = {
            "status_code": 200,
            "body": json.dumps({"code": 0, "data": {"unread": 0}}),
        }
        with patch.object(client, "_post", return_value=api_response):
            result = client.get_unread_message_count()
        assert result == 0
        client.close()


# ---------------------------------------------------------------------------
# Client — vehicle status C10 fallback
# ---------------------------------------------------------------------------

_STATUS_OK = {"status_code": 200, "body": json.dumps({"code": 0, "data": {"signal": {}}})}
_STATUS_404 = {
    "status_code": 404,
    "body": json.dumps({"status": 404, "error": "Not Found", "message": "No message available"}),
}


class TestVehicleStatusC10Fallback:
    def _client(self) -> LeapmotorApiClient:
        client = _make_client()
        client.token = "tok"
        client.user_id = "uid"
        client.sign_ikm = "ikm"
        client.sign_salt = "salt"
        client.sign_info = "info"
        client.account_cert_file = "/tmp/cert.pem"
        client.account_key_file = "/tmp/key.pem"
        return client

    def _vehicle(self, car_type: str) -> Vehicle:
        return Vehicle(
            vin="VIN1",
            car_type=car_type,
            email=None,
            plate_number=None,
            car_id="1",
            user_nickname="N",
            vehicle_nickname="N",
            is_shared=False,
        )

    @staticmethod
    def _paths(post: Any) -> list[str]:
        return [call.kwargs["path"].rsplit("/", 1)[-1] for call in post.call_args_list]

    def test_retries_on_c10_after_404(self) -> None:
        client = self._client()
        with patch.object(client, "_post", side_effect=[_STATUS_404, _STATUS_OK]) as post:
            result = client.get_vehicle_raw_status(self._vehicle("X99"))
        assert result["code"] == 0
        assert self._paths(post) == ["x99", "c10"]
        client.close()

    def test_records_both_attempts(self) -> None:
        client = self._client()
        with patch.object(client, "_post", side_effect=[_STATUS_404, _STATUS_OK]):
            client.get_vehicle_raw_status(self._vehicle("X99"))
        assert client.last_api_results["vehicle status"]["http_status"] == 404
        assert client.last_api_results["vehicle status"]["message"] == "No message available"
        assert client.last_api_results["vehicle status c10 fallback"]["http_status"] == 200
        assert client.last_api_results["vehicle status c10 fallback"]["code"] == 0
        client.close()

    def test_remembers_c10_after_successful_fallback(self) -> None:
        client = self._client()
        with patch.object(client, "_post", side_effect=[_STATUS_404, _STATUS_OK, _STATUS_OK]) as post:
            client.get_vehicle_raw_status(self._vehicle("X99"))
            client.get_vehicle_raw_status(self._vehicle("X99"))
        assert self._paths(post) == ["x99", "c10", "c10"]
        client.close()

    def test_warns_once_per_model(self, caplog: pytest.LogCaptureFixture) -> None:
        client = self._client()
        with (
            caplog.at_level(logging.WARNING, logger="leapmotor_api.client"),
            patch.object(client, "_post", side_effect=[_STATUS_404, _STATUS_OK, _STATUS_OK]),
        ):
            client.get_vehicle_raw_status(self._vehicle("X99"))
            client.get_vehicle_raw_status(self._vehicle("X99"))
        warnings = [r for r in caplog.records if "answered 404" in r.getMessage()]
        assert len(warnings) == 1
        assert "X99" in warnings[0].getMessage()
        client.close()

    def test_does_not_remember_failed_fallback(self) -> None:
        client = self._client()
        with (
            patch.object(client, "_post", return_value=_STATUS_404),
            pytest.raises(LeapmotorApiError, match="No message available"),
        ):
            client.get_vehicle_raw_status(self._vehicle("X99"))
        with patch.object(client, "_post", side_effect=[_STATUS_404, _STATUS_OK]) as post:
            client.get_vehicle_raw_status(self._vehicle("X99"))
        assert self._paths(post) == ["x99", "c10"]
        client.close()

    def test_no_retry_when_already_c10(self) -> None:
        client = self._client()
        with (
            patch.object(client, "_post", return_value=_STATUS_404) as post,
            pytest.raises(LeapmotorApiError, match="No message available"),
        ):
            client.get_vehicle_raw_status(self._vehicle("B05"))
        assert self._paths(post) == ["c10"]
        client.close()

    def test_no_retry_on_other_errors(self) -> None:
        client = self._client()
        error = {"status_code": 200, "body": json.dumps({"code": 500, "message": "Server busy"})}
        with (
            patch.object(client, "_post", return_value=error) as post,
            pytest.raises(LeapmotorApiError, match="Server busy"),
        ):
            client.get_vehicle_raw_status(self._vehicle("X99"))
        assert self._paths(post) == ["x99"]
        client.close()

    def test_raises_when_c10_also_fails(self) -> None:
        client = self._client()
        with (
            patch.object(client, "_post", return_value=_STATUS_404) as post,
            pytest.raises(LeapmotorApiError) as exc_info,
        ):
            client.get_vehicle_raw_status(self._vehicle("X99"))
        assert self._paths(post) == ["x99", "c10"]
        message = str(exc_info.value)
        assert "No message available" in message
        assert "'x99' (HTTP 404) and 'c10'" in message
        client.close()


class TestVehicleStatusHemisphere:
    """``get_vehicle_status`` keeps the coordinate sign across polls (issue #17)."""

    def _vehicle(self) -> Vehicle:
        return Vehicle(
            vin="VIN1",
            car_type="C10",
            email=None,
            plate_number=None,
            car_id="1",
            user_nickname="N",
            vehicle_nickname="N",
            is_shared=False,
        )

    def test_restores_sign_when_signed_pair_is_missing(self) -> None:
        client = _make_client()
        frames = [
            {"data": {"signal": {"2": -9.14, "3": 38.72, "3724": 9.14, "3725": 38.72}}},
            {"data": {"signal": {"3724": 9.14, "3725": 38.72}}},
        ]
        with patch.object(client, "_get_vehicle_raw_status", side_effect=frames):
            first = client._get_vehicle_status(self._vehicle())
            second = client._get_vehicle_status(self._vehicle())
        assert first.location.longitude == -9.14
        assert second.location.longitude == -9.14
        client.close()

    def test_accepts_saved_guard(self) -> None:
        guard = HemisphereGuard({"VIN1": {"longitude": {"sign": -1, "last": -9.14}}})
        client = _make_client(hemisphere_guard=guard)
        assert client.hemisphere_guard is guard
        with patch.object(
            client, "_get_vehicle_raw_status", return_value={"data": {"signal": {"3724": 9.14, "3725": 38.72}}}
        ):
            status = client._get_vehicle_status(self._vehicle())
        assert status.location.longitude == -9.14
        client.close()


# ---------------------------------------------------------------------------
# set_charge_limit — schedule preservation (issue #18)
# ---------------------------------------------------------------------------


class TestSetChargeLimit:
    """set_charge_limit() must change only chargesoc, never reset the plan."""

    @staticmethod
    def _capture_cmd_content(client: LeapmotorApiClient, schedule: dict[str, Any]) -> dict[str, Any]:
        """Run set_charge_limit with a mocked schedule and return the sent payload."""
        captured: dict[str, Any] = {}

        def fake_remote_control(*, vin: str, action: str, cmd_content: str, **_: Any) -> dict[str, Any]:
            captured["cmd_content"] = json.loads(cmd_content)
            return {"code": 0}

        with (
            patch.object(client, "get_charge_schedule", return_value=schedule),
            patch.object(client, "_remote_control", side_effect=fake_remote_control),
        ):
            client.set_charge_limit("VIN123", 80)
        return captured["cmd_content"]

    def test_enabled_partial_schedule_preserves_starttime(self) -> None:
        """Regression for #18: an active start-time-only plan omits cycles/endtime.

        The cloud returns only the populated fields, so guarding on `cycles`
        used to route this into the all-defaults branch — resetting starttime
        to 00:00 and disabling the schedule. Only chargesoc must change.
        """
        client = _make_client()
        # Real live response captured for an enabled 10:00 plan.
        schedule = {"chargeEnable": 1, "chargesoc": 100, "circulation": 0, "starttime": "10:00"}
        sent = self._capture_cmd_content(client, schedule)

        assert sent["starttime"] == "10:00"  # preserved, NOT reset to 00:00
        assert sent["chargeEnable"] == 1  # preserved, NOT disabled
        assert sent["chargesoc"] == 80  # the only intended change
        client.close()

    def test_full_schedule_preserved(self) -> None:
        client = _make_client()
        schedule = {
            "chargeEnable": 1,
            "chargesoc": 100,
            "circulation": 1,
            "cycles": "1,0,1,0,1,0,1",
            "endtime": "07:30",
            "recharge": 1,
            "starttime": "23:00",
        }
        sent = self._capture_cmd_content(client, schedule)

        assert sent["starttime"] == "23:00"
        assert sent["endtime"] == "07:30"
        assert sent["cycles"] == "1,0,1,0,1,0,1"
        assert sent["circulation"] == 1
        assert sent["recharge"] == 1
        assert sent["chargeEnable"] == 1
        assert sent["chargesoc"] == 80
        client.close()

    def test_no_schedule_uses_disabled_defaults(self) -> None:
        client = _make_client()
        sent = self._capture_cmd_content(client, {})

        assert sent["chargeEnable"] == 0
        assert sent["chargesoc"] == 80
        assert sent["starttime"] == "00:00"
        client.close()


# ---------------------------------------------------------------------------
# Car sharing — invitations (recipient side)
# ---------------------------------------------------------------------------


class TestShareInvitationEndpoints:
    INVITATION: dict[str, Any] = {
        "msgid": 1790348570370,
        "shareUserid": "123456",
        "carCode": "LFZTEST0000000001",
        "carId": "159533",
        "nickName": "Owner",
        "carType": "B10",
        "rightList": None,
        "type": 1,
        "moduleRights": "100,200,300,400",
        "shareTime": 1790348570370,
        "durationType": 0,
    }

    def _setup_auth(self, client: LeapmotorApiClient) -> None:
        client.token = "tok"
        client.user_id = "uid"
        client.sign_ikm = "ikm"
        client.sign_salt = "salt"
        client.sign_info = "info"
        client.account_cert_file = "/tmp/cert.pem"
        client.account_key_file = "/tmp/key.pem"

    def test_get_share_invitations(self) -> None:
        client = _make_client()
        self._setup_auth(client)
        api_response = {
            "status_code": 200,
            "body": json.dumps({"result": 0, "code": 0, "data": [self.INVITATION]}),
        }
        with patch.object(client, "_post", return_value=api_response) as post:
            result = client.get_share_invitations()
        assert post.call_args.kwargs["path"] == "/carownerservice/oversea/sharecar/getsharemsg"
        assert post.call_args.kwargs["data"] == ""
        assert len(result) == 1
        assert isinstance(result[0], ShareInvitation)
        assert result[0].vin == "LFZTEST0000000001"
        assert result[0].share_user_id == "123456"
        assert result[0].car_type == "B10"
        client.close()

    def test_get_share_invitations_empty(self) -> None:
        client = _make_client()
        self._setup_auth(client)
        api_response = {"status_code": 200, "body": json.dumps({"result": 0, "code": 0, "data": []})}
        with patch.object(client, "_post", return_value=api_response):
            assert client.get_share_invitations() == []
        client.close()

    def _answer(self, method: str) -> dict[str, Any]:
        """Run accept/reject with a mocked _post and return the request it sent."""
        client = _make_client()
        self._setup_auth(client)
        invitation = ShareInvitation.from_dict(self.INVITATION)
        api_response = {"status_code": 200, "body": json.dumps({"result": 0, "code": 0, "data": None})}
        with patch.object(client, "_post", return_value=api_response) as post:
            result = getattr(client, method)(invitation)
        client.close()
        assert result == {"result": 0, "code": 0, "data": None}
        sent = dict(post.call_args.kwargs)
        sent["form"] = dict(parse_qsl(sent["data"]))
        return sent

    def test_accept_share_invitation_sends_yes(self) -> None:
        sent = self._answer("accept_share_invitation")
        assert sent["path"] == "/carownerservice/oversea/sharecar/setokmsg"
        assert sent["form"] == {
            "shareUserId": "123456",
            "userId": "uid",
            "carCode": "LFZTEST0000000001",
            "state": "yes",
        }
        assert sent["headers"]["userId"] == "uid"
        assert sent["headers"]["token"] == "tok"
        assert "sign" in sent["headers"]

    def test_reject_share_invitation_sends_no(self) -> None:
        sent = self._answer("reject_share_invitation")
        assert sent["path"] == "/carownerservice/oversea/sharecar/setokmsg"
        assert sent["form"]["state"] == "no"

    def test_answer_refuses_an_incomplete_invitation_locally(self) -> None:
        client = _make_client()
        self._setup_auth(client)
        invitation = ShareInvitation.from_dict({**self.INVITATION, "carCode": None})
        with patch.object(client, "_post") as post:
            with pytest.raises(ValueError, match="owner id or VIN"):
                client.accept_share_invitation(invitation)
        post.assert_not_called()
        client.close()

    def test_answer_failure_raises(self) -> None:
        client = _make_client()
        self._setup_auth(client)
        invitation = ShareInvitation.from_dict(self.INVITATION)
        api_response = {"status_code": 200, "body": json.dumps({"code": -1, "message": "No such permission"})}
        with patch.object(client, "_post", return_value=api_response):
            with pytest.raises(LeapmotorApiError, match="No such permission"):
                client.accept_share_invitation(invitation)
        client.close()


class TestWindowedStatisticsEndpoints:
    VEHICLE = Vehicle(
        vin="VIN1",
        car_type="B10",
        email=None,
        plate_number=None,
        car_id="1",
        user_nickname="N",
        vehicle_nickname="N",
        is_shared=False,
    )
    START = datetime(2026, 8, 29, tzinfo=UTC)
    END = datetime(2026, 8, 30, 23, 59, 59, tzinfo=UTC)

    def _setup_auth(self, client: LeapmotorApiClient) -> None:
        client.token = "tok"
        client.user_id = "uid"
        client.sign_ikm = "ikm"
        client.sign_salt = "salt"
        client.sign_info = "info"
        client.account_cert_file = "/tmp/cert.pem"
        client.account_key_file = "/tmp/key.pem"

    @staticmethod
    def _sign(client: LeapmotorApiClient, *fields: str) -> str:
        return hmac.new(client.sign_key, "".join(fields).encode("utf-8"), hashlib.sha256).hexdigest()

    def test_get_mileage_energy_history(self) -> None:
        client = _make_client()
        self._setup_auth(client)
        data = {
            "totalmileage": 12084,
            "totalmileageMile": "7508.6",
            "deliveryDays": 210,
            "totalEnergy": "2154.3",
            "totalAccumulatedMileage": 84,
            "totalAccumulatedMileageMile": "52.2",
            "detail": [
                {
                    "day": "2026-08-29",
                    "xDay": 1787961600000,
                    "currentMileage": 12010,
                    "accumulatedMileage": 10,
                    "accumulatedMileageMile": "6.2",
                    "accumulatedEnergyConsume": 2,
                },
                {"day": "2026-08-30", "accumulatedMileage": 74},
            ],
        }
        api_response = {"status_code": 200, "body": json.dumps({"result": 0, "code": 0, "data": data})}
        with patch.object(client, "_post", return_value=api_response) as post:
            result = client.get_mileage_energy_history(self.VEHICLE, start=self.START, end=self.END)
        sent = post.call_args.kwargs
        h = sent["headers"]
        assert sent["path"] == "/carownerservice/oversea/drivingRecord/v1/mileage/energy/detail"
        assert dict(parse_qsl(sent["data"])) == {
            "begintime": "1787961600000",
            "endtime": "1788134399000",
            "vin": "VIN1",
        }
        # Window in milliseconds and part of the signature (field order as in leapmotor-ha).
        assert h["sign"] == self._sign(
            client, h["acceptLanguage"], "1787961600000", h["channel"], h["deviceId"], h["deviceType"],
            "1788134399000", h["nonce"], h["source"], h["timestamp"], h["version"], "VIN1",
        )  # fmt: skip
        assert isinstance(result, MileageEnergyHistory)
        assert result.total_energy_kwh == 2154.3
        assert result.total_mileage_km == 12084.0
        assert result.delivery_days == 210
        assert result.window_mileage_km == 84.0
        assert [d.day for d in result.days] == ["2026-08-29", "2026-08-30"]
        assert result.days[0].energy_kwh == 2.0
        assert result.days[1].energy_kwh is None
        client.close()

    def test_get_consumption_breakdown(self) -> None:
        client = _make_client()
        self._setup_auth(client)
        api_response = {
            "status_code": 200,
            "body": json.dumps({"result": 0, "code": 0, "data": {"driverEC": "9.4", "acEC": "0.3", "otherEC": "0.1"}}),
        }
        with patch.object(client, "_post", return_value=api_response) as post:
            result = client.get_consumption_breakdown(self.VEHICLE, start=self.START, end=self.END)
        sent = post.call_args.kwargs
        h = sent["headers"]
        assert sent["path"] == "/carownerservice/oversea/drivingRecord/v1/getLastweekEC"
        assert dict(parse_qsl(sent["data"])) == {"begintime": "1787961600", "endtime": "1788134399", "carvin": "VIN1"}
        assert h["sign"] == self._sign(
            client, h["acceptLanguage"], "1787961600", "VIN1", h["channel"], h["deviceId"], h["deviceType"],
            "1788134399", h["nonce"], h["source"], h["timestamp"], h["version"],
        )  # fmt: skip
        assert result == ConsumptionBreakdown(driver_ec=9.4, ac_ec=0.3, other_ec=0.1)
        assert "consumption breakdown" in client.last_api_results
        client.close()

    def test_last_week_breakdown_uses_previous_week_and_legacy_label(self) -> None:
        client = _make_client()
        self._setup_auth(client)
        api_response = {"status_code": 200, "body": json.dumps({"result": 0, "code": 0, "data": {"driverEC": "1"}})}
        with (
            patch("leapmotor_api.client.previous_week_window_seconds", return_value=(1787961600, 1788566399)),
            patch.object(client, "_post", return_value=api_response) as post,
        ):
            result = client.get_consumption_last_week_breakdown(self.VEHICLE)
        assert dict(parse_qsl(post.call_args.kwargs["data"]))["begintime"] == "1787961600"
        assert dict(parse_qsl(post.call_args.kwargs["data"]))["endtime"] == "1788566399"
        assert result.driver_ec == 1.0
        assert "consumption last week breakdown" in client.last_api_results
        client.close()

    @pytest.mark.parametrize(
        ("start", "end"),
        [
            (datetime(2026, 8, 29), datetime(2026, 8, 30)),  # noqa: DTZ001
            (datetime(2026, 8, 30, tzinfo=UTC), datetime(2026, 8, 29, tzinfo=UTC)),
        ],
    )
    @pytest.mark.parametrize("method", ["get_mileage_energy_history", "get_consumption_breakdown"])
    def test_rejects_invalid_window(self, method: str, start: datetime, end: datetime) -> None:
        client = _make_client()
        with patch.object(client, "_post") as post, pytest.raises(ValueError):
            getattr(client, method)(self.VEHICLE, start=start, end=end)
        post.assert_not_called()
        client.close()


class TestSoftwareInfo:
    VEHICLE = TestWindowedStatisticsEndpoints.VEHICLE

    def _client(self) -> LeapmotorApiClient:
        client = _make_client()
        TestWindowedStatisticsEndpoints()._setup_auth(client)
        return client

    def test_get_software_info(self) -> None:
        client = self._client()
        data = {"currentVersion": {"generalVersion": "0.00.00"}, "newVersion": {"generalVersion": "1.03.12"}}
        api_response = {"status_code": 200, "body": json.dumps({"result": 0, "code": 0, "data": data})}
        with patch.object(client, "_post", return_value=api_response) as post:
            result = client.get_software_info(self.VEHICLE)
        sent = post.call_args.kwargs
        h = sent["headers"]
        assert sent["path"] == "/carownerservice/oversea/hotspot/fetch"
        assert sent["data"] == "vin=VIN1"
        assert h["sign"] == TestWindowedStatisticsEndpoints._sign(
            client, h["acceptLanguage"], h["channel"], h["deviceId"], h["deviceType"],
            h["nonce"], h["source"], h["timestamp"], h["version"], "VIN1",
        )  # fmt: skip
        assert isinstance(result, SoftwareInfo)
        assert result.update_available is True
        assert result.new_version is not None
        assert result.new_version.version == "1.03.12"
        assert client.last_api_results["software info"]["code"] == 0
        client.close()

    def test_shared_account_raises_permission_error(self) -> None:
        client = self._client()
        body = {"code": 40, "result": 40, "message": "No such permission", "data": None}
        api_response = {"status_code": 200, "body": json.dumps(body)}
        with (
            patch.object(client, "_post", return_value=api_response),
            pytest.raises(LeapmotorPermissionError, match="owns the car"),
        ):
            client.get_software_info(self.VEHICLE)
        client.close()

    def test_other_errors_stay_generic(self) -> None:
        client = self._client()
        api_response = {"status_code": 200, "body": json.dumps({"code": 500, "message": "boom"})}
        with patch.object(client, "_post", return_value=api_response), pytest.raises(LeapmotorApiError) as exc_info:
            client.get_software_info(self.VEHICLE)
        assert not isinstance(exc_info.value, LeapmotorPermissionError)
        client.close()


class _FakeCdnResponse:
    def __init__(self, status: int, body: bytes = b"", headers: dict[str, str] | None = None, fail_after: int = -1):
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self._fail_after = fail_after

    def __enter__(self) -> _FakeCdnResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def iter_content(self, chunk_size: int = 1) -> Any:
        for i in range(0, len(self._body), chunk_size):
            if 0 <= self._fail_after <= i:
                raise requests.ConnectionError("boom https://ota-cdn.example/f?Signature=SECRET")
            yield self._body[i : i + chunk_size]


class _FakeCdnSession:
    """Stands in for ``requests.Session`` in the client module: replays responses, records requests."""

    def __init__(self, *responses: _FakeCdnResponse | Exception):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def __call__(self) -> _FakeCdnSession:
        return self

    def __enter__(self) -> _FakeCdnSession:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get(self, url: str, **kwargs: Any) -> _FakeCdnResponse:
        self.calls.append({"url": url, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class TestDownloadSoftwarePackage:
    NAME = "LP-VCU020-AD_V1.01.16_R_20260114.bin"
    BODY = bytes(range(256)) * 4

    def _package(
        self, *, expires: int = 4102444800, size: int | None = None, url: str | None = None
    ) -> SoftwarePackage:
        return SoftwarePackage.from_dict(
            {
                "fileName": self.NAME,
                "fileSize": len(self.BODY) if size is None else size,
                "downloadURL": url
                or f"https://ota-cdn.example/p/{self.NAME}.encrypt?Expires={expires}&Signature=SECRET&Key-Pair-Id=K",
            }
        )

    def _download(
        self, tmp_path: Path, cdn: _FakeCdnSession, package: SoftwarePackage | None = None, **kw: Any
    ) -> Path:
        client = _make_client(verify_ssl=False)
        try:
            with (
                patch("leapmotor_api.client.requests.Session", cdn),
                patch.object(client.session, "get") as api_get,
                patch.object(client.session, "post") as api_post,
            ):
                return client.download_software_package(package or self._package(), tmp_path, chunk_size=100, **kw)
        finally:
            api_get.assert_not_called()
            api_post.assert_not_called()
            client.close()

    def test_fresh_download(self, tmp_path: Path) -> None:
        cdn = _FakeCdnSession(_FakeCdnResponse(200, self.BODY, {"Content-Length": str(len(self.BODY))}))
        seen: list[tuple[int, int | None]] = []
        result = self._download(tmp_path, cdn, progress=lambda done, total: seen.append((done, total)))
        assert result == tmp_path / f"{self.NAME}.encrypt"
        assert result.read_bytes() == self.BODY
        assert not (tmp_path / f"{self.NAME}.encrypt.part").exists()
        call = cdn.calls[0]
        # Plain CDN request: TLS verified even with verify_ssl=False, no client cert, no Leapmotor auth.
        assert call["verify"] is True
        assert "cert" not in call
        assert call["headers"] == {"Accept-Encoding": "identity"}
        assert call["stream"] is True
        assert [done for done, _ in seen] == sorted({done for done, _ in seen})
        assert seen[-1] == (len(self.BODY), len(self.BODY))

    def test_destination_file_path(self, tmp_path: Path) -> None:
        cdn = _FakeCdnSession(_FakeCdnResponse(200, self.BODY))
        client = _make_client()
        with patch("leapmotor_api.client.requests.Session", cdn):
            result = client.download_software_package(self._package(), tmp_path / "custom.bin")
        client.close()
        assert result == tmp_path / "custom.bin"
        assert result.read_bytes() == self.BODY

    def test_resume_with_206(self, tmp_path: Path) -> None:
        (tmp_path / f"{self.NAME}.encrypt.part").write_bytes(self.BODY[:300])
        rest = self.BODY[300:]
        cdn = _FakeCdnSession(
            _FakeCdnResponse(206, rest, {"Content-Range": f"bytes 300-{len(self.BODY) - 1}/{len(self.BODY)}"})
        )
        result = self._download(tmp_path, cdn)
        assert cdn.calls[0]["headers"]["Range"] == "bytes=300-"
        assert result.read_bytes() == self.BODY

    def test_server_ignoring_range_restarts(self, tmp_path: Path) -> None:
        (tmp_path / f"{self.NAME}.encrypt.part").write_bytes(b"garbage")
        cdn = _FakeCdnSession(_FakeCdnResponse(200, self.BODY, {"Content-Length": str(len(self.BODY))}))
        assert self._download(tmp_path, cdn).read_bytes() == self.BODY

    def test_416_with_complete_part_renames(self, tmp_path: Path) -> None:
        (tmp_path / f"{self.NAME}.encrypt.part").write_bytes(self.BODY)
        cdn = _FakeCdnSession(_FakeCdnResponse(416, headers={"Content-Range": f"bytes */{len(self.BODY)}"}))
        assert self._download(tmp_path, cdn).read_bytes() == self.BODY
        assert len(cdn.calls) == 1

    def test_416_with_mismatching_part_restarts_once(self, tmp_path: Path) -> None:
        (tmp_path / f"{self.NAME}.encrypt.part").write_bytes(self.BODY + b"extra")
        cdn = _FakeCdnSession(
            _FakeCdnResponse(416, headers={"Content-Range": f"bytes */{len(self.BODY)}"}),
            _FakeCdnResponse(200, self.BODY, {"Content-Length": str(len(self.BODY))}),
        )
        assert self._download(tmp_path, cdn).read_bytes() == self.BODY
        assert "Range" not in cdn.calls[1]["headers"]

    def test_resume_false_discards_part(self, tmp_path: Path) -> None:
        (tmp_path / f"{self.NAME}.encrypt.part").write_bytes(self.BODY[:300])
        cdn = _FakeCdnSession(_FakeCdnResponse(200, self.BODY))
        assert self._download(tmp_path, cdn, resume=False).read_bytes() == self.BODY
        assert "Range" not in cdn.calls[0]["headers"]

    def test_403_has_no_secret(self, tmp_path: Path) -> None:
        cdn = _FakeCdnSession(_FakeCdnResponse(403))
        with pytest.raises(LeapmotorApiError, match="get_software_info") as exc_info:
            self._download(tmp_path, cdn)
        assert "SECRET" not in str(exc_info.value)
        assert "ota-cdn" not in str(exc_info.value)

    def test_other_status(self, tmp_path: Path) -> None:
        with pytest.raises(LeapmotorApiError, match="HTTP 500"):
            self._download(tmp_path, _FakeCdnSession(_FakeCdnResponse(500)))

    def test_expired_link_makes_no_request(self, tmp_path: Path) -> None:
        cdn = _FakeCdnSession()
        expired = int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())
        with pytest.raises(LeapmotorApiError, match="expired"):
            self._download(tmp_path, cdn, self._package(expires=expired))
        assert cdn.calls == []

    def test_incomplete_download_keeps_part(self, tmp_path: Path) -> None:
        cdn = _FakeCdnSession(_FakeCdnResponse(200, self.BODY[:500], {"Content-Length": str(len(self.BODY))}))
        with pytest.raises(LeapmotorApiError, match="incomplete"):
            self._download(tmp_path, cdn)
        assert (tmp_path / f"{self.NAME}.encrypt.part").read_bytes() == self.BODY[:500]
        assert not (tmp_path / f"{self.NAME}.encrypt").exists()

    def test_network_error_has_no_secret_and_keeps_part(self, tmp_path: Path) -> None:
        cdn = _FakeCdnSession(_FakeCdnResponse(200, self.BODY, fail_after=300))
        with pytest.raises(LeapmotorApiError, match="ConnectionError") as exc_info:
            self._download(tmp_path, cdn)
        assert "SECRET" not in str(exc_info.value)
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__suppress_context__ is True
        assert (tmp_path / f"{self.NAME}.encrypt.part").read_bytes() == self.BODY[:300]

    def test_progress_exception_propagates_and_resume_completes(self, tmp_path: Path) -> None:
        class StopDownloadError(Exception):
            pass

        def stop_halfway(done: int, total: int | None) -> None:
            if done >= 500:
                raise StopDownloadError

        first = _FakeCdnSession(_FakeCdnResponse(200, self.BODY, {"Content-Length": str(len(self.BODY))}))
        with pytest.raises(StopDownloadError):
            self._download(tmp_path, first, progress=stop_halfway)
        part = tmp_path / f"{self.NAME}.encrypt.part"
        assert part.stat().st_size == 500
        second = _FakeCdnSession(
            _FakeCdnResponse(
                206, self.BODY[500:], {"Content-Range": f"bytes 500-{len(self.BODY) - 1}/{len(self.BODY)}"}
            )
        )
        assert self._download(tmp_path, second).read_bytes() == self.BODY
        assert second.calls[0]["headers"]["Range"] == "bytes=500-"

    def test_size_differing_from_file_size_warns(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        cdn = _FakeCdnSession(_FakeCdnResponse(200, self.BODY))
        with caplog.at_level(logging.WARNING, logger="leapmotor_api.client"):
            self._download(tmp_path, cdn, self._package(size=1))
        assert "declares 1" in caplog.text
        assert "SECRET" not in caplog.text

    def test_missing_link(self, tmp_path: Path) -> None:
        package = SoftwarePackage.from_dict({"fileName": self.NAME})
        with pytest.raises(ValueError, match="no download link"):
            self._download(tmp_path, _FakeCdnSession(), package)

    def test_unsafe_name_into_directory(self, tmp_path: Path) -> None:
        package = SoftwarePackage.from_dict({"fileName": "../evil.bin", "downloadURL": "https://ota-cdn.example/a/.."})
        with pytest.raises(ValueError, match="file name"):
            self._download(tmp_path, _FakeCdnSession(), package)


class TestDownloadSoftwareUpdate:
    def _version(self) -> SoftwareVersion:
        def item(name: str, size: int) -> dict[str, Any]:
            return {"fileName": name, "fileSize": size, "downloadURL": f"https://ota-cdn.example/p/{name}.encrypt"}

        return SoftwareVersion.from_dict(
            {"generalVersion": "1.03.12", "updateItemList": [item("a.bin", 3), item("b.bin", 2)]}
        )

    def test_downloads_all_and_skips_complete(self, tmp_path: Path) -> None:
        (tmp_path / "a.bin.encrypt").write_bytes(b"AAA")
        cdn = _FakeCdnSession(_FakeCdnResponse(200, b"BB", {"Content-Length": "2"}))
        seen: list[tuple[str | None, int, int | None]] = []
        client = _make_client()
        with patch("leapmotor_api.client.requests.Session", cdn):
            files = client.download_software_update(
                self._version(), tmp_path, progress=lambda p, done, total: seen.append((p.file_name, done, total))
            )
        client.close()
        assert files == [tmp_path / "a.bin.encrypt", tmp_path / "b.bin.encrypt"]
        assert (tmp_path / "b.bin.encrypt").read_bytes() == b"BB"
        assert len(cdn.calls) == 1
        assert seen == [("a.bin", 3, 3), ("b.bin", 2, 2)]

    def test_directory_must_exist(self, tmp_path: Path) -> None:
        client = _make_client()
        with pytest.raises(ValueError, match="existing directory"):
            client.download_software_update(self._version(), tmp_path / "missing")
        client.close()


# ---------------------------------------------------------------------------
# ac_off — per-model payload (issue #9)
# ---------------------------------------------------------------------------


class TestAcOff:
    """ac_off() must send operate=off in the shape each model executes."""

    @staticmethod
    def _sent_cmd_content(car_type: str) -> dict[str, Any]:
        client = _make_client(operation_password="1234")
        client.token = "tok"
        vehicle = Vehicle(
            vin="VIN1",
            car_type=car_type,
            email=None,
            plate_number=None,
            car_id="1",
            user_nickname="N",
            vehicle_nickname="N",
            is_shared=False,
        )
        with (
            patch.object(client, "_find_vehicle_by_vin", return_value=vehicle),
            patch.object(client, "_remote_control_raw", return_value={"code": 0}) as raw,
        ):
            client.ac_off("VIN1")
        client.close()
        assert raw.call_args.kwargs["cmd_id"] == "170"
        return json.loads(raw.call_args.kwargs["cmd_content"])

    @pytest.mark.parametrize("car_type", ["B10", "C10", "B05"])
    def test_bare_operate_off(self, car_type: str) -> None:
        assert self._sent_cmd_content(car_type) == {"operate": "off"}

    @pytest.mark.parametrize("car_type", ["T03", "t03", " T03 "])
    def test_t03_full_body_with_operate_off(self, car_type: str) -> None:
        assert self._sent_cmd_content(car_type) == {
            "circle": "out",
            "mode": "wind",
            "operate": "off",
            "position": "all",
            "temperature": "26",
            "windlevel": "3",
            "wshld": "0",
        }


# ---------------------------------------------------------------------------
# Charging history
# ---------------------------------------------------------------------------


def _charge_item(start_ts: int, charge_type: str = "SLOW", energy: float = 1.0) -> dict[str, Any]:
    return {
        "chargeGunStartTs": start_ts,
        "chargeGunEndTs": start_ts + 60_000,
        "chargeEarliestTs": start_ts,
        "chargeLatestTs": start_ts + 60_000,
        "chargeType": charge_type,
        "chargeInEnergy": energy,
        "chargeStartLongitude": "7.0",
        "chargeStartLatitude": "51.0",
        "zone": "UTC+2",
    }


def _charge_response(items: list[dict[str, Any]], total: int, page_num: int, page_size: int) -> dict[str, Any]:
    # The cloud reports totalPage=0 even when there are several pages.
    data = {"pageNum": page_num, "pageSize": page_size, "totalPage": 0, "total": total, "list": items}
    return {"status_code": 200, "body": json.dumps({"code": 0, "result": 0, "data": data})}


class TestChargingHistory:
    def _client(self) -> LeapmotorApiClient:
        client = _make_client()
        TestWindowedStatisticsEndpoints()._setup_auth(client)
        return client

    def test_get_all_charging_records_pages_despite_total_page_zero(self) -> None:
        client = self._client()
        page1 = [_charge_item(1_000_000 + i) for i in range(3)]
        page2 = [_charge_item(2_000_000)]
        responses = [_charge_response(page1, 4, 1, 3), _charge_response(page2, 4, 2, 3)]
        with patch.object(client, "_post_json", side_effect=responses) as post:
            records = client.get_all_charging_records(
                "VIN1", start_time=date(2026, 1, 1), end_time=date(2026, 10, 19), page_size=3
            )
        assert len(records) == 4
        assert [c.kwargs["json_body"]["pageNum"] for c in post.call_args_list] == [1, 2]
        client.close()

    def test_get_all_charging_records_stops_on_empty_page(self) -> None:
        client = self._client()
        page1 = [_charge_item(1_000_000 + i) for i in range(2)]
        responses = [_charge_response(page1, 0, 1, 2), _charge_response([], 0, 2, 2)]
        with patch.object(client, "_post_json", side_effect=responses) as post:
            records = client.get_all_charging_records(
                "VIN1", start_time=date(2026, 1, 1), end_time=date(2026, 10, 19), page_size=2
            )
        assert len(records) == 2
        assert post.call_count == 2
        client.close()

    def test_page_exposes_total(self) -> None:
        client = self._client()
        with patch.object(client, "_post_json", return_value=_charge_response([_charge_item(1)], 56, 1, 50)):
            page = client.get_charging_daily_detail("VIN1", start_time=date(2026, 1, 1), end_time=date(2026, 10, 19))
        assert page.total == 56
        assert page.total_page == 0
        client.close()

    def test_empty_history_on_shared_vehicle_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        client = self._client()
        client._shared_vins = {"VIN1"}
        with (
            patch.object(client, "_post_json", return_value=_charge_response([], 0, 1, 10)),
            caplog.at_level(logging.WARNING, logger="leapmotor_api.client"),
        ):
            client.get_charging_daily_detail("VIN1", start_time=date(2026, 1, 1), end_time=date(2026, 10, 19))
        assert "is_shared=True" in caplog.text
        assert "owner account" in caplog.text
        client.close()

    def test_empty_history_on_owned_vehicle_does_not_warn(self, caplog: pytest.LogCaptureFixture) -> None:
        client = self._client()
        with (
            patch.object(client, "_post_json", return_value=_charge_response([], 0, 1, 10)),
            caplog.at_level(logging.WARNING, logger="leapmotor_api.client"),
        ):
            client.get_charging_daily_detail("VIN1", start_time=date(2026, 1, 1), end_time=date(2026, 10, 19))
        assert "is_shared" not in caplog.text
        client.close()

    def test_vehicle_list_remembers_shared_vins(self) -> None:
        client = self._client()
        data = {"bindcars": [{"vin": "OWN1", "carType": "B10"}], "sharedcars": [{"vin": "SHR1", "carType": "B10"}]}
        api_response = {"status_code": 200, "body": json.dumps({"code": 0, "result": 0, "data": data})}
        with patch.object(client, "_post", return_value=api_response):
            client.get_vehicle_list()
        assert client._shared_vins == {"SHR1"}
        client.close()
