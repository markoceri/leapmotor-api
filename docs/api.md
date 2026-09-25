# Leapmotor Cloud API Reference

Technical documentation of the endpoints, cryptography and remote commands
used by the `leapmotor-api` library.

> **Base URL:** `https://appgateway.leapmotor-international.de`
>
> All endpoints require **mutual TLS** (client certificate).
> Server certificates are self-signed: SSL verification is disabled by default.

---

## Table of Contents

- [Authentication](#authentication)
  - [Login](#login)
  - [Token Refresh](#token-refresh)
  - [Certificates](#certificates)
- [Cryptography and Signatures](#cryptography-and-signatures)
  - [Login Signature (SHA-256)](#login-signature-sha-256)
  - [HMAC Signature (authenticated requests)](#hmac-signature-authenticated-requests)
  - [Sign Key Derivation (HKDF)](#sign-key-derivation-hkdf)
  - [PKCS#12 Password (SM4)](#pkcs12-password-sm4)
  - [Vehicle PIN Encryption (AES-128-CBC)](#vehicle-pin-encryption-aes-128-cbc)
- [Read-Only Endpoints](#read-only-endpoints)
  - [Vehicle List](#vehicle-list)
  - [Vehicle Status](#vehicle-status)
  - [Mileage and Energy](#mileage-and-energy)
  - [Weekly Energy Consumption and Ranking](#weekly-energy-consumption-and-ranking)
  - [Last Week Energy Breakdown](#last-week-energy-breakdown)
  - [Vehicle Image](#vehicle-image)
  - [Image Package Download](#image-package-download)
  - [Message List](#message-list)
  - [Unread Message Count](#unread-message-count)
  - [Share Invitations](#share-invitations)
  - [Share Invitation Answer](#share-invitation-answer)
  - [Charging Daily Detail](#charging-daily-detail)
- [Remote Control Endpoints](#remote-control-endpoints)
  - [Certificate Sync](#certificate-sync)
  - [Operation PIN Verification](#operation-pin-verification)
  - [Remote Command Execution](#remote-command-execution)
  - [Result Polling](#result-polling)
- [Remote Commands](#remote-commands)
  - [Lock / Unlock (cmd_id=110)](#lock--unlock-cmd_id110)
  - [Find Car (cmd_id=120)](#find-car-cmd_id120)
  - [Trunk (cmd_id=130)](#trunk-cmd_id130)
  - [Hotspot (cmd_id=140)](#hotspot-cmd_id140)
  - [Autopark (cmd_id=150)](#autopark-cmd_id150)
  - [Battery Preheat (cmd_id=160)](#battery-preheat-cmd_id160)
  - [Sentry Mode (cmd_id=220)](#sentry-mode-cmd_id220)
  - [Climate (cmd_id=170)](#climate-cmd_id170)
  - [Send Destination (cmd_id=180)](#send-destination-cmd_id180)
  - [Set Charge Plan (cmd_id=190)](#set-charge-plan-cmd_id190)
  - [Unlock Charger (cmd_id=192)](#unlock-charger-cmd_id192)
  - [Start / Stop Charging (cmd_id=193)](#start--stop-charging-cmd_id193)
  - [Steering Wheel Heat (cmd_id=320)](#steering-wheel-heat-cmd_id320)
  - [Fuel Heating (cmd_id=380)](#fuel-heating-cmd_id380)
  - [ON3 (cmd_id=410)](#on3-cmd_id410)
  - [Rearview Mirror Heat (cmd_id=440)](#rearview-mirror-heat-cmd_id440)
  - [Healthy Charging (cmd_id=480)](#healthy-charging-cmd_id480)
  - [Speed Limit (cmd_id=510)](#speed-limit-cmd_id510)
  - [Seat Heat (cmd_id=301)](#seat-heat-cmd_id301)
  - [Seat Ventilation (cmd_id=370)](#seat-ventilation-cmd_id370)
  - [Sunroof (cmd_id=300)](#sunroof-cmd_id300)
  - [Windows (cmd_id=230)](#windows-cmd_id230)
  - [Sunshade (cmd_id=240)](#sunshade-cmd_id240)

---

## Authentication

### Login

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/acct/v1/login` |
| **Cert** | App certificate (`app_cert.pem` + `app_key.pem`) |
| **Content-Type** | `application/x-www-form-urlencoded; charset=UTF-8` |
| **Signature** | SHA-256 (see [Login Signature](#login-signature-sha-256)) |

**Form body:**

| Parameter | Value |
|---|---|
| `email` | Username (email) |
| `password` | Account password |
| `loginMethod` | `1` |
| `policyId` | `20260204` |
| `isRecoverAcct` | `0` |

**Response (data):**

| Field | Description |
|---|---|
| `id` | User ID (used as `userId` in subsequent requests) |
| `token` | JWT access token |
| `refreshToken` | Token for refresh |
| `signIkm` | Input Key Material for HKDF |
| `signSalt` | Salt for HKDF |
| `signInfo` | Info for HKDF |
| `base64Cert` | Account certificate in PKCS#12 format, Base64-encoded |
| `uid` | UID for P12 password derivation |

After login, the `deviceId` is extracted from the JWT token payload
(`user_name.split(",")[2]`).

### Token Refresh

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/acct/v1/token/refresh` |
| **Cert** | Account certificate |
| **Signature** | HMAC-SHA256 (with `refreshToken` in body_params) |

**Form body:**

| Parameter | Value |
|---|---|
| `refreshToken` | Refresh token obtained from login |

**Response (data):**

| Field | Description |
|---|---|
| `token` | New access token |
| `refreshToken` | New refresh token |

### Certificates

The system uses **two levels of certificates**:

1. **App certificate** (`app_cert.pem`, `app_key.pem`) — Static application
   certificate, used for login and remote certificate sync.
   Not included in the repository.

2. **Account certificate** — Received in the login response as Base64
   PKCS#12 (`base64Cert`). Decoded with a derived password
   (see [PKCS#12 Password](#pkcs12-password-sm4)) and used as client cert
   for all subsequent authenticated requests.

---

## Cryptography and Signatures

### Login Signature (SHA-256)

Used **only** for the login request. The signature is a SHA-256 hash of
the concatenation of the following fields (in this order):

```
language + deviceType + deviceId + "1" + username + "0" + "1" + nonce + password + "20260204" + source + timestamp + version
```

| Field | Default value |
|---|---|
| `language` | `en-GB` |
| `deviceType` | `1` |
| `source` | `leapmotor` |
| `version` | `1.12.3` |
| `channel` | `1` |

### HMAC Signature (authenticated requests)

All requests after login use **HMAC-SHA256** with the sign key
derived via HKDF. The signature input varies by endpoint:

**Standard signature (build_signed_headers):**

The input is the concatenation of all field **values** (headers + optional
body params), sorted **alphabetically by key**:

```
acceptLanguage + channel + deviceId + deviceType + nonce + source + timestamp + version [+ vin] [+ body_params...]
```

**Car picture key signature:**

```
language + channel + deviceId + deviceId + deviceType + nonce + source + timestamp + version + vin
```

> Note: `deviceId` appears **twice**.

**Car picture package signature:**

```
language + channel + deviceId + deviceType + pictureKey + nonce + source + timestamp + version
```

**operatePassword verify signature:**

```
language + channel + deviceId + deviceType + nonce + operatePassword + source + timestamp + version + vin
```

**Remote control write signature (with PIN):**

```
language + channel + cmdContent + cmdId + deviceId + deviceType + nonce + operatePassword + source + timestamp + version + vin
```

**Remote control write signature (without PIN):**

```
language + channel + cmdContent + cmdId + deviceId + deviceType + nonce + source + timestamp + version + vin
```

**Remote control result query signature:**

```
language + channel + deviceId + deviceType + nonce + remoteCtlId + source + timestamp + version
```

### Sign Key Derivation (HKDF)

The HMAC key is derived using **HKDF-SHA256**:

| Parameter | Source |
|---|---|
| IKM (Input Key Material) | `signIkm` from login response |
| Salt | `signSalt` from login response |
| Info | `signInfo` from login response |
| Length | 32 bytes |

### PKCS#12 Password (SM4)

The password for decrypting the account PKCS#12 certificate is derived as follows:

1. `cn = MD5(account_id)` — hexadecimal hash
2. `app_input = cn + cn[::2] + uid[1::2]` — concatenation with slicing
3. `digest = SHA-256(app_input)` — binary hash (32 bytes)
4. `encoded = SM4_ECB_encrypt(digest)` — encryption with static round keys
5. `password = Base64(encoded[:12])[:15]` — first 12 bytes encoded, truncated to 15 characters

The SM4 algorithm uses pre-computed hardcoded round keys (not a dynamic key).

### Vehicle PIN Encryption (AES-128-CBC)

The operation PIN (`operatePassword`) is encrypted with **AES-128-CBC**:

1. Key and IV are derived from the session token:
   - `key = MD5(token[0:32])[8:24]` — 16 characters (128 bits)
   - `iv = MD5(token[32:64])[8:24]` — 16 characters (128 bits)
2. The PIN is padded with **PKCS#7** (128-bit block)
3. The result is encoded in **Base64**

If the token is absent or too short (< 64 chars), hardcoded fallback
values are used.

---

## Read-Only Endpoints

All read-only endpoints use:
- **Method:** POST
- **Content-Type:** `application/x-www-form-urlencoded`
- **Cert:** Account certificate
- **Signature:** HMAC-SHA256 (standard)
- **Additional headers:** `userId`, `token`

### Vehicle List

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/vehicle/v1/list` |
| **Body** | (empty) |

**Response (data):**

| Field | Type | Description |
|---|---|---|
| `bindcars` | `list` | Owned vehicles |
| `sharedcars` | `list` | Shared vehicles |

Each vehicle contains: `vin`, `carId`, `carType`, `nickName`, `vinNickname`,
`email`, `plateNumber`, `mobileNumber`, `outColor`, `year`, `abilities`,
`rightList`, `moduleRights`, `allocationCode`, `seatLayout`, `rudder`,
`shareTime`, `expireTime`, `durationType`.

### Vehicle Status

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/vehicle/v1/status/get/{car_type}` |
| **Body** | `vin={VIN}` |
| **Signature** | HMAC-SHA256 (with `vin` in the input) |

The `{car_type}` segment is the vehicle's `carType` in lowercase (e.g. `t03`,
`c10`). **B10** uses the **C10** path (`/status/get/c10`).

The response format varies by model — see [docs/vehicles.md](vehicles.md).

### Mileage and Energy

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/drivingRecord/v1/mileage/energy/detail` |
| **Body** | `vin={VIN}` |

**Response (data):**

| Field | Description |
|---|---|
| `totalmileage` | Total mileage (km) |
| `totalmileageMile` | Total mileage (miles) |
| `deliveryDays` | Days since delivery |

### Weekly Energy Consumption and Ranking

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/drivingRecord/v1/getLastNweeks100kmECAndRank` |
| **Body** | `carvin={VIN}` |
| **Signature** | HMAC-SHA256 (with `carvin` in body_params) |

**Response (data):**

| Field | Description |
|---|---|
| `rankResult.result` | Rank result code (0 = OK) |
| `rankResult.rank` | Percentile rank (e.g. `"0%"`) |
| `rankResult.hundredKmEC` | Average consumption (kWh/100 km) |
| `rankResult.hundredMiKwhEC` | Average consumption (kWh/100 mi) |
| `weeklyEC[].weekStart` | Week start date (`YYYY-MM-DD`) |
| `weeklyEC[].weekEnd` | Week end date (`YYYY-MM-DD`) |
| `weeklyEC[].hundredKmEC` | Consumption that week (kWh/100 km) |
| `weeklyEC[].hundredMiKwhEC` | Consumption that week (kWh/100 mi) |
| `weeklyEC[].xWeekStart` | Week start timestamp (ms) |
| `weeklyEC[].xWeekEnd` | Week end timestamp (ms) |

**Typed model:** `ConsumptionWeeklyRank` (contains `ConsumptionRank` + `list[WeeklyConsumption]`)

### Last Week Energy Breakdown

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/drivingRecord/v1/getLastweekEC` |
| **Body** | `endtime={epoch_s}&begintime={epoch_s}&carvin={VIN}` |
| **Signature** | HMAC-SHA256 (with `endtime`, `begintime`, `carvin` in body_params) |

The `begintime` / `endtime` parameters are Unix epoch seconds delimiting
the previous calendar week (Monday 00:00 → Sunday 23:59:59 UTC).

**Response (data):**

| Field | Description |
|---|---|
| `driverEC` | Driving energy consumption (kWh, string) |
| `acEC` | Air conditioning energy consumption (kWh, string) |
| `otherEC` | Other systems energy consumption (kWh, string) |

**Typed model:** `ConsumptionLastWeekBreakdown` (with `total_ec` computed property)

### Vehicle Image

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/vehicle/v1/carpicture/key` |
| **Body** | `deviceID={deviceId}&vin={VIN}` |
| **Signature** | Car picture variant (duplicated deviceId) |

**Response (data):**

| Field | Description |
|---|---|
| `key` | Key for the package download |
| `shareBindUrl` | CDN URL of the image |
| `whole` | Full image flag |

### Image Package Download

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/vehicle/v1/carpicture/package` |
| **Body** | `key={picture_key}` |
| **Signature** | Car picture package variant |
| **Response** | Binary (ZIP) |

### Message List

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/message/v1/list` |
| **Body** | `pageNo={n}&pageSize={n}` |
| **Signature** | HMAC-SHA256 (with `pageNo`, `pageSize` in body_params) |

### Unread Message Count

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/message/v1/unread/count` |
| **Body** | (empty) |

### Share Invitations

Invitations to a car another account shares with this one (recipient side).

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/sharecar/getsharemsg` |
| **Body** | (empty) |

**Response** — `data` is a list, one entry per pending invitation:

| Field | Type | Description |
|---|---|---|
| `msgid` | `int` | Invitation id |
| `shareUserid` | `string` | Owner's account id — echoed back on accept/reject |
| `carCode` | `string` | VIN |
| `carId` | `string` | Car id |
| `carType` | `string` | Model code (`B10`, `C10`, …) |
| `carAlias` | `string` | Owner's name for the car |
| `nickName`, `email`, `mobileNumber` | `string` | Owner |
| `type` | `int` | `1` on the invitations seen so far |
| `moduleRights` | `string` | Comma-separated codes of the categories the owner chose to share, any subset of the four in [ModuleRight](#moduleright--macro-permission-categories-modulerights) |
| `rightList` | `string` | `null` on the invitation; the granted rights appear on the shared vehicle after acceptance |
| `durationType` | `int` | `0` for a share with no end date (the only kind seen so far); `expireTime` is then `null` |
| `shareTime`, `expireTime` | `int` | Epoch ms |

### Share Invitation Answer

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/sharecar/setokmsg` |
| **Body** | `shareUserId={owner id}&userId={own id}&carCode={vin}&state=yes` (`no` to reject) |
| **Signature** | HMAC-SHA256 (with the four fields in body_params) |

Responds `{"result": 0, "code": 0, "data": null}`; the car is in `vehicle/v1/list` → `sharedcars` a few seconds later.

### Charging Daily Detail

| | |
|---|---|
| **Path** | `POST /carownerservice/charge/daily/detail/page` |
| **Content-Type** | `application/json` |
| **Signature** | HMAC-SHA256 (with `vin`, `timeZone`, `startTime`, `endTime`, `pageNum`, `pageSize` in body_params) |

**JSON body:**

| Parameter | Type | Description |
|---|---|---|
| `vin` | string | Vehicle Identification Number |
| `timeZone` | string | Timezone (e.g. `"GMT+01:00"`) |
| `startTime` | string | Start date (`"2025-01-01"`) |
| `endTime` | string | End date (`"2026-05-10"`) |
| `pageNum` | int | Page number (1-based) |
| `pageSize` | int | Items per page |

**Response (data):**

| Field | Type | Description |
|---|---|---|
| `list[].chargeGunStartTs` | long | Charge start timestamp (epoch ms) |
| `list[].chargeGunEndTs` | long | Charge end timestamp (epoch ms) |
| `list[].chargeType` | string | `"1"` = AC (normal), `"2"` = DC (fast) |
| `list[].chargeInEnergy` | float | Energy charged (kWh) |
| `list[].chargeStartLongitude` | string | Longitude |
| `list[].chargeStartLatitude` | string | Latitude |
| `list[].zone` | string | Timezone (e.g. `"GMT+01:00"`) |

---

## Remote Control Endpoints

### Certificate Sync

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/vehicle/v1/cert/sync` |
| **Body** | (empty) |
| **Cert** | **App certificate** (not account cert) |

Executed once per session before the first remote command.

### Operation PIN Verification

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/vehicle/v1/operPwd/verify` |
| **Body** | `operatePassword={encrypted_pin}&vin={VIN}` |
| **Signature** | operatePassword verify variant |
| **Cert** | Account certificate |

Must be called before every remote command that requires the PIN.

### Remote Command Execution

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/vehicle/v1/app/remote/ctl` |
| **Signature** | Remote control write variant |
| **Cert** | Account certificate |

**Body (with PIN):**

```
cmdContent={json}&vin={VIN}&cmdId={id}&operatePassword={encrypted_pin}
```

**Body (without PIN, e.g. send_destination):**

```
cmdContent={json}&vin={VIN}&cmdId={id}
```

**Response (data):**

| Field | Description |
|---|---|
| `remoteCtlId` | ID for result polling |
| `queryRemoteCtlResultTimeout` | Polling timeout (ms) |
| `queryInterval` | Polling interval (ms) |

### Result Polling

| | |
|---|---|
| **Path** | `POST /carownerservice/oversea/vehicle/v1/app/remote/ctl/result/query` |
| **Body** | `remoteCtlId={id}` |
| **Signature** | Remote control result variant |

Polling continues until `data == 1` (success) or the timeout expires.

---

## Remote Commands

### Lock / Unlock (cmd_id=110)

| Action | cmd_content |
|---|---|
| Lock | `{"value":"lock"}` |
| Unlock | `{"value":"unlock"}` |

Requires PIN.

### Find Car (cmd_id=120)

| Action | cmd_content |
|---|---|
| Find | `{"value":"true"}` |

Requires PIN. Activates horn/lights to locate the vehicle.

### Trunk (cmd_id=130)

| Action | cmd_content |
|---|---|
| Open | `{"value":"true"}` |
| Close | `{"value":"false"}` |

Requires PIN.

### Hotspot (cmd_id=140)

| Action | cmd_content |
|---|---|
| Activate | `{"value":"findCar"}` |

Requires PIN. Triggers the hotspot / connectivity command.

### Autopark (cmd_id=150)

| Action | cmd_content |
|---|---|
| Activate | `{"value":"findCar"}` |

Requires PIN. Triggers auto park / summon.

### Battery Preheat (cmd_id=160)

| Action | cmd_content |
|---|---|
| On | `{"value":"ptcon"}` |
| Off | `{"value":"ptcoff"}` |

Requires PIN.

### Sentry Mode (cmd_id=220)

| Action | cmd_content |
|---|---|
| On | `{"value":"1"}` |
| Off | `{"value":"0"}` |

Requires PIN. Controls the sentinel / dashcam mode.

### Climate (cmd_id=170)

All climate profiles use `cmd_id=170`. The `cmd_content` is a JSON with:

| Field | Values | Description |
|---|---|---|
| `circle` | `in`, `out` | Air recirculation |
| `mode` | `cold`, `hot`, `wind` | Climate mode |
| `operate` | `manual`, `auto`, `close` | Operation mode (`close` = turn off) |
| `position` | `all` | Air distribution position |
| `temperature` | `"18"` – `"32"` | Target temperature (°C) |
| `windlevel` | `"1"` – `"7"` | Fan level |
| `wshld` | `0`, `1` | 0=Off, 1=Windshield defrost on |

**Predefined profiles:**

| Action | operate | circle | mode | temp | wind | wshld |
|---|---|---|---|---|---|---|
| AC On (default) | `manual` | `out` | `wind` | 26 | 3 | 0 |
| AC Off | `close` | `out` | `wind` | 26 | 3 | 0 |
| Quick Cool | `manual` | `in` | `cold` | 18 | 7 | 0 |
| Quick Heat | `manual` | `in` | `hot` | 32 | 7 | 0 |
| Windshield Defrost | `manual` | `in` | `hot` | 32 | 7 | 1 |

Requires PIN.

### Climate Schedule (cmd_id=171)

Schedules one or more climate activations. The `cmd_content` wraps a `controls` array.

Each invocation is a **full-state replacement**: the array must contain *all* active schedules. An empty array (`{"controls": []}`) cancels every existing schedule.

```json
{
  "controls": [
    {
      "mode": "cold",
      "on": "1",
      "operate": "auto",
      "set_id": "air_set3a4b5c6d1747382400000",
      "start_time": "2026-05-16 07:30:00",
      "temperature": "22",
      "update_time": "1747382400000",
      "windlevel": "4",
      "days": [1, 2, 3, 4, 5],
      "circle": "in",
      "position": "all",
      "wshld": "0"
    }
  ]
}
```

| Field | Values | Description |
|---|---|---|
| `mode` | `cold`, `hot`, `wind` | Climate mode |
| `on` | `"1"`, `"0"` | Schedule enabled/disabled |
| `operate` | `manual`, `auto` | Operation mode (no `close` in scheduler) |
| `set_id` | string | Unique id (`"air_set"` + phoneId + epochMs) |
| `start_time` | `"yyyy-MM-dd HH:mm:00"` | Activation time in vehicle timezone |
| `temperature` | `"18"` – `"32"` | Target temperature (°C) |
| `update_time` | epoch ms string | Last modification timestamp |
| `windlevel` | `"1"` – `"7"` | Fan level |
| `days` | `int[]` | Days of week (0=Sun..6=Sat), empty=once |
| `circle` | `in`, `out`, null | Air recirculation (null if unsupported) |
| `position` | `all` | Air distribution position |
| `wshld` | `"0"`, `"1"` | 0=Off, 1=Windshield defrost on |

Multiple schedules can be sent in a single `controls` array.

Requires PIN.

### Get Schedule (getAppointment)

Generic endpoint to retrieve active schedules from the server.

```
POST /carownerservice/oversea/vehicle/v1/app/remote/ctl/getAppointment
Body: vin={VIN}&cmdId={CMD_ID}
```

The response `data` field is a **JSON string** that must be double-parsed:

```json
{
  "result": 0,
  "data": "{...}"
}
```

Empty string or null `data` means no active schedules.
Server returns "No such permission" if the vehicle doesn't support the requested schedule type.

Does not require PIN.

#### Supported cmdId values

| cmdId | Name | Wrapper | Python method |
|-------|------|---------|---------------|
| `161` | PTC battery heating | `{"controls": [...]}` | `get_ptc_heating_schedule()` |
| `171` | Climate AC | `{"controls": [...]}` | `get_climate_schedule()` |
| `190` | Charge schedule | flat object (no controls) | `get_charge_schedule()` |
| `361` | Prepare car | `{"controls": [...]}` | `get_prepare_car_schedule()` |
| `392` | FOTA install | `{"controls": [...]}` | `get_fota_schedule()` |

#### cmdId=161 — PTC Heating

Each entry: `on`, `set_id`, `start_time`, `update_time`, `days`.

#### cmdId=171 — Climate

Same `controls` structure used by cmd_id=171 (see above).

#### cmdId=190 — Charge Schedule

Returns a flat object (NOT wrapped in `controls`):

```json
{"chargeEnable": 0, "chargesoc": 100, "circulation": 0, "starttime": "20:16"}
```

Also available in vehicle status (`config.$3`).

#### cmdId=361 — Prepare Car

Each entry: `name`, `desc`, `enable`, `set_id`, `start_time`, `update_time`, `days`, `datacontent` (sub-commands for climate, navigation, seats, etc.).

#### cmdId=392 — FOTA Install

Each entry: `pid` (package ID), `start_time`.

### Send Destination (cmd_id=180)

| Field | Description |
|---|---|
| `address` | Text address |
| `addressname` | Point of interest name |
| `latitude` | Latitude (string) |
| `longitude` | Longitude (string) |
| `linenum` | `"0"` |

Does **not** require PIN. Uses the flow without `operatePassword`.

### Set Charge Plan (cmd_id=190)

| Field | Description |
|---|---|
| `chargeEnable` | 0 or 1 |
| `chargesoc` | Percentage limit (1-100) |
| `circulation` | Schedule recurrence |
| `cycles` | Active days (e.g. `"1,1,1,1,1,1,1"`) |
| `endtime` | Schedule end time |
| `recharge` | Recharge flag |
| `starttime` | Schedule start time |

Requires PIN.

**Library methods:**

- `set_charge_limit(vin, charge_limit_percent)` — updates only the SOC limit, preserving the current schedule values.
- `set_charge_schedule(vin, enabled, soc_limit, start_time, end_time, cycles, circulation, recharge)` — sets all schedule fields at once.

### Unlock Charger (cmd_id=192)

| Action | cmd_content |
|---|---|
| Unlock | `{"operation":"unlock"}` |

Requires PIN. Unlocks the charging connector before unplugging.

### Start / Stop Charging (cmd_id=193)

| Action | cmd_content |
|---|---|
| Start | `{"value":"start"}` |
| Stop | `{"value":"stop"}` |

Requires PIN. Starts or stops charging when the connector is plugged in.
Available on C10/B10 models.

### Steering Wheel Heat (cmd_id=320)

| Action | cmd_content |
|---|---|
| On | `{"value":"on"}` |
| Off | `{"value":"off"}` |

Requires PIN. Enables or disables steering wheel heating.
Available on C10/B10 models.

### Fuel Heating (cmd_id=380)

| Action | cmd_content |
|---|---|
| On | `{"value":"1"}` |
| Off | `{"value":"0"}` |

Requires PIN. Enables or disables fuel heating (EREV/PHEV models).
Available on C10 fuel variant.

### Rearview Mirror Heat (cmd_id=440)

| Action | cmd_content |
|---|---|
| On | `{"value":"on"}` |
| Off | `{"value":"off"}` |

Requires PIN. Enables or disables rearview mirror heating.
Available on C10/B10 models.

### Healthy Charging (cmd_id=480)

| Action | cmd_content |
|---|---|
| On | `{"value":"1"}` |
| Off | `{"value":"0"}` |

Requires PIN. Enables or disables healthy charging mode (limits charge to ~80% to preserve battery health).

### ON3 (cmd_id=410)

| Action | cmd_content |
|---|---|
| On | `{"on3":"on"}` |
| Off | `{"on3":"off"}` |

Requires PIN. Enables or disables ON3 mode (domestic models).

### Speed Limit (cmd_id=510)

| Action | cmd_content |
|---|---|
| Set 80 km/h | `{"value":"80"}` |
| Set 120 km/h | `{"value":"120"}` |

Requires PIN. Sets a maximum speed limit (km/h). International models only.

### Seat Heat (cmd_id=301)

| Action | cmd_content |
|---|---|
| Driver seat, level 3 | `{"value":"3,3"}` |
| Left front, off | `{"value":"1,0"}` |

Requires PIN. Sets seat heating level.
Value format: `"position,level"` — position: 1=left_front, 2=copilot, 3=driver, 4=right_front, 5=left_rear, 6=right_rear; level: 0-3.

### Seat Ventilation (cmd_id=370)

| Action | cmd_content |
|---|---|
| Driver seat, level 3 | `{"value":"3,3"}` |
| Copilot, off | `{"value":"2,0"}` |

Requires PIN. Sets seat ventilation level.
Value format: same as Seat Heat — `"position,level"`.

### Sunroof (cmd_id=300)

| Action | cmd_content |
|---|---|
| Open | `{"value":"open"}` |
| Close | `{"value":"close"}` |

Requires PIN. Opens or closes the sunroof.
Available on C10/C16 models.

### Windows (cmd_id=230)

| Action | cmd_content |
|---|---|
| Open (100%) | `{"value":"100"}` |
| Close (0%) | `{"value":"0"}` |
| Partial | `{"value":"0"}`–`{"value":"100"}` |

Requires PIN. The `value` represents the opening percentage.

### Sunshade (cmd_id=240)

| Action | cmd_content |
|---|---|
| Open (10) | `{"value":"10"}` |
| Close (0) | `{"value":"0"}` |
| Partial | `{"value":"0"}`–`{"value":"10"}` |

### BLE Key Restart (cmd_id=430)

| Action | cmd_content |
|---|---|
| Restart | `{"value":"restart"}` |

Requires PIN. Restarts the BLE (Bluetooth Low Energy) digital key module.
Available on C10/B10 models.

### Music (cmd_id=270)

| Action | cmd_content |
|---|---|
| Play | `{"operation":"play"}` |
| Pause | `{"operation":"pause"}` |
| Next | `{"operation":"next"}` |
| Previous | `{"operation":"previous"}` |

Requires PIN. Controls music playback on the vehicle's infotainment system.
Available on C10/C16 models.

### Video (cmd_id=290)

| Action | cmd_content |
|---|---|
| Play | `{"operation":"play"}` |
| Pause | `{"operation":"pause"}` |
| Next | `{"operation":"next"}` |
| Previous | `{"operation":"previous"}` |

Requires PIN. Controls video playback on the vehicle's infotainment system.
Available on C10/C16 models.

### FOTA Download (cmd_id=390)

| Action | cmd_content |
|---|---|
| Download task 123 | `{"taskId":123}` |

Requires PIN. Triggers firmware-over-the-air download for the given task ID.

### FOTA Install (cmd_id=391)

| Action | cmd_content |
|---|---|
| Install task 123 | `{"taskId":123}` |

Requires PIN. Triggers firmware-over-the-air installation for the given task ID.

### FOTA Schedule (cmd_id=392)

| Action | cmd_content |
|---|---|
| Schedule task 123 | `{"taskId":123,"scheduleTime":"2026-05-13T10:00:00"}` |

Requires PIN. Schedules a firmware-over-the-air installation for the given task.

### Rear Seats (cmd_id=470)

| Action | cmd_content |
|---|---|
| Control | `{"seatInfo":"<data>"}` |

Requires PIN. Controls 2nd/3rd row seat adjustments.
Available on C16 models only.

### Prepare Car (cmd_id=360)

| Action | cmd_content |
|---|---|
| Pre-condition | Full JSON payload |

Requires PIN. Activates pre-conditioning (climate, seat heat, etc.).
Available on C10/B10 models. The payload is a full JSON string with scheduling and climate parameters.

### Seat Adjust (cmd_id=280)

| Action | cmd_content |
|---|---|
| Adjust | Full JSON payload |

Requires PIN. Controls seat adjustment on C10/C16 models.
The payload format is unknown; pass the full JSON payload string.

### Piloted Parking (cmd_id=350)

| Action | cmd_content |
|---|---|
| Park | Full JSON payload |

Requires PIN. Activates piloted parking on C10/C16 models.
The payload format is unknown; pass the full JSON payload string.

---

## Permission Reference

### VehicleRight — Remote Command Permissions (rightList)

Each remote command requires a corresponding right in the vehicle's
`rightList`. The server enforces permissions; the client performs a soft
check and logs a warning when a required right is missing.

| Code | Name | Required by cmd_id | Description |
|---|---|---|---|
| 110 | `LOCK` | 110 | Lock / Unlock doors |
| 120 | `FIND_CAR` | 120 | Find car (horn + lights) |
| 130 | `TRUNK` | 130 | Trunk open/close |
| 140 | `HOTSPOT` | 140 | Hotspot / connectivity |
| 150 | `AUTOPARK` | 150 | Auto park / summon |
| 160 | `SUNROOF` | — | Sunroof control |
| 161 | `SUNSHADE` | 240 | Sunshade control |
| 170 | `CLIMATE` | 170 (ac_switch) | Climate / AC on-off |
| 171 | `QUICK_CLIMATE` | 170 (quick_cool/heat) | Quick cool / Quick heat |
| 180 | `SEND_DESTINATION` | 180 | Send destination (navigation) |
| 190 | `BATTERY_PREHEAT` | 160 | Battery preheating |
| 192 | `UNLOCK_CHARGER` | 192 | Unlock charger connector |
| 193 | `TOGGLE_CHARGE` | — | Start / stop charging |
| 220 | `SENTRY_MODE` | — | Sentry mode |
| 230 | `WINDOWS` | 230 | Windows |
| 240 | `SKYLIGHT` | — | Skylight control |
| 270 | `MUSIC` | — | Music control |
| 280 | `SEAT_ADJUST` | — | Seat adjust |
| 290 | `VIDEO` | — | Video |
| 301 | `SEAT_HEAT` | — | Seat heating |
| 320 | `STEERING_WHEEL_HEAT` | — | Steering wheel heating |
| 340 | `CHARGE_LIMIT` | 190 | Charge limit |
| 360 | `PREPARE_CAR` | — | Pre-conditioning (prepare car) |
| 361 | `PREPARE_CAR_ALARM` | — | Pre-conditioning alarm |
| 370 | `SEAT_VENTILATION` | — | Seat ventilation |
| 380 | `FUEL_HEATING` | — | Fuel heating |
| 410 | `ON3` | 410 | ON3 mode |
| 460 | `WINDSHIELD_DEFROST` | 170 (defrost) | Windshield defrost / mirror heating |
| 480 | `HEALTHY_CHARGING` | 480 | Healthy charging mode |
| 510 | `SPEED_LIMIT` | — | Speed limit |

> **"—"** in the cmd_id column indicates the command is not yet implemented
> in this library (the right may appear in `rightList` for certain models).

### ModuleRight — Macro Permission Categories (moduleRights)

| Code | Name | Description |
|---|---|---|
| 100 | `BASIC` | Basic authorisation (lock/unlock) |
| 200 | `VEHICLE_CONTROL` | Vehicle control (climate, charge, quick control) |
| 300 | `VEHICLE_POSITIONING` | Vehicle positioning (GPS) |
| 400 | `MILEAGE_ENERGY` | Mileage & energy consumption |
