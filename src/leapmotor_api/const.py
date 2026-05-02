"""Leapmotor API constants."""

from __future__ import annotations

from .models import (
    BatteryPreheatValue,
    ClimateCircle,
    ClimateMode,
    ClimateOperate,
    ClimatePosition,
    ClimateWindshield,
    LockValue,
    RemoteActionCtlBatteryPreheat,
    RemoteActionCtlClimate,
    RemoteActionCtlFindCar,
    RemoteActionCtlLock,
    RemoteActionCtlSunshade,
    RemoteActionCtlTrunk,
    RemoteActionCtlWindows,
    RemoteActionSpec,
    SunshadeValue,
    ToggleValue,
    WindowsValue,
)

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
    REMOTE_CTL_UNLOCK: RemoteActionCtlLock(value=LockValue.UNLOCK),
    REMOTE_CTL_LOCK: RemoteActionCtlLock(value=LockValue.LOCK),
    REMOTE_CTL_TRUNK: RemoteActionCtlTrunk(value=ToggleValue.TRUE),
    REMOTE_CTL_TRUNK_OPEN: RemoteActionCtlTrunk(value=ToggleValue.TRUE),
    REMOTE_CTL_TRUNK_CLOSE: RemoteActionCtlTrunk(value=ToggleValue.FALSE),
    REMOTE_CTL_FIND_CAR: RemoteActionCtlFindCar(value=ToggleValue.TRUE),
    REMOTE_CTL_SUNSHADE: RemoteActionCtlSunshade(value=SunshadeValue.OPEN),
    REMOTE_CTL_SUNSHADE_OPEN: RemoteActionCtlSunshade(value=SunshadeValue.OPEN),
    REMOTE_CTL_SUNSHADE_CLOSE: RemoteActionCtlSunshade(value=SunshadeValue.CLOSE),
    REMOTE_CTL_BATTERY_PREHEAT: RemoteActionCtlBatteryPreheat(value=BatteryPreheatValue.ON),
    REMOTE_CTL_WINDOWS: RemoteActionCtlWindows(value=WindowsValue.OPEN),
    REMOTE_CTL_WINDOWS_OPEN: RemoteActionCtlWindows(value=WindowsValue.OPEN),
    REMOTE_CTL_WINDOWS_CLOSE: RemoteActionCtlWindows(value=WindowsValue.CLOSE),
    REMOTE_CTL_AC_SWITCH: RemoteActionCtlClimate(
        circle=ClimateCircle.OUT,
        mode=ClimateMode.NO_HOT_COLD,
        operate=ClimateOperate.MANUAL,
        position=ClimatePosition.ALL,
        temperature="24",
        windlevel="4",
        wshld=ClimateWindshield.NORMAL,
    ),
    REMOTE_CTL_QUICK_COOL: RemoteActionCtlClimate(
        circle=ClimateCircle.IN,
        mode=ClimateMode.COLD,
        operate=ClimateOperate.MANUAL,
        position=ClimatePosition.ALL,
        temperature="18",
        windlevel="7",
        wshld=ClimateWindshield.NORMAL,
    ),
    REMOTE_CTL_QUICK_HEAT: RemoteActionCtlClimate(
        circle=ClimateCircle.IN,
        mode=ClimateMode.HOT,
        operate=ClimateOperate.MANUAL,
        position=ClimatePosition.ALL,
        temperature="32",
        windlevel="7",
        wshld=ClimateWindshield.NORMAL,
    ),
    REMOTE_CTL_WINDSHIELD_DEFROST: RemoteActionCtlClimate(
        circle=ClimateCircle.IN,
        mode=ClimateMode.HOT,
        operate=ClimateOperate.MANUAL,
        position=ClimatePosition.ALL,
        temperature="32",
        windlevel="7",
        wshld=ClimateWindshield.DEFROST,
    ),
}
