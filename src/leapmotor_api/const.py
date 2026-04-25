"""Leapmotor API constants."""

from __future__ import annotations

from .models import RemoteActionSpec

DEFAULT_BASE_URL = "https://appgateway.leapmotor-international.de"
DEFAULT_APP_VERSION = "1.12.3"
DEFAULT_SOURCE = "leapmotor"
DEFAULT_CHANNEL = "1"
DEFAULT_LANGUAGE = "en-GB"
DEFAULT_DEVICE_TYPE = "1"
DEFAULT_P12_ENC_ALG = "1"

DEFAULT_OPERPWD_AES_KEY = "f1cf0c025baec0e2"
DEFAULT_OPERPWD_AES_IV = "6b6a1fe94e133fd7"

# Known fallback passwords for account PKCS#12 certificate.
KNOWN_ACCOUNT_P12_PASSWORDS: tuple[str, ...] = ()

# Remote-control action identifiers.
REMOTE_CTL_LOCK = "lock"
REMOTE_CTL_UNLOCK = "unlock"
REMOTE_CTL_TRUNK = "trunk"
REMOTE_CTL_TRUNK_OPEN = "trunk_open"
REMOTE_CTL_TRUNK_CLOSE = "trunk_close"
REMOTE_CTL_FIND_CAR = "find_car"
REMOTE_CTL_SUNSHADE = "sunshade"
REMOTE_CTL_SUNSHADE_OPEN = "sunshade_open"
REMOTE_CTL_SUNSHADE_CLOSE = "sunshade_close"
REMOTE_CTL_BATTERY_PREHEAT = "battery_preheat"
REMOTE_CTL_WINDOWS = "windows"
REMOTE_CTL_WINDOWS_OPEN = "windows_open"
REMOTE_CTL_WINDOWS_CLOSE = "windows_close"
REMOTE_CTL_AC_SWITCH = "ac_switch"
REMOTE_CTL_QUICK_COOL = "quick_cool"
REMOTE_CTL_QUICK_HEAT = "quick_heat"
REMOTE_CTL_WINDSHIELD_DEFROST = "windshield_defrost"

REMOTE_ACTION_SPECS: dict[str, RemoteActionSpec] = {
    REMOTE_CTL_UNLOCK: RemoteActionSpec(cmd_id="110", cmd_content='{"value":"unlock"}'),
    REMOTE_CTL_LOCK: RemoteActionSpec(cmd_id="110", cmd_content='{"value":"lock"}'),
    REMOTE_CTL_TRUNK: RemoteActionSpec(cmd_id="130", cmd_content='{"value":"true"}'),
    REMOTE_CTL_TRUNK_OPEN: RemoteActionSpec(cmd_id="130", cmd_content='{"value":"true"}'),
    REMOTE_CTL_TRUNK_CLOSE: RemoteActionSpec(cmd_id="130", cmd_content='{"value":"false"}'),
    REMOTE_CTL_FIND_CAR: RemoteActionSpec(cmd_id="120", cmd_content='{"value":"true"}'),
    REMOTE_CTL_SUNSHADE: RemoteActionSpec(cmd_id="240", cmd_content='{"value":"10"}'),
    REMOTE_CTL_SUNSHADE_OPEN: RemoteActionSpec(cmd_id="240", cmd_content='{"value":"10"}'),
    REMOTE_CTL_SUNSHADE_CLOSE: RemoteActionSpec(cmd_id="240", cmd_content='{"value":"0"}'),
    REMOTE_CTL_BATTERY_PREHEAT: RemoteActionSpec(cmd_id="160", cmd_content='{"value":"ptcon"}'),
    REMOTE_CTL_WINDOWS: RemoteActionSpec(cmd_id="230", cmd_content='{"value":"2"}'),
    REMOTE_CTL_WINDOWS_OPEN: RemoteActionSpec(cmd_id="230", cmd_content='{"value":"2"}'),
    REMOTE_CTL_WINDOWS_CLOSE: RemoteActionSpec(cmd_id="230", cmd_content='{"value":"0"}'),
    REMOTE_CTL_AC_SWITCH: RemoteActionSpec(
        cmd_id="170",
        cmd_content='{"circle":"out","mode":"nohotcold","operate":"manual","position":"all","temperature":"24","windlevel":"4","wshld":"1"}',
    ),
    REMOTE_CTL_QUICK_COOL: RemoteActionSpec(
        cmd_id="170",
        cmd_content='{"circle":"in","mode":"cold","operate":"manual","position":"all","temperature":"18","windlevel":"7","wshld":"1"}',
    ),
    REMOTE_CTL_QUICK_HEAT: RemoteActionSpec(
        cmd_id="170",
        cmd_content='{"circle":"in","mode":"hot","operate":"manual","position":"all","temperature":"32","windlevel":"7","wshld":"1"}',
    ),
    REMOTE_CTL_WINDSHIELD_DEFROST: RemoteActionSpec(
        cmd_id="170",
        cmd_content='{"circle":"in","mode":"hot","operate":"manual","position":"all","temperature":"32","windlevel":"7","wshld":"2"}',
    ),
}
