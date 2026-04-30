"""Leapmotor cryptographic operations.

Consolidates SM4, AES-CBC, HMAC-SHA256, HKDF and password/key derivation
from the original p12.py and api.py modules.

NOTE: MD5 and hardcoded keys are imposed by the Leapmotor protocol and cannot
be changed without server-side modifications.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import random
import time

from cryptography.hazmat.primitives import hashes, padding, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import pkcs12

from .const import (
    DEFAULT_APP_VERSION,
    DEFAULT_CHANNEL,
    DEFAULT_DEVICE_TYPE,
    DEFAULT_LANGUAGE,
    DEFAULT_OPERPWD_AES_IV,
    DEFAULT_OPERPWD_AES_KEY,
    DEFAULT_P12_ENC_ALG,
    DEFAULT_SOURCE,
)

# ---------------------------------------------------------------------------
# SM4 cipher tables (for PKCS#12 password derivation)
# ---------------------------------------------------------------------------

# fmt: off
_SM4_SBOX = (
    0xD6, 0x90, 0xE9, 0xFE, 0xCC, 0xE1, 0x3D, 0xB7, 0x16, 0xB6, 0x14, 0xC2, 0x28, 0xFB, 0x2C, 0x05,
    0x2B, 0x67, 0x9A, 0x76, 0x2A, 0xBE, 0x04, 0xC3, 0xAA, 0x44, 0x13, 0x26, 0x49, 0x86, 0x06, 0x99,
    0x9C, 0x42, 0x50, 0xF4, 0x91, 0xEF, 0x98, 0x7A, 0x33, 0x54, 0x0B, 0x43, 0xED, 0xCF, 0xAC, 0x62,
    0xE4, 0xB3, 0x1C, 0xA9, 0xC9, 0x08, 0xE8, 0x95, 0x80, 0xDF, 0x94, 0xFA, 0x75, 0x8F, 0x3F, 0xA6,
    0x47, 0x07, 0xA7, 0xFC, 0xF3, 0x73, 0x17, 0xBA, 0x83, 0x59, 0x3C, 0x19, 0xE6, 0x85, 0x4F, 0xA8,
    0x68, 0x6B, 0x81, 0xB2, 0x71, 0x64, 0xDA, 0x8B, 0xF8, 0xEB, 0x0F, 0x4B, 0x70, 0x56, 0x9D, 0x35,
    0x1E, 0x24, 0x0E, 0x5E, 0x63, 0x58, 0xD1, 0xA2, 0x25, 0x22, 0x7C, 0x3B, 0x01, 0x21, 0x78, 0x87,
    0xD4, 0x00, 0x46, 0x57, 0x9F, 0xD3, 0x27, 0x52, 0x4C, 0x36, 0x02, 0xE7, 0xA0, 0xC4, 0xC8, 0x9E,
    0xEA, 0xBF, 0x8A, 0xD2, 0x40, 0xC7, 0x38, 0xB5, 0xA3, 0xF7, 0xF2, 0xCE, 0xF9, 0x61, 0x15, 0xA1,
    0xE0, 0xAE, 0x5D, 0xA4, 0x9B, 0x34, 0x1A, 0x55, 0xAD, 0x93, 0x32, 0x30, 0xF5, 0x8C, 0xB1, 0xE3,
    0x1D, 0xF6, 0xE2, 0x2E, 0x82, 0x66, 0xCA, 0x60, 0xC0, 0x29, 0x23, 0xAB, 0x0D, 0x53, 0x4E, 0x6F,
    0xD5, 0xDB, 0x37, 0x45, 0xDE, 0xFD, 0x8E, 0x2F, 0x03, 0xFF, 0x6A, 0x72, 0x6D, 0x6C, 0x5B, 0x51,
    0x8D, 0x1B, 0xAF, 0x92, 0xBB, 0xDD, 0xBC, 0x7F, 0x11, 0xD9, 0x5C, 0x41, 0x1F, 0x10, 0x5A, 0xD8,
    0x0A, 0xC1, 0x31, 0x88, 0xA5, 0xCD, 0x7B, 0xBD, 0x2D, 0x74, 0xD0, 0x12, 0xB8, 0xE5, 0xB4, 0xB0,
    0x89, 0x69, 0x97, 0x4A, 0x0C, 0x96, 0x77, 0x7E, 0x65, 0xB9, 0xF1, 0x09, 0xC5, 0x6E, 0xC6, 0x84,
    0x18, 0xF0, 0x7D, 0xEC, 0x3A, 0xDC, 0x4D, 0x20, 0x79, 0xEE, 0x5F, 0x3E, 0xD7, 0xCB, 0x39, 0x48,
)

_P12_SM4_ROUND_KEYS = (
    0x818FA553, 0xEBA3318D, 0x5FC3C93A, 0xBD1DADD9,
    0xBB61CAB9, 0x000FD7EA, 0xDC6E0166, 0xDA937279,
    0x607EE786, 0xB548754C, 0x107330E4, 0xEA17C186,
    0x0F56F74B, 0xB21E443C, 0xE1210FE2, 0x009995C8,
    0xE7529A48, 0x6EF474F6, 0x2AB06DF6, 0x43B11BE8,
    0x359D4A14, 0xC29E2CDE, 0x30CF6A3E, 0x79D1C806,
    0x7C502387, 0xAAAB9BC6, 0xF0FE744B, 0x1CAFC872,
    0x95A9D075, 0x88070D58, 0x22800475, 0x8391938B,
)
# fmt: on


# ---------------------------------------------------------------------------
# SM4 cipher primitives
# ---------------------------------------------------------------------------


def _rotate_left(value: int, bits: int) -> int:
    return ((value << bits) & 0xFFFFFFFF) | (value >> (32 - bits))


def _sm4_encrypt_block(block: bytes) -> bytes:
    x0 = int.from_bytes(block[0:4], "big")
    x1 = int.from_bytes(block[4:8], "big")
    x2 = int.from_bytes(block[8:12], "big")
    x3 = int.from_bytes(block[12:16], "big")

    for round_key in _P12_SM4_ROUND_KEYS:
        t = x1 ^ x2 ^ x3 ^ round_key
        b = (
            (_SM4_SBOX[(t >> 24) & 0xFF] << 24)
            | (_SM4_SBOX[(t >> 16) & 0xFF] << 16)
            | (_SM4_SBOX[(t >> 8) & 0xFF] << 8)
            | _SM4_SBOX[t & 0xFF]
        )
        new_x = x0 ^ b ^ _rotate_left(b, 2) ^ _rotate_left(b, 10) ^ _rotate_left(b, 18) ^ _rotate_left(b, 24)
        x0, x1, x2, x3 = x1, x2, x3, new_x & 0xFFFFFFFF

    return b"".join(value.to_bytes(4, "big") for value in (x3, x2, x1, x0))


def _p12_memory_encode(data: bytes) -> bytes:
    pad_len = 16 - (len(data) % 16)
    padded = data + bytes([pad_len]) * pad_len
    return b"".join(_sm4_encrypt_block(padded[offset : offset + 16]) for offset in range(0, len(padded), 16))


# ---------------------------------------------------------------------------
# PKCS#12 password derivation
# ---------------------------------------------------------------------------


def derive_account_p12_password(account_id: str | int, uid: str) -> str:
    """Derive the account certificate password from login response fields."""
    cn = hashlib.md5(str(account_id).encode("ascii")).hexdigest()  # noqa: S324
    app_input = f"{cn}{cn[::2]}{uid[1::2]}".encode("ascii")
    digest = hashlib.sha256(app_input).digest()
    encoded = _p12_memory_encode(digest)
    return base64.b64encode(encoded[:12]).decode("ascii")[:15]


# ---------------------------------------------------------------------------
# PKCS#12 certificate loading
# ---------------------------------------------------------------------------


def load_account_cert_from_p12(
    p12_bytes: bytes,
    password: str,
) -> tuple[bytes, bytes]:
    """Load account certificate and private key from PKCS#12 binary.

    Returns:
        Tuple of (cert_pem_bytes, key_pem_bytes).

    Raises:
        ValueError: If the certificate or key cannot be extracted.
    """
    key, cert, _additional = pkcs12.load_key_and_certificates(
        p12_bytes,
        password.encode("utf-8"),
    )
    if key is None or cert is None:
        raise ValueError("PKCS#12 bundle does not contain a valid key/cert pair.")

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem


# ---------------------------------------------------------------------------
# AES-CBC encryption for operation password (vehicle PIN)
# ---------------------------------------------------------------------------


def derive_operpwd_key_iv(token: str | None) -> tuple[str, str]:
    """Derive AES key and IV from the session token for operatePassword encryption."""
    if not token or len(token) < 64:
        return DEFAULT_OPERPWD_AES_KEY, DEFAULT_OPERPWD_AES_IV
    key_source = token[:32]
    iv_source = token[32:64]
    key_text = hashlib.md5(key_source.encode("utf-8")).hexdigest()[8:24]  # noqa: S324
    iv_text = hashlib.md5(iv_source.encode("utf-8")).hexdigest()[8:24]  # noqa: S324
    return key_text, iv_text


def encrypt_operate_password(pin: str, token: str | None) -> str:
    """Encrypt the vehicle PIN using AES-128-CBC with token-derived key/IV."""
    key_text, iv_text = derive_operpwd_key_iv(token)
    padder = padding.PKCS7(128).padder()
    padded = padder.update(pin.encode("utf-8")) + padder.finalize()
    cipher = Cipher(
        algorithms.AES(key_text.encode("utf-8")),
        modes.CBC(iv_text.encode("utf-8")),
    )
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode("ascii")


# ---------------------------------------------------------------------------
# HKDF signing key derivation
# ---------------------------------------------------------------------------


def derive_sign_key(ikm: str, salt: str, info: str) -> bytes:
    """Derive the 32-byte HMAC signing key using HKDF-SHA256."""
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.encode("utf-8"),
        info=info.encode("utf-8"),
    ).derive(ikm.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT device ID extraction
# ---------------------------------------------------------------------------


def derive_session_device_id(token: str | None, fallback_device_id: str) -> str:
    """Extract the session deviceId from the JWT payload."""
    if not token:
        return fallback_device_id
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")))
        user_name = str(payload.get("user_name") or "")
        parts = user_name.split(",")
        if len(parts) >= 4 and parts[2]:
            return parts[2]
    except Exception:  # noqa: BLE001, S110
        pass
    return fallback_device_id


# ---------------------------------------------------------------------------
# Request header builders
# ---------------------------------------------------------------------------


def build_login_headers(
    *,
    device_id: str,
    username: str,
    password: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, str]:
    """Build headers for the login request with SHA256 signature."""
    nonce = str(random.randint(100000, 9999999))  # noqa: S311
    timestamp = str(int(time.time() * 1000))
    sign_input = "".join(
        [
            language,
            DEFAULT_DEVICE_TYPE,
            device_id,
            "1",
            username,
            "0",
            "1",
            nonce,
            password,
            "20260204",
            DEFAULT_SOURCE,
            timestamp,
            DEFAULT_APP_VERSION,
        ]
    )
    return {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "acceptLanguage": language,
        "channel": DEFAULT_CHANNEL,
        "deviceType": DEFAULT_DEVICE_TYPE,
        "X-P12_ENC_ALG": DEFAULT_P12_ENC_ALG,
        "source": DEFAULT_SOURCE,
        "version": DEFAULT_APP_VERSION,
        "nonce": nonce,
        "deviceId": device_id,
        "timestamp": timestamp,
        "sign": hashlib.sha256(sign_input.encode("utf-8")).hexdigest(),
    }


def build_signed_headers(
    *,
    sign_key: bytes,
    device_id: str,
    vin: str | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, str]:
    """Build HMAC-SHA256 signed headers for authenticated requests."""
    nonce = str(random.randint(100000, 9999999))  # noqa: S311
    timestamp = str(int(time.time() * 1000))
    sign_input_parts = [
        language,
        DEFAULT_CHANNEL,
        device_id,
        DEFAULT_DEVICE_TYPE,
        nonce,
        DEFAULT_SOURCE,
        timestamp,
        DEFAULT_APP_VERSION,
    ]
    if vin:
        sign_input_parts.append(vin)
    sign_input = "".join(sign_input_parts)
    return {
        "acceptLanguage": language,
        "channel": DEFAULT_CHANNEL,
        "deviceType": DEFAULT_DEVICE_TYPE,
        "X-P12_ENC_ALG": DEFAULT_P12_ENC_ALG,
        "source": DEFAULT_SOURCE,
        "version": DEFAULT_APP_VERSION,
        "nonce": nonce,
        "deviceId": device_id,
        "timestamp": timestamp,
        "sign": hmac.new(sign_key, sign_input.encode("utf-8"), hashlib.sha256).hexdigest(),
    }


def build_car_picture_headers(
    *,
    sign_key: bytes,
    device_id: str,
    vin: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, str]:
    """Build the signature variant used by vehicle/v1/carpicture/key."""
    nonce = str(random.randint(100000, 9999999))  # noqa: S311
    timestamp = str(int(time.time() * 1000))
    sign_input = (
        f"{language}"
        f"{DEFAULT_CHANNEL}"
        f"{device_id}"
        f"{device_id}"
        f"{DEFAULT_DEVICE_TYPE}"
        f"{nonce}"
        f"{DEFAULT_SOURCE}"
        f"{timestamp}"
        f"{DEFAULT_APP_VERSION}"
        f"{vin}"
    )
    return {
        "acceptLanguage": language,
        "channel": DEFAULT_CHANNEL,
        "deviceType": DEFAULT_DEVICE_TYPE,
        "X-P12_ENC_ALG": DEFAULT_P12_ENC_ALG,
        "source": DEFAULT_SOURCE,
        "version": DEFAULT_APP_VERSION,
        "nonce": nonce,
        "deviceId": device_id,
        "timestamp": timestamp,
        "sign": hmac.new(sign_key, sign_input.encode("utf-8"), hashlib.sha256).hexdigest(),
    }


def build_car_picture_package_headers(
    *,
    sign_key: bytes,
    device_id: str,
    picture_key: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, str]:
    """Build the signature variant used by vehicle/v1/carpicture/package."""
    nonce = str(random.randint(100000, 9999999))  # noqa: S311
    timestamp = str(int(time.time() * 1000))
    sign_input = (
        f"{language}"
        f"{DEFAULT_CHANNEL}"
        f"{device_id}"
        f"{DEFAULT_DEVICE_TYPE}"
        f"{picture_key}"
        f"{nonce}"
        f"{DEFAULT_SOURCE}"
        f"{timestamp}"
        f"{DEFAULT_APP_VERSION}"
    )
    return {
        "acceptLanguage": language,
        "channel": DEFAULT_CHANNEL,
        "deviceType": DEFAULT_DEVICE_TYPE,
        "source": DEFAULT_SOURCE,
        "version": DEFAULT_APP_VERSION,
        "nonce": nonce,
        "deviceId": device_id,
        "timestamp": timestamp,
        "sign": hmac.new(sign_key, sign_input.encode("utf-8"), hashlib.sha256).hexdigest(),
    }


def build_operpwd_verify_headers(
    *,
    sign_key: bytes,
    device_id: str,
    vin: str,
    operation_password: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, str]:
    """Build headers for operatePassword verify request."""
    nonce = str(random.randint(100000, 9999999))  # noqa: S311
    timestamp = str(int(time.time() * 1000))
    sign_input = (
        f"{language}"
        f"{DEFAULT_CHANNEL}"
        f"{device_id}"
        f"{DEFAULT_DEVICE_TYPE}"
        f"{nonce}"
        f"{operation_password}"
        f"{DEFAULT_SOURCE}"
        f"{timestamp}"
        f"{DEFAULT_APP_VERSION}"
        f"{vin}"
    )
    return {
        "acceptLanguage": language,
        "channel": DEFAULT_CHANNEL,
        "deviceType": DEFAULT_DEVICE_TYPE,
        "X-P12_ENC_ALG": DEFAULT_P12_ENC_ALG,
        "source": DEFAULT_SOURCE,
        "version": DEFAULT_APP_VERSION,
        "nonce": nonce,
        "deviceId": device_id,
        "timestamp": timestamp,
        "sign": hmac.new(sign_key, sign_input.encode("utf-8"), hashlib.sha256).hexdigest(),
    }


def build_remote_ctl_write_headers(
    *,
    sign_key: bytes,
    device_id: str,
    vin: str,
    cmd_content: str,
    cmd_id: str,
    operation_password: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, str]:
    """Build headers for the remote control write request."""
    nonce = str(random.randint(100000, 9999999))  # noqa: S311
    timestamp = str(int(time.time() * 1000))
    sign_input = (
        f"{language}"
        f"{DEFAULT_CHANNEL}"
        f"{cmd_content}"
        f"{cmd_id}"
        f"{device_id}"
        f"{DEFAULT_DEVICE_TYPE}"
        f"{nonce}"
        f"{operation_password}"
        f"{DEFAULT_SOURCE}"
        f"{timestamp}"
        f"{DEFAULT_APP_VERSION}"
        f"{vin}"
    )
    return {
        "acceptLanguage": language,
        "channel": DEFAULT_CHANNEL,
        "deviceType": DEFAULT_DEVICE_TYPE,
        "X-P12_ENC_ALG": DEFAULT_P12_ENC_ALG,
        "source": DEFAULT_SOURCE,
        "version": DEFAULT_APP_VERSION,
        "nonce": nonce,
        "deviceId": device_id,
        "timestamp": timestamp,
        "sign": hmac.new(sign_key, sign_input.encode("utf-8"), hashlib.sha256).hexdigest(),
    }


def build_remote_ctl_write_headers_without_pin(
    *,
    sign_key: bytes,
    device_id: str,
    vin: str,
    cmd_content: str,
    cmd_id: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, str]:
    """Build headers for remote control write requests that do not require a PIN."""
    nonce = str(random.randint(100000, 9999999))  # noqa: S311
    timestamp = str(int(time.time() * 1000))
    sign_input = (
        f"{language}"
        f"{DEFAULT_CHANNEL}"
        f"{cmd_content}"
        f"{cmd_id}"
        f"{device_id}"
        f"{DEFAULT_DEVICE_TYPE}"
        f"{nonce}"
        f"{DEFAULT_SOURCE}"
        f"{timestamp}"
        f"{DEFAULT_APP_VERSION}"
        f"{vin}"
    )
    return {
        "acceptLanguage": language,
        "channel": DEFAULT_CHANNEL,
        "deviceType": DEFAULT_DEVICE_TYPE,
        "X-P12_ENC_ALG": DEFAULT_P12_ENC_ALG,
        "source": DEFAULT_SOURCE,
        "version": DEFAULT_APP_VERSION,
        "nonce": nonce,
        "deviceId": device_id,
        "timestamp": timestamp,
        "sign": hmac.new(sign_key, sign_input.encode("utf-8"), hashlib.sha256).hexdigest(),
    }


def build_remote_ctl_result_headers(
    *,
    sign_key: bytes,
    device_id: str,
    remote_ctl_id: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, str]:
    """Build headers for the remote control result query."""
    nonce = str(random.randint(100000, 9999999))  # noqa: S311
    timestamp = str(int(time.time() * 1000))
    sign_input = (
        f"{language}"
        f"{DEFAULT_CHANNEL}"
        f"{device_id}"
        f"{DEFAULT_DEVICE_TYPE}"
        f"{nonce}"
        f"{remote_ctl_id}"
        f"{DEFAULT_SOURCE}"
        f"{timestamp}"
        f"{DEFAULT_APP_VERSION}"
    )
    return {
        "acceptLanguage": language,
        "channel": DEFAULT_CHANNEL,
        "deviceType": DEFAULT_DEVICE_TYPE,
        "X-P12_ENC_ALG": DEFAULT_P12_ENC_ALG,
        "source": DEFAULT_SOURCE,
        "version": DEFAULT_APP_VERSION,
        "nonce": nonce,
        "deviceId": device_id,
        "timestamp": timestamp,
        "sign": hmac.new(sign_key, sign_input.encode("utf-8"), hashlib.sha256).hexdigest(),
    }
