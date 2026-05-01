"""Connect to Leapmotor servers and display status."""

import os
import sys

from leapmotor_api.client import LeapmotorApiClient

# --- Credentials from environment variables ---
USERNAME = os.environ.get("LEAPMOTOR_USERNAME", "")
PASSWORD = os.environ.get("LEAPMOTOR_PASSWORD", "")
APP_CERT_PATH = os.environ.get("LEAPMOTOR_APP_CERT", "certs/app_cert.pem")
APP_KEY_PATH = os.environ.get("LEAPMOTOR_APP_KEY", "certs/app_key.pem")
OPERATION_PIN = os.environ.get("LEAPMOTOR_PIN", None)
ACCOUNT_P12_PASSWORD = os.environ.get("LEAPMOTOR_P12_PASSWORD", None)

if not USERNAME or not PASSWORD:
    print("ERROR: Set LEAPMOTOR_USERNAME and LEAPMOTOR_PASSWORD environment variables.")
    sys.exit(1)


def main() -> None:
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

        vehicles = client.get_vehicle_list()
        if not vehicles:
            print("No vehicles found.")
            return

        for vehicle in vehicles:
            print("=" * 60)
            print(f"Vehicle: {vehicle.vehicle_nickname}")
            print(f"  VIN: {vehicle.vin}")
            print(f"  Car ID: {vehicle.car_id}")
            print(f"  Plate: {vehicle.plate_number}")
            print(f"  Type: {vehicle.car_type}")
            print(f"  Year: {vehicle.year}")
            print(f"  Color: {vehicle.out_color}")
            print(f"  Seat layout: {vehicle.seat_layout}")
            print(f"  Rudder: {vehicle.rudder}")

            print("-" * 60)
            print(f"User: {vehicle.user_nickname}")
            print(f"  Mobile: {vehicle.mobile_number}")
            print(f"  Email: {vehicle.email}")
            print(f"  Allocation code: {vehicle.allocation_code}")

            print("-" * 60)
            print(f"Shared: {vehicle.is_shared}")
            if vehicle.is_shared:
                print(f"  Share time: {vehicle.share_time}")
                print(f"  Expire time: {vehicle.expire_time}")
                print(f"  Duration type: {vehicle.duration_type}")

            print("-" * 60)
            print("Other:")
            print(f"  Rights: {vehicle.rights}")
            print(f"  Abilities: {', '.join(vehicle.abilities) if vehicle.abilities else 'None'}")
            print(f"  Module rights: {vehicle.module_rights}")

            print("=" * 60)

            vs = client.get_vehicle_status(vehicle)

            print("\n  [Battery & Charging]")
            print(f"    SOC:                    {vs.battery.soc}%")
            print(f"    Current:                {vs.battery.battery_current} A")
            print(f"    Voltage:                {vs.battery.battery_voltage} V")
            print(f"    Battery power:          {vs.battery.battery_power} kW")
            print(f"    Charging power:         {vs.battery.charging_power_kw} kW")
            print(f"    Discharging power:      {vs.battery.discharging_power_kw} kW")
            print(f"    is_charging (batt):     {vs.battery.is_charging}")
            print(f"    is_discharging (batt):  {vs.battery.is_discharging}")
            print(f"    Charge remain time:     {vs.battery.charge_remain_time} min")
            print(f"    Charge state:           {vs.battery.charge_state}")
            print(f"    Expected mileage:       {vs.battery.expected_mileage} km")

            print("\n  [Driving]")
            print(f"    Speed:                  {vs.driving.speed}")
            print(f"    Gear:                   {vs.driving.gear_status}")
            print(f"    is_parked:              {vs.is_parked}")

            print("\n  [Combined status]")
            print(f"    is_charging:            {vs.is_charging}")
            print(f"    is_regening:            {vs.is_regening}")
            print(f"    is_locked:              {vs.is_locked}")

            print("\n  [Location]")
            print(f"    Latitude:               {vs.location.latitude}")
            print(f"    Longitude:              {vs.location.longitude}")

            print()

        # --- Messages ---
        print("\n" + "=" * 60)
        print("MESSAGES")
        print("=" * 60)

        unread = client.get_unread_message_count()
        print(f"Unread messages: {unread}\n")

        message_list = client.get_message_list(page_no=1, page_size=10)
        print(f"Total messages: {message_list.count}")
        for msg in message_list.messages:
            status = "READ" if msg.is_read else "UNREAD"
            print(f"  [{status}] {msg.title} (type={msg.msg_type})")
            print(f"    {msg.message}")
            print(f"    Time: {msg.send_datetime}")
            print()

    finally:
        client.close()


if __name__ == "__main__":
    main()
