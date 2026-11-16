"""Leapmotor API constants."""

from __future__ import annotations

DEFAULT_BASE_URL = "https://appgateway.leapmotor-international.de"
# Fallback host for the route login / app-global-service (hostType GLOBAL in the
# app). Used only if the primary gateway does not route the new /base/base-user
# paths. See client._route_login.
DEFAULT_GLOBAL_BASE_URL = "https://app-gw-global-master.leapmotor-international.de"
DEFAULT_APP_VERSION = "1.12.3"
# App version advertised on the v2-signed endpoints (route login + charging
# history). The real app 1.18.2 sends this; it is part of the v2 sign input, so
# it must match what the gateway recomputes against. v1/legacy login keep
# DEFAULT_APP_VERSION.
DEFAULT_APP_VERSION_V2 = "1.18.2"
DEFAULT_SOURCE = "leapmotor"
DEFAULT_CHANNEL = "1"
DEFAULT_LANGUAGE = "en-GB"
DEFAULT_DEVICE_TYPE = "1"
DEFAULT_P12_ENC_ALG = "1"
DEFAULT_POLICY_ID = "20260204"

# --- v2 signature (x-api-signature-version: 2.0) ---
# The real app uses deviceType="android" (not "1") for v2-signed requests, plus
# the extra headers below. These are only applied by build_signed_headers_v2 so
# the legacy login/v1 paths keep deviceType="1".
DEFAULT_DEVICE_TYPE_V2 = "android"
DEFAULT_REGION = "EU"
DEFAULT_SIGNATURE_VERSION = "2.0"

DEFAULT_OPERPWD_AES_KEY = "f1cf0c025baec0e2"
DEFAULT_OPERPWD_AES_IV = "6b6a1fe94e133fd7"

# Known fallback passwords for account PKCS#12 certificate.
KNOWN_ACCOUNT_P12_PASSWORDS: tuple[str, ...] = ()

# Remote-control action identifiers.
REMOTE_CTL_LOCK = "lock"
REMOTE_CTL_UNLOCK = "unlock"
REMOTE_CTL_UNLOCK_CHARGER = "unlock_charger"
REMOTE_CTL_TRUNK = "trunk"
REMOTE_CTL_TRUNK_OPEN = "trunk_open"
REMOTE_CTL_TRUNK_CLOSE = "trunk_close"
REMOTE_CTL_FIND_CAR = "find_car"
REMOTE_CTL_HOTSPOT = "hotspot"
REMOTE_CTL_AUTOPARK = "autopark"
REMOTE_CTL_SUNSHADE = "sunshade"
REMOTE_CTL_SUNSHADE_OPEN = "sunshade_open"
REMOTE_CTL_SUNSHADE_CLOSE = "sunshade_close"
REMOTE_CTL_BATTERY_PREHEAT = "battery_preheat"
REMOTE_CTL_BATTERY_PREHEAT_ON = "battery_preheat_on"
REMOTE_CTL_BATTERY_PREHEAT_OFF = "battery_preheat_off"
REMOTE_CTL_WINDOWS = "windows"
REMOTE_CTL_WINDOWS_OPEN = "windows_open"
REMOTE_CTL_WINDOWS_CLOSE = "windows_close"
REMOTE_CTL_AC_SWITCH = "ac_switch"
REMOTE_CTL_AC_ON = "ac_on"
REMOTE_CTL_AC_OFF = "ac_off"
REMOTE_CTL_AC_SCHEDULE = "ac_schedule"
REMOTE_CTL_QUICK_COOL = "quick_cool"
REMOTE_CTL_QUICK_HEAT = "quick_heat"
REMOTE_CTL_WINDSHIELD_DEFROST = "windshield_defrost"
REMOTE_CTL_CHARGE_LIMIT = "set_charge_limit"
REMOTE_CTL_CHARGE_SCHEDULE = "set_charge_schedule"
REMOTE_CTL_SEND_DESTINATION = "send_destination"
REMOTE_CTL_SENTRY_MODE = "sentry_mode"
REMOTE_CTL_SENTRY_MODE_ON = "sentry_mode_on"
REMOTE_CTL_SENTRY_MODE_OFF = "sentry_mode_off"
REMOTE_CTL_CHARGE_START = "charge_start"
REMOTE_CTL_CHARGE_STOP = "charge_stop"
REMOTE_CTL_STEERING_WHEEL_HEAT = "steering_wheel_heat"
REMOTE_CTL_STEERING_WHEEL_HEAT_ON = "steering_wheel_heat_on"
REMOTE_CTL_STEERING_WHEEL_HEAT_OFF = "steering_wheel_heat_off"
REMOTE_CTL_FUEL_HEATING = "fuel_heating"
REMOTE_CTL_FUEL_HEATING_ON = "fuel_heating_on"
REMOTE_CTL_FUEL_HEATING_OFF = "fuel_heating_off"
REMOTE_CTL_REARVIEW_MIRROR_HEAT = "rearview_mirror_heat"
REMOTE_CTL_REARVIEW_MIRROR_HEAT_ON = "rearview_mirror_heat_on"
REMOTE_CTL_REARVIEW_MIRROR_HEAT_OFF = "rearview_mirror_heat_off"
REMOTE_CTL_SPEED_LIMIT = "set_speed_limit"
REMOTE_CTL_SEAT_HEAT = "seat_heat"
REMOTE_CTL_SEAT_VENTILATION = "seat_ventilation"
REMOTE_CTL_SUNROOF = "sunroof"
REMOTE_CTL_SUNROOF_OPEN = "sunroof_open"
REMOTE_CTL_SUNROOF_CLOSE = "sunroof_close"
REMOTE_CTL_HEALTHY_CHARGING = "healthy_charging"
REMOTE_CTL_HEALTHY_CHARGING_ON = "healthy_charging_on"
REMOTE_CTL_HEALTHY_CHARGING_OFF = "healthy_charging_off"
REMOTE_CTL_ON3 = "on3"
REMOTE_CTL_ON3_ON = "on3_on"
REMOTE_CTL_ON3_OFF = "on3_off"
REMOTE_CTL_BLE_KEY_RESTART = "ble_key_restart"
REMOTE_CTL_MUSIC = "music"
REMOTE_CTL_VIDEO = "video"
REMOTE_CTL_FOTA_DOWNLOAD = "fota_download"
REMOTE_CTL_FOTA_INSTALL = "fota_install"
REMOTE_CTL_FOTA_SCHEDULE = "fota_schedule"
REMOTE_CTL_REAR_SEATS = "rear_seats"
REMOTE_CTL_PREPARE_CAR = "prepare_car"
REMOTE_CTL_PREPARE_CAR_SCHEDULE = "prepare_car_schedule"
REMOTE_CTL_SEAT_ADJUST = "seat_adjust"
REMOTE_CTL_PILOTED_PARKING = "piloted_parking"

DEFAULT_TIMEOUT = 30
