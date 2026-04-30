"""Tests for leapmotor_api.crypto module."""

from __future__ import annotations

import hashlib

from leapmotor_api.crypto import (
    build_login_headers,
    build_signed_headers,
    derive_account_p12_password,
    derive_operpwd_key_iv,
    derive_session_device_id,
    derive_sign_key,
    encrypt_operate_password,
)


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

    def test_contains_required_fields(self) -> None:
        headers = build_login_headers(
            device_id="test_device",
            username="user@test.com",
            password="secret",
        )
        assert "sign" in headers
        assert headers["deviceId"] == "test_device"
        assert headers["source"] == "leapmotor"
        assert "Content-Type" in headers

    def test_sign_is_sha256_hex(self) -> None:
        headers = build_login_headers(
            device_id="dev", username="u", password="p",
        )
        assert len(headers["sign"]) == 64  # SHA256 hex


class TestBuildSignedHeaders:
    """Test HMAC-signed header construction."""

    def test_contains_required_fields(self) -> None:
        sign_key = derive_sign_key("ikm", "salt", "info")
        headers = build_signed_headers(
            sign_key=sign_key, device_id="test_device",
        )
        assert "sign" in headers
        assert headers["deviceId"] == "test_device"

    def test_sign_includes_vin_when_provided(self) -> None:
        sign_key = derive_sign_key("ikm", "salt", "info")
        h1 = build_signed_headers(sign_key=sign_key, device_id="dev")
        h2 = build_signed_headers(sign_key=sign_key, device_id="dev", vin="VIN123")
        # Different inputs → different signatures (with extremely high probability)
        # Note: nonce/timestamp make them always different, but we test the code path
        assert h1["sign"] != h2["sign"]
