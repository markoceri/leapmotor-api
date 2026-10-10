# Examples

Example scripts for interacting with the Leapmotor API.

## Prerequisites

1. Install the `leapmotor_api` package (from the project root):

   ```bash
   pip install -e .
   ```

2. Set the environment variables with your credentials:

   ```bash
   export LEAPMOTOR_USERNAME="your_username"
   export LEAPMOTOR_PASSWORD="your_password"
   export LEAPMOTOR_PIN="your_operation_pin"
   ```

3. (Optional) If the certificates are not in the default location (`certs/`):

   ```bash
   export LEAPMOTOR_APP_CERT="/path/to/app_cert.pem"
   export LEAPMOTOR_APP_KEY="/path/to/app_key.pem"
   export LEAPMOTOR_P12_PASSWORD="p12_password"
   ```

## Environment variables

| Variable                 | Required | Default               | Description                        |
| ------------------------ | -------- | --------------------- | ---------------------------------- |
| `LEAPMOTOR_USERNAME`     | Yes      | —                     | Leapmotor account username         |
| `LEAPMOTOR_PASSWORD`     | Yes      | —                     | Account password                   |
| `LEAPMOTOR_PIN`          | Yes*     | —                     | Operation PIN for remote commands  |
| `LEAPMOTOR_APP_CERT`     | No       | `certs/app_cert.pem`  | Path to the app certificate        |
| `LEAPMOTOR_APP_KEY`      | No       | `certs/app_key.pem`   | Path to the app key                |
| `LEAPMOTOR_P12_PASSWORD` | No       | —                     | Account P12 certificate password   |

\* Required for all remote commands except `send-destination`.

---

## usage.py — Vehicle status

Displays all available information: vehicle data, battery, climate, location, tires, messages, consumption and charging history.

```bash
python examples/usage.py
```

Information displayed:

- **Vehicle** — name, VIN, plate, type, year, color, seat layout, rudder
- **Battery & charging** — SOC, current, voltage, power, charge state, schedule
- **Driving** — speed, gear, vehicle state, remaining range, parking brake
- **Climate** — AC, interior/outdoor temperature, mode, ventilation, defrost
- **Seats & comfort** — seat heating/ventilation, steering wheel heating
- **Security** — alarm, sentry mode, mirror heating, roof
- **Location** — latitude, longitude
- **Tires** — pressure for each wheel
- **Consumption** — weekly breakdown and ranking
- **Messages** — unread count and message list
- **Charging** — daily detail for the last 30 days

---

## commands.py — Remote commands

Send remote commands to the vehicle via CLI. Uses the first vehicle on the account unless a VIN is specified with `--vin`.

```bash
python examples/commands.py <command> [arguments]
```

To see all available commands:

```bash
python examples/commands.py --help
```

### Available commands

#### Lock & unlock

```bash
python examples/commands.py lock
python examples/commands.py unlock
python examples/commands.py unlock-charger
```

#### Trunk

```bash
python examples/commands.py open-trunk
python examples/commands.py close-trunk
```

#### Search & connectivity

```bash
python examples/commands.py find              # horn + lights flash
python examples/commands.py hotspot
python examples/commands.py autopark
```

#### Charging

```bash
python examples/commands.py start-charging
python examples/commands.py stop-charging
python examples/commands.py charge-limit 80            # SOC limit in percent
python examples/commands.py charge-schedule 23:00 07:00 1,2,3,4,5,6,7  # start end cycles
python examples/commands.py charge-schedule 23:00 07:00 1,2,3,4,5,6,7 --enable 1 --soc 80 --circulation 1
python examples/commands.py healthy-charging-on
python examples/commands.py healthy-charging-off
```

#### Battery

```bash
python examples/commands.py battery-preheat
python examples/commands.py battery-preheat-off
```

#### Climate

```bash
python examples/commands.py ac-on                              # turn AC on with defaults
python examples/commands.py ac-on --temp 22 --mode cold --wind 3
python examples/commands.py ac-off                             # turn AC off
python examples/commands.py ac-off --wait 15                   # re-read acSwitch after 15 s
python examples/commands.py ac-off --wait 0                    # send only, no status check
python examples/commands.py quick-cool
python examples/commands.py quick-heat
python examples/commands.py defrost                            # windshield defrost
python examples/commands.py ac-schedule '2026-05-16 07:30:00' --temp 22 --mode cold --days 1,2,3,4,5
python examples/commands.py ac-schedule '2026-05-17 06:00:00' --temp 28 --mode hot  # once
python examples/commands.py ac-schedule-cancel                 # cancel all schedules
python examples/commands.py ac-schedule-list                   # list active schedules
```

`ac-on` and `ac-off` print `acSwitch` from the vehicle status before the command and again after `--wait` seconds (default 8). The cloud answers `code=0` even to commands the car ignores, so the change in `acSwitch` is the real result.

#### Sentry mode

```bash
python examples/commands.py sentry-on
python examples/commands.py sentry-off
```

#### Windows

```bash
python examples/commands.py open-windows            # fully open
python examples/commands.py open-windows 50          # position 0-100
python examples/commands.py close-windows
```

#### Sunroof & sunshade

```bash
python examples/commands.py open-sunroof
python examples/commands.py close-sunroof
python examples/commands.py open-sunshade            # fully open
python examples/commands.py open-sunshade 5           # position 0-10
python examples/commands.py close-sunshade
```

#### Seats

Positions: `1`=left front, `2`=copilot, `3`=driver, `4`=right front, `5`=left rear, `6`=right rear

Levels: `0`=off, `1`=low, `2`=medium, `3`=high

```bash
python examples/commands.py seat-heat 3 2            # driver, medium heating
python examples/commands.py seat-vent 3 1            # driver, low ventilation
```

#### Steering wheel & mirror heating

```bash
python examples/commands.py steering-heat-on
python examples/commands.py steering-heat-off
python examples/commands.py mirror-heat-on
python examples/commands.py mirror-heat-off
```

#### Fuel heating

```bash
python examples/commands.py fuel-heat-on
python examples/commands.py fuel-heat-off
```

#### ON3 mode

```bash
python examples/commands.py on3-on
python examples/commands.py on3-off
```

#### Speed limit

```bash
python examples/commands.py speed-limit 120          # km/h
```

#### Navigation

```bash
python examples/commands.py send-destination "Via Roma 1, Milano" "Casa" 45.4642 9.1900
```

### Selecting a specific vehicle

If the account has multiple vehicles, specify the VIN with `--vin`:

```bash
python examples/commands.py --vin LVTMA1234AB567890 lock
```
