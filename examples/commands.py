"""Send remote commands to a Leapmotor vehicle."""

import argparse
import os
import sys
import time
from collections.abc import Callable
from typing import Any

from leapmotor_api.client import LeapmotorApiClient

# --- Credentials from environment variables ---
USERNAME = os.environ.get("LEAPMOTOR_USERNAME", "")
PASSWORD = os.environ.get("LEAPMOTOR_PASSWORD", "")
APP_CERT_PATH = os.environ.get("LEAPMOTOR_APP_CERT", "certs/app_cert.pem")
APP_KEY_PATH = os.environ.get("LEAPMOTOR_APP_KEY", "certs/app_key.pem")
OPERATION_PIN = os.environ.get("LEAPMOTOR_PIN", None)
ACCOUNT_P12_PASSWORD = os.environ.get("LEAPMOTOR_P12_PASSWORD", None)


COMMANDS: dict[str, dict[str, object]] = {
    # Lock & Unlock
    "lock": {"help": "Lock the vehicle", "args": []},
    "unlock": {"help": "Unlock the vehicle", "args": []},
    "unlock-charger": {"help": "Unlock the charging connector", "args": []},
    # Trunk
    "open-trunk": {"help": "Open the trunk", "args": []},
    "close-trunk": {"help": "Close the trunk", "args": []},
    # Search & Connectivity
    "find": {"help": "Find the vehicle (horn + lights flash)", "args": []},
    "hotspot": {"help": "Trigger hotspot / connectivity", "args": []},
    "autopark": {"help": "Trigger auto park / summon", "args": []},
    # Charging
    "start-charging": {"help": "Start charging", "args": []},
    "stop-charging": {"help": "Stop charging", "args": []},
    "charge-limit": {
        "help": "Set charge limit (percent)",
        "args": [{"name": "value", "type": int, "help": "SOC limit (e.g. 80)"}],
    },
    "charge-schedule": {
        "help": "Set charging schedule",
        "args": [
            {"name": "--enable", "type": int, "help": "Enable schedule (1=on, 0=off)", "default": 1},
            {"name": "--soc", "type": int, "help": "SOC limit (e.g. 80)", "default": 80},
            {"name": "start", "type": str, "help": "Start time (e.g. 23:00)"},
            {"name": "end", "type": str, "help": "End time (e.g. 07:00)"},
            {"name": "cycles", "type": str, "help": "Days (e.g. 1,2,3,4,5,6,7)"},
            {"name": "--circulation", "type": int, "help": "Repeat mode (0=once, 1=repeat)", "default": 0},
            {"name": "--recharge", "type": int, "help": "Auto-recharge (0=off, 1=on)", "default": 0},
        ],
    },
    "healthy-charging-on": {"help": "Enable healthy charging mode", "args": []},
    "healthy-charging-off": {"help": "Disable healthy charging mode", "args": []},
    # Battery
    "battery-preheat": {"help": "Start battery preheating", "args": []},
    "battery-preheat-off": {"help": "Stop battery preheating", "args": []},
    # Climate
    "ac-on": {
        "help": "Turn AC on (optional params: temp, mode, wind)",
        "args": [
            {"name": "--temp", "type": str, "help": "Temperature (e.g. 22)", "default": None},
            {"name": "--mode", "type": str, "help": "Mode: cold, hot, wind", "default": None},
            {"name": "--wind", "type": str, "help": "Wind level (e.g. 3)", "default": None},
            {
                "name": "--wait",
                "type": int,
                "help": "Seconds before re-reading acSwitch from the vehicle status (0 = skip)",
                "default": 12,
            },
        ],
    },
    "ac-off": {
        "help": "Turn AC off",
        "args": [
            {
                "name": "--wait",
                "type": int,
                "help": "Seconds before re-reading acSwitch from the vehicle status (0 = skip)",
                "default": 12,
            },
        ],
    },
    "ac-schedule": {
        "help": "Set climate schedule (start_time, temp, mode, wind, days)",
        "args": [
            {
                "name": "start_time",
                "type": str,
                "help": "Start time 'yyyy-MM-dd HH:mm:00' (e.g. '2026-05-16 07:30:00')",
            },
            {"name": "--temp", "type": str, "help": "Temperature (e.g. 22)", "default": "26"},
            {"name": "--mode", "type": str, "help": "Mode: cold, hot, wind", "default": "wind"},
            {"name": "--wind", "type": str, "help": "Wind level 1-7 (e.g. 3)", "default": "3"},
            {"name": "--days", "type": str, "help": "Days: 0-6 comma-sep (0=Sun), empty=once", "default": ""},
            {"name": "--circle", "type": str, "help": "Circulation: in, out", "default": "out"},
            {"name": "--off", "action": "store_true", "help": "Disable the schedule", "default": False},
        ],
    },
    "quick-cool": {"help": "Quick cooling", "args": []},
    "quick-heat": {"help": "Quick heating", "args": []},
    "defrost": {"help": "Windshield defrost", "args": []},
    "ac-schedule-cancel": {"help": "Cancel all climate schedules", "args": []},
    "ac-schedule-list": {"help": "List active climate schedules", "args": []},
    "ptc-schedule-list": {"help": "List active PTC battery heating schedules", "args": []},
    "charge-schedule-list": {"help": "Show charge schedule", "args": []},
    "prepare-car-schedule-list": {"help": "List active prepare-car schedules", "args": []},
    "fota-schedule-list": {"help": "List active FOTA install schedules", "args": []},
    # Sentry
    "sentry-on": {"help": "Enable sentry mode", "args": []},
    "sentry-off": {"help": "Disable sentry mode", "args": []},
    # Windows
    "open-windows": {
        "help": "Open windows (optional position 0-100)",
        "args": [{"name": "value", "type": str, "nargs": "?", "help": "Position 0-100", "default": None}],
    },
    "close-windows": {
        "help": "Close windows (optional position 0-100)",
        "args": [{"name": "value", "type": str, "nargs": "?", "help": "Position 0-100", "default": None}],
    },
    # Sunroof
    "open-sunroof": {"help": "Open sunroof", "args": []},
    "close-sunroof": {"help": "Close sunroof", "args": []},
    # Sunshade
    "open-sunshade": {
        "help": "Open sunshade (optional position 0-10)",
        "args": [{"name": "value", "type": str, "nargs": "?", "help": "Position 0-10", "default": None}],
    },
    "close-sunshade": {
        "help": "Close sunshade (optional position 0-10)",
        "args": [{"name": "value", "type": str, "nargs": "?", "help": "Position 0-10", "default": None}],
    },
    # Seats
    "seat-heat": {
        "help": "Set seat heating (position 1-6, level 0-3)",
        "args": [
            {
                "name": "position",
                "type": int,
                "help": "Seat: 1=left_front 2=copilot 3=driver 4=right_front 5=left_rear 6=right_rear",
            },
            {"name": "level", "type": int, "help": "Level: 0=off 1=low 2=medium 3=high"},
        ],
    },
    "seat-vent": {
        "help": "Set seat ventilation (position 1-6, level 0-3)",
        "args": [
            {
                "name": "position",
                "type": int,
                "help": "Seat: 1=left_front 2=copilot 3=driver 4=right_front 5=left_rear 6=right_rear",
            },
            {"name": "level", "type": int, "help": "Level: 0=off 1=low 2=medium 3=high"},
        ],
    },
    # Steering wheel
    "steering-heat-on": {"help": "Enable steering wheel heating", "args": []},
    "steering-heat-off": {"help": "Disable steering wheel heating", "args": []},
    # Mirrors
    "mirror-heat-on": {"help": "Enable rearview mirror heating", "args": []},
    "mirror-heat-off": {"help": "Disable rearview mirror heating", "args": []},
    # Fuel heating
    "fuel-heat-on": {"help": "Enable fuel heating", "args": []},
    "fuel-heat-off": {"help": "Disable fuel heating", "args": []},
    # ON3
    "on3-on": {"help": "Enable ON3 mode", "args": []},
    "on3-off": {"help": "Disable ON3 mode", "args": []},
    # Speed limit
    "speed-limit": {
        "help": "Set speed limit (km/h)",
        "args": [{"name": "value", "type": str, "help": "Speed in km/h (e.g. 120)"}],
    },
    # Navigation
    "send-destination": {
        "help": "Send navigation destination to the vehicle",
        "args": [
            {"name": "address", "type": str, "help": "Street address"},
            {"name": "name", "type": str, "help": "Destination name"},
            {"name": "lat", "type": float, "help": "Latitude"},
            {"name": "lon", "type": float, "help": "Longitude"},
        ],
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send remote commands to a Leapmotor vehicle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--vin",
        help="VIN of the target vehicle (uses first vehicle if omitted)",
        default=None,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    for cmd_name, cmd_info in COMMANDS.items():
        sub = subparsers.add_parser(cmd_name, help=str(cmd_info["help"]))
        for arg in cmd_info["args"]:  # type: ignore[union-attr]
            arg = dict(arg)  # copy
            name = arg.pop("name")
            if name.startswith("--"):
                sub.add_argument(name, **arg)
            else:
                sub.add_argument(name, **arg)

    return parser


def get_vin(client: LeapmotorApiClient, requested_vin: str | None) -> str:
    vehicles = client.get_vehicle_list()
    if not vehicles:
        print("ERROR: No vehicles found on this account.")
        sys.exit(1)

    if requested_vin:
        for v in vehicles:
            if v.vin == requested_vin:
                return v.vin
        print(f"ERROR: VIN {requested_vin} not found. Available:")
        for v in vehicles:
            print(f"  {v.vin}  ({v.vehicle_nickname})")
        sys.exit(1)

    vin = vehicles[0].vin
    print(f"Using vehicle: {vehicles[0].vehicle_nickname} ({vin})")
    return vin


def print_ac_switch(client: LeapmotorApiClient, vin: str, label: str) -> None:
    """Print acSwitch (signal 1938) as read from the vehicle status."""
    vehicle = next(v for v in client.get_vehicle_list() if v.vin == vin)
    status = client.get_vehicle_status(vehicle)
    print(f"acSwitch {label} ({vehicle.car_type}): {status.climate.ac_switch}")


def verify_ac_command(client: LeapmotorApiClient, vin: str, wait: int, send: Callable[[], Any]) -> Any:
    """Send an A/C command and show whether the car executed it.

    The cloud answers ``code=0`` even to commands the car ignores, so the
    only reliable check is acSwitch in the vehicle status after the command.
    """
    if wait <= 0:
        return send()
    print_ac_switch(client, vin, "before")
    result = send()
    print(f"OK: {result}")
    print(f"Waiting {wait}s before re-reading the vehicle status...")
    time.sleep(wait)
    print_ac_switch(client, vin, "after")
    return None


def execute_command(client: LeapmotorApiClient, vin: str, args: argparse.Namespace) -> None:
    cmd = args.command
    result = None

    # Lock & Unlock
    if cmd == "lock":
        result = client.lock_vehicle(vin)
    elif cmd == "unlock":
        result = client.unlock_vehicle(vin)
    elif cmd == "unlock-charger":
        result = client.unlock_charger(vin)

    # Trunk
    elif cmd == "open-trunk":
        result = client.open_trunk(vin)
    elif cmd == "close-trunk":
        result = client.close_trunk(vin)

    # Search & Connectivity
    elif cmd == "find":
        result = client.find_vehicle(vin)
    elif cmd == "hotspot":
        result = client.hotspot(vin)
    elif cmd == "autopark":
        result = client.autopark(vin)

    # Charging
    elif cmd == "start-charging":
        result = client.start_charging(vin)
    elif cmd == "stop-charging":
        result = client.stop_charging(vin)
    elif cmd == "charge-limit":
        result = client.set_charge_limit(vin, args.value)
    elif cmd == "charge-schedule":
        result = client.set_charge_schedule(
            vin,
            enabled=bool(args.enable),
            soc_limit=args.soc,
            start_time=args.start,
            end_time=args.end,
            cycles=args.cycles,
            circulation=args.circulation,
            recharge=args.recharge,
        )
    elif cmd == "healthy-charging-on":
        result = client.healthy_charging_on(vin)
    elif cmd == "healthy-charging-off":
        result = client.healthy_charging_off(vin)

    # Battery
    elif cmd == "battery-preheat":
        result = client.battery_preheat(vin)
    elif cmd == "battery-preheat-off":
        result = client.battery_preheat_off(vin)

    # Climate
    elif cmd == "ac-on":
        params: dict[str, str] = {}
        if args.temp:
            params["temperature"] = args.temp
        if args.mode:
            params["mode"] = args.mode
        if args.wind:
            params["windlevel"] = args.wind
        result = verify_ac_command(client, vin, args.wait, lambda: client.ac_on(vin, params=params or None))
    elif cmd == "ac-off":
        result = verify_ac_command(client, vin, args.wait, lambda: client.ac_off(vin))
    elif cmd == "ac-schedule":
        device_id = "example"
        now_ms = str(int(time.time() * 1000))
        days_list = [int(d) for d in args.days.split(",") if d.strip()] if args.days else []
        control = {
            "mode": args.mode,
            "on": "0" if args.off else "1",
            "operate": "manual",
            "set_id": f"air_set{device_id}{now_ms}",
            "start_time": args.start_time,
            "temperature": args.temp,
            "update_time": now_ms,
            "windlevel": args.wind,
            "days": days_list,
            "circle": args.circle,
            "position": "all",
            "wshld": "0",
        }
        result = client.set_climate_schedule(vin, controls=[control])
    elif cmd == "quick-cool":
        result = client.quick_cool(vin)
    elif cmd == "quick-heat":
        result = client.quick_heat(vin)
    elif cmd == "defrost":
        result = client.windshield_defrost(vin)
    elif cmd == "ac-schedule-cancel":
        result = client.cancel_climate_schedule(vin)
    elif cmd == "ac-schedule-list":
        import json as _json

        schedules = client.get_climate_schedule(vin)
        if not schedules:
            print("No active climate schedules.")
        else:
            print(f"{len(schedules)} climate schedule(s):")
            print(_json.dumps(schedules, indent=2))
        return
    elif cmd == "ptc-schedule-list":
        import json as _json

        schedules = client.get_ptc_heating_schedule(vin)
        if not schedules:
            print("No active PTC heating schedules.")
        else:
            print(f"{len(schedules)} PTC schedule(s):")
            print(_json.dumps(schedules, indent=2))
        return
    elif cmd == "charge-schedule-list":
        import json as _json

        schedule = client.get_charge_schedule(vin)
        if not schedule:
            print("No charge schedule set.")
        else:
            print("Charge schedule:")
            print(_json.dumps(schedule, indent=2))
        return
    elif cmd == "prepare-car-schedule-list":
        import json as _json

        schedules = client.get_prepare_car_schedule(vin)
        if not schedules:
            print("No active prepare-car schedules.")
        else:
            print(f"{len(schedules)} prepare-car schedule(s):")
            print(_json.dumps(schedules, indent=2))
        return
    elif cmd == "fota-schedule-list":
        import json as _json

        schedules = client.get_fota_schedule(vin)
        if not schedules:
            print("No active FOTA schedules.")
        else:
            print(f"{len(schedules)} FOTA schedule(s):")
            print(_json.dumps(schedules, indent=2))
        return

    # Sentry
    elif cmd == "sentry-on":
        result = client.sentry_mode_on(vin)
    elif cmd == "sentry-off":
        result = client.sentry_mode_off(vin)

    # Windows
    elif cmd == "open-windows":
        result = client.open_windows(vin, value=args.value)
    elif cmd == "close-windows":
        result = client.close_windows(vin, value=args.value)

    # Sunroof
    elif cmd == "open-sunroof":
        result = client.open_sunroof(vin)
    elif cmd == "close-sunroof":
        result = client.close_sunroof(vin)

    # Sunshade
    elif cmd == "open-sunshade":
        result = client.open_sunshade(vin, value=args.value)
    elif cmd == "close-sunshade":
        result = client.close_sunshade(vin, value=args.value)

    # Seats
    elif cmd == "seat-heat":
        result = client.seat_heat(vin, position=args.position, level=args.level)
    elif cmd == "seat-vent":
        result = client.seat_ventilation(vin, position=args.position, level=args.level)

    # Steering wheel
    elif cmd == "steering-heat-on":
        result = client.steering_wheel_heat_on(vin)
    elif cmd == "steering-heat-off":
        result = client.steering_wheel_heat_off(vin)

    # Mirrors
    elif cmd == "mirror-heat-on":
        result = client.rearview_mirror_heat_on(vin)
    elif cmd == "mirror-heat-off":
        result = client.rearview_mirror_heat_off(vin)

    # Fuel heating
    elif cmd == "fuel-heat-on":
        result = client.fuel_heating_on(vin)
    elif cmd == "fuel-heat-off":
        result = client.fuel_heating_off(vin)

    # ON3
    elif cmd == "on3-on":
        result = client.on3_on(vin)
    elif cmd == "on3-off":
        result = client.on3_off(vin)

    # Speed limit
    elif cmd == "speed-limit":
        result = client.set_speed_limit(vin, value=args.value)

    # Navigation
    elif cmd == "send-destination":
        result = client.send_destination(
            vin,
            address=args.address,
            address_name=args.name,
            latitude=args.lat,
            longitude=args.lon,
        )

    if result is not None:
        print(f"OK: {result}")


def main() -> None:
    if not USERNAME or not PASSWORD:
        print("ERROR: Set LEAPMOTOR_USERNAME and LEAPMOTOR_PASSWORD environment variables.")
        sys.exit(1)

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    client = LeapmotorApiClient(
        username=USERNAME,
        password=PASSWORD,
        app_cert_path=APP_CERT_PATH,
        app_key_path=APP_KEY_PATH,
        operation_password=OPERATION_PIN,
        account_p12_password=ACCOUNT_P12_PASSWORD,
    )

    try:
        print("Logging in...")
        client.login()
        print(f"Logged in as user_id={client.user_id}\n")

        vin = get_vin(client, args.vin)
        print(f"Sending command: {args.command}")
        print("-" * 40)
        execute_command(client, vin, args)
    finally:
        client.close()


if __name__ == "__main__":
    main()
