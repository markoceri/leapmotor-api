"""Remote-control action mappings.

This module is separated from :mod:`const` to avoid circular imports
between ``const`` and ``models``.
"""

from __future__ import annotations

from .const import (
    REMOTE_CTL_AC_OFF,
    REMOTE_CTL_AC_ON,
    REMOTE_CTL_AC_SCHEDULE,
    REMOTE_CTL_AC_SWITCH,
    REMOTE_CTL_AUTOPARK,
    REMOTE_CTL_BATTERY_PREHEAT,
    REMOTE_CTL_BATTERY_PREHEAT_OFF,
    REMOTE_CTL_BATTERY_PREHEAT_ON,
    REMOTE_CTL_BLE_KEY_RESTART,
    REMOTE_CTL_CHARGE_LIMIT,
    REMOTE_CTL_CHARGE_SCHEDULE,
    REMOTE_CTL_CHARGE_START,
    REMOTE_CTL_CHARGE_STOP,
    REMOTE_CTL_FIND_CAR,
    REMOTE_CTL_FOTA_DOWNLOAD,
    REMOTE_CTL_FOTA_INSTALL,
    REMOTE_CTL_FOTA_SCHEDULE,
    REMOTE_CTL_FUEL_HEATING,
    REMOTE_CTL_FUEL_HEATING_OFF,
    REMOTE_CTL_FUEL_HEATING_ON,
    REMOTE_CTL_HEALTHY_CHARGING,
    REMOTE_CTL_HEALTHY_CHARGING_OFF,
    REMOTE_CTL_HEALTHY_CHARGING_ON,
    REMOTE_CTL_HOTSPOT,
    REMOTE_CTL_LOCK,
    REMOTE_CTL_MUSIC,
    REMOTE_CTL_ON3,
    REMOTE_CTL_ON3_OFF,
    REMOTE_CTL_ON3_ON,
    REMOTE_CTL_PILOTED_PARKING,
    REMOTE_CTL_PREPARE_CAR,
    REMOTE_CTL_PREPARE_CAR_SCHEDULE,
    REMOTE_CTL_QUICK_COOL,
    REMOTE_CTL_QUICK_HEAT,
    REMOTE_CTL_REAR_SEATS,
    REMOTE_CTL_REARVIEW_MIRROR_HEAT,
    REMOTE_CTL_REARVIEW_MIRROR_HEAT_OFF,
    REMOTE_CTL_REARVIEW_MIRROR_HEAT_ON,
    REMOTE_CTL_SEAT_ADJUST,
    REMOTE_CTL_SEAT_HEAT,
    REMOTE_CTL_SEAT_VENTILATION,
    REMOTE_CTL_SEND_DESTINATION,
    REMOTE_CTL_SENTRY_MODE,
    REMOTE_CTL_SENTRY_MODE_OFF,
    REMOTE_CTL_SENTRY_MODE_ON,
    REMOTE_CTL_SPEED_LIMIT,
    REMOTE_CTL_STEERING_WHEEL_HEAT,
    REMOTE_CTL_STEERING_WHEEL_HEAT_OFF,
    REMOTE_CTL_STEERING_WHEEL_HEAT_ON,
    REMOTE_CTL_SUNROOF,
    REMOTE_CTL_SUNROOF_CLOSE,
    REMOTE_CTL_SUNROOF_OPEN,
    REMOTE_CTL_SUNSHADE,
    REMOTE_CTL_SUNSHADE_CLOSE,
    REMOTE_CTL_SUNSHADE_OPEN,
    REMOTE_CTL_TRUNK,
    REMOTE_CTL_TRUNK_CLOSE,
    REMOTE_CTL_TRUNK_OPEN,
    REMOTE_CTL_UNLOCK,
    REMOTE_CTL_UNLOCK_CHARGER,
    REMOTE_CTL_VIDEO,
    REMOTE_CTL_WINDOWS,
    REMOTE_CTL_WINDOWS_CLOSE,
    REMOTE_CTL_WINDOWS_OPEN,
    REMOTE_CTL_WINDSHIELD_DEFROST,
)
from .models import (
    BatteryPreheatValue,
    CarType,
    ChargeToggleValue,
    ClimateCircle,
    ClimateMode,
    ClimateOperate,
    ClimatePosition,
    ClimateWindshield,
    FuelHeatingValue,
    HealthyChargingValue,
    LockValue,
    On3Value,
    RearviewMirrorHeatValue,
    RemoteActionCtlAutopark,
    RemoteActionCtlBatteryPreheat,
    RemoteActionCtlBleKeyRestart,
    RemoteActionCtlChargePlan,
    RemoteActionCtlClimate,
    RemoteActionCtlClimateOff,
    RemoteActionCtlClimateSchedule,
    RemoteActionCtlFindCar,
    RemoteActionCtlFotaDownload,
    RemoteActionCtlFotaInstall,
    RemoteActionCtlFotaSchedule,
    RemoteActionCtlFuelHeating,
    RemoteActionCtlHealthyCharging,
    RemoteActionCtlHotspot,
    RemoteActionCtlLock,
    RemoteActionCtlMusic,
    RemoteActionCtlOn3,
    RemoteActionCtlPilotedParking,
    RemoteActionCtlPrepareCar,
    RemoteActionCtlPrepareCarSchedule,
    RemoteActionCtlRearSeats,
    RemoteActionCtlRearviewMirrorHeat,
    RemoteActionCtlSeatAdjust,
    RemoteActionCtlSeatHeat,
    RemoteActionCtlSeatVentilation,
    RemoteActionCtlSendDestination,
    RemoteActionCtlSentryMode,
    RemoteActionCtlSpeedLimit,
    RemoteActionCtlSteeringWheelHeat,
    RemoteActionCtlSunroof,
    RemoteActionCtlSunshade,
    RemoteActionCtlToggleCharge,
    RemoteActionCtlTrunk,
    RemoteActionCtlUnlockCharger,
    RemoteActionCtlVideo,
    RemoteActionCtlWindows,
    RemoteActionSpec,
    SentryModeValue,
    SteeringWheelHeatValue,
    SunroofValue,
    SunshadeValue,
    ToggleValue,
    VehicleAbility,
    VehicleRight,
    WindowsValue,
)

REMOTE_ACTION_SPECS: dict[str, RemoteActionSpec] = {
    REMOTE_CTL_UNLOCK: RemoteActionCtlLock(value=LockValue.UNLOCK, required_right=VehicleRight.LOCK),
    REMOTE_CTL_LOCK: RemoteActionCtlLock(value=LockValue.LOCK, required_right=VehicleRight.LOCK),
    REMOTE_CTL_UNLOCK_CHARGER: RemoteActionCtlUnlockCharger(required_right=VehicleRight.UNLOCK_CHARGER),
    REMOTE_CTL_TRUNK: RemoteActionCtlTrunk(value=ToggleValue.TRUE, required_right=VehicleRight.TRUNK),
    REMOTE_CTL_TRUNK_OPEN: RemoteActionCtlTrunk(value=ToggleValue.TRUE, required_right=VehicleRight.TRUNK),
    REMOTE_CTL_TRUNK_CLOSE: RemoteActionCtlTrunk(value=ToggleValue.FALSE, required_right=VehicleRight.TRUNK),
    REMOTE_CTL_FIND_CAR: RemoteActionCtlFindCar(value=ToggleValue.TRUE, required_right=VehicleRight.FIND_CAR),
    REMOTE_CTL_HOTSPOT: RemoteActionCtlHotspot(required_right=VehicleRight.HOTSPOT),
    REMOTE_CTL_AUTOPARK: RemoteActionCtlAutopark(required_right=VehicleRight.AUTOPARK),
    REMOTE_CTL_SUNSHADE: RemoteActionCtlSunshade(value=SunshadeValue.OPEN, required_right=VehicleRight.SUNSHADE),
    REMOTE_CTL_SUNSHADE_OPEN: RemoteActionCtlSunshade(value=SunshadeValue.OPEN, required_right=VehicleRight.SUNSHADE),
    REMOTE_CTL_SUNSHADE_CLOSE: RemoteActionCtlSunshade(value=SunshadeValue.CLOSE, required_right=VehicleRight.SUNSHADE),
    REMOTE_CTL_BATTERY_PREHEAT: RemoteActionCtlBatteryPreheat(
        value=BatteryPreheatValue.ON, required_right=VehicleRight.BATTERY_PREHEAT
    ),
    REMOTE_CTL_BATTERY_PREHEAT_ON: RemoteActionCtlBatteryPreheat(
        value=BatteryPreheatValue.ON, required_right=VehicleRight.BATTERY_PREHEAT
    ),
    REMOTE_CTL_BATTERY_PREHEAT_OFF: RemoteActionCtlBatteryPreheat(
        value=BatteryPreheatValue.OFF, required_right=VehicleRight.BATTERY_PREHEAT
    ),
    REMOTE_CTL_WINDOWS: RemoteActionCtlWindows(value=WindowsValue.OPEN, required_right=VehicleRight.WINDOWS),
    REMOTE_CTL_WINDOWS_OPEN: RemoteActionCtlWindows(value=WindowsValue.OPEN, required_right=VehicleRight.WINDOWS),
    REMOTE_CTL_WINDOWS_CLOSE: RemoteActionCtlWindows(value=WindowsValue.CLOSE, required_right=VehicleRight.WINDOWS),
    REMOTE_CTL_AC_SWITCH: RemoteActionCtlClimate(
        circle=ClimateCircle.OUT,
        mode=ClimateMode.WIND,
        operate=ClimateOperate.MANUAL,
        position=ClimatePosition.ALL,
        temperature="26",
        windlevel=3,
        wshld=ClimateWindshield.OFF,
        required_right=VehicleRight.CLIMATE,
    ),
    REMOTE_CTL_AC_ON: RemoteActionCtlClimate(
        circle=ClimateCircle.OUT,
        mode=ClimateMode.WIND,
        operate=ClimateOperate.MANUAL,
        position=ClimatePosition.ALL,
        temperature="26",
        windlevel=3,
        wshld=ClimateWindshield.OFF,
        required_right=VehicleRight.CLIMATE,
    ),
    REMOTE_CTL_AC_OFF: RemoteActionCtlClimateOff(required_right=VehicleRight.CLIMATE),
    REMOTE_CTL_QUICK_COOL: RemoteActionCtlClimate(
        circle=ClimateCircle.IN,
        mode=ClimateMode.COLD,
        operate=ClimateOperate.MANUAL,
        position=ClimatePosition.ALL,
        temperature="18",
        windlevel=7,
        wshld=ClimateWindshield.OFF,
        required_right=VehicleRight.QUICK_CLIMATE,
    ),
    REMOTE_CTL_QUICK_HEAT: RemoteActionCtlClimate(
        circle=ClimateCircle.IN,
        mode=ClimateMode.HOT,
        operate=ClimateOperate.MANUAL,
        position=ClimatePosition.ALL,
        temperature="32",
        windlevel=7,
        wshld=ClimateWindshield.OFF,
        required_right=VehicleRight.QUICK_CLIMATE,
    ),
    REMOTE_CTL_WINDSHIELD_DEFROST: RemoteActionCtlClimate(
        circle=ClimateCircle.IN,
        mode=ClimateMode.HOT,
        operate=ClimateOperate.MANUAL,
        position=ClimatePosition.ALL,
        temperature="32",
        windlevel=7,
        wshld=ClimateWindshield.ON,
        required_right=VehicleRight.WINDSHIELD_DEFROST,
    ),
    REMOTE_CTL_AC_SCHEDULE: RemoteActionCtlClimateSchedule(
        required_right=VehicleRight.QUICK_CLIMATE,
    ),
    REMOTE_CTL_CHARGE_LIMIT: RemoteActionCtlChargePlan(required_right=VehicleRight.CHARGE_LIMIT),
    REMOTE_CTL_CHARGE_SCHEDULE: RemoteActionCtlChargePlan(required_right=VehicleRight.CHARGE_LIMIT),
    REMOTE_CTL_SEND_DESTINATION: RemoteActionCtlSendDestination(required_right=VehicleRight.SEND_DESTINATION),
    REMOTE_CTL_SENTRY_MODE: RemoteActionCtlSentryMode(
        value=SentryModeValue.ON, required_right=VehicleRight.SENTRY_MODE
    ),
    REMOTE_CTL_SENTRY_MODE_ON: RemoteActionCtlSentryMode(
        value=SentryModeValue.ON, required_right=VehicleRight.SENTRY_MODE
    ),
    REMOTE_CTL_SENTRY_MODE_OFF: RemoteActionCtlSentryMode(
        value=SentryModeValue.OFF, required_right=VehicleRight.SENTRY_MODE
    ),
    REMOTE_CTL_CHARGE_START: RemoteActionCtlToggleCharge(
        value=ChargeToggleValue.START, required_right=VehicleRight.TOGGLE_CHARGE
    ),
    REMOTE_CTL_CHARGE_STOP: RemoteActionCtlToggleCharge(
        value=ChargeToggleValue.STOP, required_right=VehicleRight.TOGGLE_CHARGE
    ),
    REMOTE_CTL_STEERING_WHEEL_HEAT: RemoteActionCtlSteeringWheelHeat(
        value=SteeringWheelHeatValue.ON, required_right=VehicleRight.STEERING_WHEEL_HEAT
    ),
    REMOTE_CTL_STEERING_WHEEL_HEAT_ON: RemoteActionCtlSteeringWheelHeat(
        value=SteeringWheelHeatValue.ON, required_right=VehicleRight.STEERING_WHEEL_HEAT
    ),
    REMOTE_CTL_STEERING_WHEEL_HEAT_OFF: RemoteActionCtlSteeringWheelHeat(
        value=SteeringWheelHeatValue.OFF, required_right=VehicleRight.STEERING_WHEEL_HEAT
    ),
    REMOTE_CTL_FUEL_HEATING: RemoteActionCtlFuelHeating(
        value=FuelHeatingValue.ON, required_right=VehicleRight.FUEL_HEATING
    ),
    REMOTE_CTL_FUEL_HEATING_ON: RemoteActionCtlFuelHeating(
        value=FuelHeatingValue.ON, required_right=VehicleRight.FUEL_HEATING
    ),
    REMOTE_CTL_FUEL_HEATING_OFF: RemoteActionCtlFuelHeating(
        value=FuelHeatingValue.OFF, required_right=VehicleRight.FUEL_HEATING
    ),
    REMOTE_CTL_REARVIEW_MIRROR_HEAT: RemoteActionCtlRearviewMirrorHeat(
        value=RearviewMirrorHeatValue.ON, required_right=VehicleRight.REARVIEW_MIRROR_HEAT
    ),
    REMOTE_CTL_REARVIEW_MIRROR_HEAT_ON: RemoteActionCtlRearviewMirrorHeat(
        value=RearviewMirrorHeatValue.ON, required_right=VehicleRight.REARVIEW_MIRROR_HEAT
    ),
    REMOTE_CTL_REARVIEW_MIRROR_HEAT_OFF: RemoteActionCtlRearviewMirrorHeat(
        value=RearviewMirrorHeatValue.OFF, required_right=VehicleRight.REARVIEW_MIRROR_HEAT
    ),
    REMOTE_CTL_SPEED_LIMIT: RemoteActionCtlSpeedLimit(required_right=VehicleRight.SPEED_LIMIT),
    REMOTE_CTL_SEAT_HEAT: RemoteActionCtlSeatHeat(required_right=VehicleRight.SEAT_HEAT),
    REMOTE_CTL_SEAT_VENTILATION: RemoteActionCtlSeatVentilation(required_right=VehicleRight.SEAT_VENTILATION),
    REMOTE_CTL_SUNROOF: RemoteActionCtlSunroof(value=SunroofValue.OPEN, required_right=VehicleRight.SUNROOF),
    REMOTE_CTL_SUNROOF_OPEN: RemoteActionCtlSunroof(value=SunroofValue.OPEN, required_right=VehicleRight.SUNROOF),
    REMOTE_CTL_SUNROOF_CLOSE: RemoteActionCtlSunroof(value=SunroofValue.CLOSE, required_right=VehicleRight.SUNROOF),
    REMOTE_CTL_HEALTHY_CHARGING: RemoteActionCtlHealthyCharging(
        value=HealthyChargingValue.ON, required_right=VehicleRight.HEALTHY_CHARGING
    ),
    REMOTE_CTL_HEALTHY_CHARGING_ON: RemoteActionCtlHealthyCharging(
        value=HealthyChargingValue.ON, required_right=VehicleRight.HEALTHY_CHARGING
    ),
    REMOTE_CTL_HEALTHY_CHARGING_OFF: RemoteActionCtlHealthyCharging(
        value=HealthyChargingValue.OFF, required_right=VehicleRight.HEALTHY_CHARGING
    ),
    REMOTE_CTL_ON3: RemoteActionCtlOn3(value=On3Value.ON, required_right=VehicleRight.ON3),
    REMOTE_CTL_ON3_ON: RemoteActionCtlOn3(value=On3Value.ON, required_right=VehicleRight.ON3),
    REMOTE_CTL_ON3_OFF: RemoteActionCtlOn3(value=On3Value.OFF, required_right=VehicleRight.ON3),
    REMOTE_CTL_BLE_KEY_RESTART: RemoteActionCtlBleKeyRestart(required_right=VehicleRight.BLE_KEY_RESTART),
    REMOTE_CTL_MUSIC: RemoteActionCtlMusic(required_right=VehicleRight.MUSIC),
    REMOTE_CTL_VIDEO: RemoteActionCtlVideo(required_right=VehicleRight.VIDEO),
    REMOTE_CTL_FOTA_DOWNLOAD: RemoteActionCtlFotaDownload(required_right=VehicleRight.FOTA_DOWNLOAD),
    REMOTE_CTL_FOTA_INSTALL: RemoteActionCtlFotaInstall(required_right=VehicleRight.FOTA_INSTALL),
    REMOTE_CTL_FOTA_SCHEDULE: RemoteActionCtlFotaSchedule(required_right=VehicleRight.FOTA_INSTALL_APPOINTMENT),
    REMOTE_CTL_REAR_SEATS: RemoteActionCtlRearSeats(required_right=VehicleRight.REAR_SEATS),
    REMOTE_CTL_PREPARE_CAR: RemoteActionCtlPrepareCar(required_right=VehicleRight.PREPARE_CAR),
    REMOTE_CTL_PREPARE_CAR_SCHEDULE: RemoteActionCtlPrepareCarSchedule(required_right=VehicleRight.PREPARE_CAR_ALARM),
    REMOTE_CTL_SEAT_ADJUST: RemoteActionCtlSeatAdjust(required_right=VehicleRight.SEAT_ADJUST),
    REMOTE_CTL_PILOTED_PARKING: RemoteActionCtlPilotedParking(required_right=VehicleRight.PILOTED_PARKING),
}

# ---------------------------------------------------------------------------
# Per-model remote action overrides
# ---------------------------------------------------------------------------

# Some models need a different payload for the same action. The cloud answers
# ``code=0`` to both shapes, but only the right one is executed by the car.
# ``_remote_control`` picks the override for the target vehicle's ``carType``
# and falls back to :data:`REMOTE_ACTION_SPECS`.
REMOTE_ACTION_CAR_TYPE_SPECS: dict[str, dict[CarType, RemoteActionSpec]] = {
    # The T03 ignores the bare ``{"operate":"off"}`` body (and ``operate=close``):
    # it powers off only with ``operate=off`` inside the full climate body.
    REMOTE_CTL_AC_OFF: {
        CarType.T03: RemoteActionCtlClimate(
            circle=ClimateCircle.OUT,
            mode=ClimateMode.WIND,
            operate=ClimateOperate.OFF,
            position=ClimatePosition.ALL,
            temperature="26",
            windlevel=3,
            wshld=ClimateWindshield.OFF,
            required_right=VehicleRight.CLIMATE,
        ),
    },
}

# ---------------------------------------------------------------------------
# Car-type path mapping
# ---------------------------------------------------------------------------

# The international backend reports carType=B10 in the vehicle list,
# but the status endpoint is shared with C10.  B11 and B05 also use the C10 path.
# Requesting the model's own segment (e.g. ``/status/get/b05``) is answered with
# ``No message available`` / HTTP 404, while every other call in the flow succeeds.
# Single source of truth: resolve at runtime via ``CarType(car_type_str).status_path``.
CAR_TYPE_PATH_MAP: dict[str, str] = {
    CarType.B10: CarType.C10,
    CarType.B11: CarType.C10,
    CarType.B05: CarType.C10,
}

# ---------------------------------------------------------------------------
# Ability → Right relationship mapping
# ---------------------------------------------------------------------------
# Documents which VehicleAbility codes enable which VehicleRight codes.
# The server computes this; the mapping is informational for consumers.
# Based on decompiled international APK ``CarAblityToPerManager.ablityToPer()``.

ABILITY_TO_RIGHTS: dict[VehicleAbility, list[VehicleRight]] = {
    VehicleAbility.BASE: [VehicleRight.LOCK],
    VehicleAbility.STATUS_DATA: [VehicleRight.FIND_CAR],
    VehicleAbility.TRUNK: [VehicleRight.TRUNK],
    VehicleAbility.AUTOPARK: [VehicleRight.AUTOPARK],
    VehicleAbility.AC_ON: [VehicleRight.CLIMATE],
    VehicleAbility.AC_PRESET: [VehicleRight.QUICK_CLIMATE],
    VehicleAbility.LOCK_UNLOCK: [VehicleRight.BATTERY_PREHEAT],
    VehicleAbility.FIND_CAR: [VehicleRight.SUNSHADE],
    VehicleAbility.WINDOWS_C10: [VehicleRight.WINDOWS],
    VehicleAbility.WINDOWS_T03: [VehicleRight.WINDOWS],
    VehicleAbility.SEAT_HEATING: [VehicleRight.SEAT_HEAT],
    VehicleAbility.STEERING_WHEEL: [VehicleRight.STEERING_WHEEL_HEAT],
    VehicleAbility.CLIMATE_ADVANCED: [VehicleRight.QUICK_CLIMATE],
    VehicleAbility.WINDSHIELD_DEFROST: [VehicleRight.WINDSHIELD_DEFROST],
    VehicleAbility.TRUNK_SPECIAL: [VehicleRight.TRUNK],
    VehicleAbility.CYCLIC_CHARGE: [VehicleRight.SUNROOF],
    VehicleAbility.GPS_SHARING: [VehicleRight.SEND_DESTINATION],
    VehicleAbility.MILEAGE_ENERGY: [],
    VehicleAbility.SPEED_LIMIT: [VehicleRight.SPEED_LIMIT],
    VehicleAbility.CHARGE_LIMIT: [VehicleRight.CHARGE_LIMIT],
    VehicleAbility.PREPARE: [VehicleRight.PREPARE_CAR, VehicleRight.PREPARE_CAR_ALARM],
    VehicleAbility.FUEL_HEATING: [VehicleRight.FUEL_HEATING],
    VehicleAbility.SENTINEL: [VehicleRight.SENTRY_MODE],
    VehicleAbility.NAVIGATION: [VehicleRight.SEND_DESTINATION],
    VehicleAbility.DRIVER_SEAT_VENTILATION: [VehicleRight.SEAT_VENTILATION],
    VehicleAbility.PASSENGER_SEAT_VENTILATION: [VehicleRight.SEAT_VENTILATION],
    VehicleAbility.UNLOCK_CHARGE_GUN: [VehicleRight.UNLOCK_CHARGER],
}

# Rights restricted to T03/S01 only — these models have a limited
# feature set compared to C-platform and B-platform models.
T03_S01_SUPPORTED_RIGHTS: frozenset[VehicleRight] = frozenset(
    {
        VehicleRight.LOCK,
        VehicleRight.FIND_CAR,
        VehicleRight.TRUNK,
        VehicleRight.CLIMATE,
        VehicleRight.QUICK_CLIMATE,
        VehicleRight.SEND_DESTINATION,
        VehicleRight.BATTERY_PREHEAT,
        VehicleRight.SUNSHADE,
        VehicleRight.SENTRY_MODE,
        VehicleRight.WINDOWS,
        VehicleRight.SKYLIGHT,
        VehicleRight.CHARGE_LIMIT,
        VehicleRight.WINDSHIELD_DEFROST,
        VehicleRight.SUNROOF,
        VehicleRight.AUTOPARK,
    }
)
