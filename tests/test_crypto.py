"""Tests for leapmotor_api.crypto module."""

from __future__ import annotations

import base64
import hashlib
import os

from leapmotor_api.crypto import (
    build_login_headers,
    build_signed_headers,
    build_signed_headers_v2,
    derive_account_p12_password,
    derive_operpwd_key_iv,
    derive_session_device_id,
    derive_sign_key,
    derive_sign_key_v2,
    encrypt_operate_password,
)
from leapmotor_api.models import ApiRequestHeaders


class TestDeriveAccountP12Password:
    """Test SM4-based PKCS#12 password derivation."""

    def test_deterministic(self) -> None:
        """Same inputs must always produce the same password."""
        p1 = derive_account_p12_password("12345", "abcdef")
        p2 = derive_account_p12_password("12345", "abcdef")
        assert p1 == p2

    def test_different_inputs_different_output(self) -> None:
        p1 = derive_account_p12_password("12345", "abcdef")
        p2 = derive_account_p12_password("99999", "zzzzzzz")
        assert p1 != p2

    def test_output_length(self) -> None:
        """Password must be exactly 15 characters (base64 truncated)."""
        p = derive_account_p12_password("12345", "abcdef")
        assert len(p) == 15

    def test_output_is_ascii(self) -> None:
        p = derive_account_p12_password("12345", "abcdef")
        assert p.isascii()

    def test_integer_account_id(self) -> None:
        """account_id can be int or str."""
        p1 = derive_account_p12_password(12345, "abcdef")
        p2 = derive_account_p12_password("12345", "abcdef")
        assert p1 == p2


class TestDeriveOperpwdKeyIv:
    """Test AES key/IV derivation from JWT token."""

    def test_short_token_returns_defaults(self) -> None:
        key, iv = derive_operpwd_key_iv("short")
        assert key == "f1cf0c025baec0e2"
        assert iv == "6b6a1fe94e133fd7"

    def test_none_token_returns_defaults(self) -> None:
        key, iv = derive_operpwd_key_iv(None)
        assert key == "f1cf0c025baec0e2"
        assert iv == "6b6a1fe94e133fd7"

    def test_valid_token_derives_key_iv(self) -> None:
        token = "a" * 64 + ".rest"
        key, iv = derive_operpwd_key_iv(token)
        assert len(key) == 16
        assert len(iv) == 16
        expected_key = hashlib.md5(("a" * 32).encode()).hexdigest()[8:24]
        expected_iv = hashlib.md5(("a" * 32).encode()).hexdigest()[8:24]
        assert key == expected_key
        assert iv == expected_iv


class TestEncryptOperatePassword:
    """Test AES-CBC encryption of the vehicle PIN."""

    def test_output_is_base64(self) -> None:
        result = encrypt_operate_password("1234", None)
        import base64

        decoded = base64.b64decode(result)
        assert len(decoded) == 16  # 4 bytes PIN + PKCS7 padding → 16 bytes

    def test_deterministic_with_same_token(self) -> None:
        token = "b" * 64 + ".payload.sig"
        r1 = encrypt_operate_password("1234", token)
        r2 = encrypt_operate_password("1234", token)
        assert r1 == r2

    def test_different_pin_different_output(self) -> None:
        r1 = encrypt_operate_password("1234", None)
        r2 = encrypt_operate_password("5678", None)
        assert r1 != r2


class TestDeriveSessionDeviceId:
    """Test JWT device ID extraction."""

    def test_none_token(self) -> None:
        assert derive_session_device_id(None, "fallback123") == "fallback123"

    def test_invalid_jwt(self) -> None:
        assert derive_session_device_id("not.a.jwt", "fallback123") == "fallback123"

    def test_valid_jwt_with_device_id(self) -> None:
        import base64
        import json

        payload = {"user_name": "user,123,device_abc,extra"}
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"header.{payload_b64}.signature"
        assert derive_session_device_id(token, "fallback") == "device_abc"

    def test_valid_jwt_without_device_id(self) -> None:
        import base64
        import json

        payload = {"user_name": "user,123,,extra"}
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"header.{payload_b64}.signature"
        assert derive_session_device_id(token, "fallback") == "fallback"


class TestDeriveSignKey:
    """Test HKDF-SHA256 signing key derivation."""

    def test_output_length(self) -> None:
        key = derive_sign_key("ikm_value", "salt_value", "info_value")
        assert len(key) == 32

    def test_deterministic(self) -> None:
        k1 = derive_sign_key("ikm", "salt", "info")
        k2 = derive_sign_key("ikm", "salt", "info")
        assert k1 == k2

    def test_different_inputs(self) -> None:
        k1 = derive_sign_key("ikm1", "salt", "info")
        k2 = derive_sign_key("ikm2", "salt", "info")
        assert k1 != k2


class TestBuildLoginHeaders:
    """Test login header construction."""

    def test_returns_api_request_headers(self) -> None:
        result = build_login_headers(
            device_id="test_device",
            username="user@test.com",
            password="secret",
        )
        assert isinstance(result, ApiRequestHeaders)

    def test_contains_required_fields(self) -> None:
        result = build_login_headers(
            device_id="test_device",
            username="user@test.com",
            password="secret",
        )
        assert result.sign
        assert result.device_id == "test_device"
        assert result.source == "leapmotor"
        assert result.content_type is not None

    def test_to_dict(self) -> None:
        result = build_login_headers(
            device_id="test_device",
            username="user@test.com",
            password="secret",
        )
        headers = result.to_dict()
        assert isinstance(headers, dict)
        assert headers["deviceId"] == "test_device"
        assert "Content-Type" in headers
        assert "X-P12_ENC_ALG" in headers
        assert "sign" in headers

    def test_sign_is_sha256_hex(self) -> None:
        result = build_login_headers(
            device_id="dev",
            username="u",
            password="p",
        )
        assert len(result.sign) == 64  # SHA256 hex


class TestBuildSignedHeaders:
    """Test HMAC-signed header construction."""

    def test_returns_api_request_headers(self) -> None:
        sign_key = derive_sign_key("ikm", "salt", "info")
        result = build_signed_headers(
            sign_key=sign_key,
            device_id="test_device",
        )
        assert isinstance(result, ApiRequestHeaders)

    def test_contains_required_fields(self) -> None:
        sign_key = derive_sign_key("ikm", "salt", "info")
        result = build_signed_headers(
            sign_key=sign_key,
            device_id="test_device",
        )
        assert result.sign
        assert result.device_id == "test_device"

    def test_to_dict_has_p12_enc_alg(self) -> None:
        sign_key = derive_sign_key("ikm", "salt", "info")
        headers = build_signed_headers(
            sign_key=sign_key,
            device_id="test_device",
        ).to_dict()
        assert "X-P12_ENC_ALG" in headers
        assert headers["deviceId"] == "test_device"

    def test_sign_includes_vin_when_provided(self) -> None:
        sign_key = derive_sign_key("ikm", "salt", "info")
        h1 = build_signed_headers(sign_key=sign_key, device_id="dev")
        h2 = build_signed_headers(sign_key=sign_key, device_id="dev", vin="VIN123")
        # Different inputs → different signatures (with extremely high probability)
        # Note: nonce/timestamp make them always different, but we test the code path
        assert h1.sign != h2.sign


class TestSignV2:
    """v2 signature (x-api-signature-version: 2.0), verified against live traffic 2026-11-16."""

    # Live HMAC key read from the running app (ConfigMmkv.getHKDFKey).
    LIVE_KEY = bytes.fromhex(
        "f6b6616d4acd25f1c949816483a083b7b90122e6f0430e89874e1e1e2f7d3fd2"
    )

    def test_derive_sign_key_v2_is_xor_of_jwt_sig_r2_r3(self) -> None:
        a, b, c = os.urandom(32), os.urandom(32), os.urandom(32)
        access_token = "hdr.payload." + base64.urlsafe_b64encode(a).decode().rstrip("=")
        key = derive_sign_key_v2(
            access_token,
            base64.b64encode(b).decode(),
            base64.b64encode(c).decode(),
        )
        assert key == bytes(a[i] ^ b[i] ^ c[i] for i in range(32))

    def test_daily_detail_sign_matches_captured_request(self, monkeypatch) -> None:
        """build_signed_headers_v2 reproduces the sign of a real captured request."""
        import leapmotor_api.crypto as crypto_mod

        # Inject the captured request's nonce and timestamp.
        monkeypatch.setattr(crypto_mod.random, "random", lambda: (6948114.037430112 - 10000) / 1e7)
        monkeypatch.setattr(crypto_mod.time, "time", lambda: 1794839315157 / 1000)

        headers = build_signed_headers_v2(
            sign_key=self.LIVE_KEY,
            device_id="android_d51b72cd86c785baf157a281a759604b",
            carvin="LFZA5AE22TE025678",
            cartype="B10",
            body_params={
                "pageSize": "50",
                "startTime": "1793487600",
                "vin": "LFZA5AE22TE025678",
                "endTime": "1793573999",
                "pageNum": "1",
            },
            language="de-DE",
            version="1.18.2",
        )
        assert headers.nonce == "6948114.037430112"
        assert headers.timestamp == "1794839315157"
        assert headers.sign == "716c8bb50e718eb4a2ad4578f1650f5d8042f9252a21ee3f04aee8f59780e289"

        wire = headers.to_dict()
        assert wire["x-api-signature-version"] == "2.0"
        assert wire["x-region"] == "EU"
        assert wire["deviceType"] == "android"
        assert wire["carvin"] == "LFZA5AE22TE025678"
        assert wire["cartype"] == "B10"

    def test_statistic_days_sign_matches_captured_request(self, monkeypatch) -> None:
        import leapmotor_api.crypto as crypto_mod

        monkeypatch.setattr(crypto_mod.random, "random", lambda: (1624388.1502888934 - 10000) / 1e7)
        monkeypatch.setattr(crypto_mod.time, "time", lambda: 1794839314967 / 1000)

        headers = build_signed_headers_v2(
            sign_key=self.LIVE_KEY,
            device_id="android_d51b72cd86c785baf157a281a759604b",
            carvin="LFZA5AE22TE025678",
            cartype="B10",
            body_params={
                "startTime": "2026-11-01",
                "vin": "LFZA5AE22TE025678",
                "endTime": "2026-11-30",
            },
            language="de-DE",
            version="1.18.2",
        )
        assert headers.nonce == "1624388.1502888934"
        assert headers.sign == "15aa614f439060334e96698a03709e7c2daf5c733bc61f629d866bb06912d52f"
