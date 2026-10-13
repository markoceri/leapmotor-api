"""Connect to Leapmotor servers and display status."""

import os
import sys
from datetime import date, timedelta

from leapmotor_api.client import LeapmotorApiClient
from leapmotor_api.exceptions import LeapmotorPermissionError

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
            print(f"  Rights: {', '.join(f'{r.name}({r.value})' for r in vehicle.rights) or 'None'}")
            print(f"  Abilities: {', '.join(f'{a.name}({a.value})' for a in vehicle.abilities) or 'None'}")
            print(f"  Module rights: {', '.join(f'{m.name}({m.value})' for m in vehicle.module_rights) or 'None'}")

            print("=" * 60)

            vs = client.get_vehicle_status(vehicle)

            print("\n  [Battery & Charging]")
            print(f"    SOC:                    {vs.battery.soc}%")
            print(f"    Precise SOC:            {vs.battery.precise_soc}%")
            print(f"    Current:                {vs.battery.battery_current} A")
            print(f"    Voltage:                {vs.battery.battery_voltage} V")
            print(f"    Battery power:          {vs.battery.battery_power} kW")
            print(f"    Charging power:         {vs.battery.charging_power_kw} kW")
            print(f"    Discharging power:      {vs.battery.discharging_power_kw} kW")
            print(f"    is_charging (batt):     {vs.battery.is_charging}")
            print(f"    is_discharging (batt):  {vs.battery.is_discharging}")
            print(f"    Charge remain time:     {vs.battery.charge_remain_time} min")
            print(f"    Charge state:           {vs.battery.charge_state}")
            print(f"    AC input (slow):        {vs.battery.ac_input_slow_charge}")
            print(f"    DC input (fast):        {vs.battery.dc_input_fast_charge}")
            print(f"    Slow gun inserted:      {vs.battery.is_charge_slow_gun_insert}")
            print(f"    Fast gun inserted:      {vs.battery.is_charge_fast_gun_insert}")
            print(f"    Charge completed:       {vs.battery.charge_completed}")
            print(f"    Expected mileage:       {vs.battery.expected_mileage} km")
            print(f"    Min battery temp:       {vs.battery.min_battery_temp}")
            print(f"    Battery thermal req:    {vs.battery.battery_thermal_request}")
            print(f"    Healthy charge:         {vs.battery.healthy_charge_enabled}")
            print(f"    Schedule enabled:       {vs.battery.charge_plan.enabled}")
            print(f"    Schedule start:         {vs.battery.charge_plan.start}")
            print(f"    Schedule end:           {vs.battery.charge_plan.end}")
            print(f"    Schedule cycles:        {vs.battery.charge_plan.cycles}")
            print(f"    Schedule circulation:   {vs.battery.charge_plan.circulation}")
            print(f"    Schedule cancelled:     {vs.battery.charge_plan.cancelled_once}")
            print(f"    Expected fuel range:    {vs.battery.expected_fuel_mileage} km")
            print(f"    Expected combined range:{vs.battery.expected_combined_mileage} km")

            print("\n  [Driving]")
            print(f"    Speed:                  {vs.driving.speed}")
            print(f"    Gear:                   {vs.driving.gear_status}")
            print(f"    Vehicle state:          {vs.driving.vehicle_state}")
            print(f"    is_parked:              {vs.is_parked}")
            print(f"    Speed limit:            {vs.driving.speed_limit}")
            print(f"    Speed limit unit:       {vs.driving.speed_limit_unit}")
            print(f"    Speed limit active:     {vs.driving.speed_limit_active}")
            print(f"    Live remaining range:   {vs.driving.live_remaining_range}")
            print(f"    Max range:              {vs.driving.max_range}")
            print(f"    Max fuel range:         {vs.driving.max_fuel_range}")
            print(f"    Max combined range:     {vs.driving.max_combined_range}")
            print(f"    Range mode:             {vs.driving.range_mode}")
            print(f"    Parking brake:          {vs.driving.parking_brake_state}")

            print("\n  [Combined status]")
            print(f"    is_plugged:             {vs.is_plugged}")
            print(f"    is_charging:            {vs.is_charging}")
            print(f"    is_regening:            {vs.is_regening}")
            print(f"    is_locked:              {vs.is_locked}")

            print("\n  [Climate]")
            print(f"    AC switch:              {vs.climate.ac_switch}")
            print(f"    AC setting:             {vs.climate.ac_setting}")
            print(f"    AC setting right:       {vs.climate.ac_setting_right}")
            print(f"    Interior temp:          {vs.climate.interior_temp}")
            print(f"    Outdoor temp:           {vs.climate.outdoor_temp}")
            print(f"    AC operate mode:        {vs.climate.ac_operate_mode}")
            print(f"    AC air volume:          {vs.climate.ac_air_volume}")
            print(f"    AC air volume setting:  {vs.climate.ac_air_volume_setting}")
            print(f"    AC wind direction:      {vs.climate.ac_wind_direction}")
            print(f"    AC temp mode:           {vs.climate.ac_temp_mode}")
            print(f"    AC circle mode:         {vs.climate.ac_circle_mode}")
            print(f"    AC cooling/heating:     {vs.climate.ac_cooling_and_heating}")
            print(f"    Recirculation mode:     {vs.climate.recirculation_mode}")
            print(f"    Windshield defrost:     {vs.climate.windshield_defrost}")
            print(f"    Defrost active:         {vs.climate.is_windshield_defrost_active}")
            print(f"    Rear window heating:    {vs.climate.rear_window_heating}")
            print(f"    Climate mode:           {vs.climate.climate_mode}")
            print(f"    Rapid cooling:          {vs.climate.rapid_cooling}")
            print(f"    Rapid heating:          {vs.climate.rapid_heating}")
            print(f"    Min single temp:        {vs.climate.min_single_temp}")
            print(f"    PTC state:              {vs.climate.ptc_state}")
            print(f"    PTC power setting:      {vs.climate.ptc_power_setting_value}")

            print("\n  [Seat & Comfort]")
            print(f"    Driver seat heating:    {vs.seat_comfort.driver_seat_heating}")
            print(f"    Driver seat vent:       {vs.seat_comfort.driver_seat_ventilation}")
            print(f"    Passenger seat heating: {vs.seat_comfort.passenger_seat_heating}")
            print(f"    Passenger seat vent:    {vs.seat_comfort.passenger_seat_ventilation}")
            print(f"    Steering wheel heating: {vs.seat_comfort.steering_wheel_heating}")
            print(f"    Steering heater mins:   {vs.seat_comfort.steering_wheel_heater_minutes}")

            print("\n  [Security]")
            print(f"    Security active:        {vs.security.vehicle_security_active}")
            print(f"    is_security_active:     {vs.security.is_security_active}")
            print(f"    Sentry mode:            {vs.security.sentry_mode}")
            print(f"    Left mirror heating:    {vs.security.left_mirror_heating}")
            print(f"    Right mirror heating:   {vs.security.right_mirror_heating}")
            print(f"    Roof opening:           {vs.security.roof_opening}")

            print("\n  [Location]")
            print(f"    Latitude:               {vs.location.latitude}")
            print(f"    Longitude:              {vs.location.longitude}")

            print("\n  [Tires]")
            print(f"    Front left pressure:    {vs.tires.front_left_kpa} kPa")
            print(f"    Front right pressure:   {vs.tires.front_right_kpa} kPa")
            print(f"    Rear left pressure:     {vs.tires.rear_left_kpa} kPa")
            print(f"    Rear right pressure:    {vs.tires.rear_right_kpa} kPa")

            print("\n  [Statistics]")
            breakdown = client.get_consumption_last_week_breakdown(vehicle)
            print(f"    Driver EC:              {breakdown.driver_ec} kWh")
            print(f"    AC EC:                  {breakdown.ac_ec} kWh")
            print(f"    Other EC:               {breakdown.other_ec} kWh")
            print(f"    Total EC:               {breakdown.total_ec} kWh")

            weekly_rank = client.get_consumption_weekly_rank(vehicle)
            print(f"    Rank:                   {weekly_rank.rank.rank}")
            print(f"    Avg consumption:        {weekly_rank.rank.hundred_km_ec} kWh/100km")
            print(f"    Avg consumption (mi):   {weekly_rank.rank.hundred_mi_kwh_ec} kWh/100mi")
            for wc in weekly_rank.weekly:
                print(f"    Week {wc.week_start} ~ {wc.week_end}: {wc.hundred_km_ec} kWh/100km")

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

        # --- Software (OTA) ---
        print("\n" + "=" * 60)
        print("SOFTWARE")
        print("=" * 60)

        for vehicle in vehicles:
            try:
                software = client.get_software_info(vehicle)
            except LeapmotorPermissionError:
                print(f"  {vehicle.vin}: not available (only the owner account sees the software version)")
                continue
            current = software.current_version.version if software.current_version else None
            print(f"  {vehicle.vin}: installed {current}")
            if software.new_version:
                new = software.new_version
                size_mb = new.download_size / 1e6
                print(f"    Update available: {new.version} ({size_mb:.0f} MB, {len(new.packages)} packages)")
                for note in new.release_notes_for("en-US"):
                    print(f"    - {note.title}: {note.content}")
            else:
                print("    Up to date")

        # --- Charging Daily Detail ---
        print("\n" + "=" * 60)
        print("CHARGING DAILY DETAIL")
        print("=" * 60)

        end = date.today()
        start = date.today() - timedelta(days=30)
        for vehicle in vehicles:
            print(f"\nVehicle: {vehicle.vehicle_nickname} ({vehicle.vin})")
            print(f"  Period: {start} ~ {end}")
            charging_detail = client.get_charging_daily_detail(
                vehicle.vin, start_time=start, end_time=end, timezone="GMT+01:00", page_num=1, page_size=50
            )

            if not charging_detail.records:
                print("  No charging records found.")
                continue

            for record in charging_detail.records:
                charge_kind = "DC (fast)" if record.is_fast_charge else "AC (normal)"
                print(f"  {record.start_datetime} -> {record.end_datetime}  {charge_kind}  {record.energy_kwh} kWh")

    finally:
        client.close()


if __name__ == "__main__":
    main()
