"""Tests for leapmotor_api.client module."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qsl

import pytest

from leapmotor_api.client import (
    LeapmotorApiClient,
    _vehicle_status_car_type_path,
)
from leapmotor_api.exceptions import (
    LeapmotorApiError,
    LeapmotorAuthError,
    LeapmotorMissingAppCertError,
)
from leapmotor_api.hemisphere import HemisphereGuard
from leapmotor_api.models import CarType, MessageList, ShareInvitation, Vehicle

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
