# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- Fixed `Vehicle.from_dict` mapping: `userNickname` → `nickName` and `rights` → `rightList` to match actual API response keys

## [0.1.2] - 2026-05-02

### Added
- Added `Message` and `MessageList` models for notification messages
- Added `get_message_list(page_no, page_size)` method to retrieve paginated messages
- Added `get_unread_message_count()` method to get the number of unread messages
- Added async variants of message methods to `AsyncLeapmotorApiClient`
- Added `body_params` support to `build_signed_headers` for endpoints that include body parameters in the HMAC signature
- Updated example usage script to display messages

### Changed
- Remote control methods (`open_windows`, `close_windows`, `windows`, `control_sunshade`, `open_sunshade`, `close_sunshade`) now accept an optional `value` parameter to control intensity/position
- AC methods (`ac_switch`, `quick_cool`, `quick_heat`, `windshield_defrost`) now accept an optional `params` dict to override default climate settings (temperature, wind level, etc.)
- Internal `_remote_control` accepts optional `cmd_content` override for custom payloads

## [0.1.1] - 2026-05-01

### Added
- Added Enum for `ChargeState` and mapped raw integer values to enum members (e.g., `NOT_CONNECTED`, `AC_CONNECTED`, `DC_CONNECTED`)
- Added discharging power and `is_discharging` properties to battery status model
- Added `from_dict` class method to `BatteryStatus` for mapping raw API response into structured model
- Added regenerative braking status to vehicle status model (`is_regening` property) that indicates when the vehicle is regeneratively braking (i.e., driving with battery charging)
- Added `certs` folder for storing certificate files used for API communication
- Added `email`, `plate_number`, `vehicle_nickname`, `mobile_number`, `out_color`, `share_time`, `expire_time`, `duration_type`, `seat_layout`, `rudder` and `allocation_code` fields to `Vehicle` model based on API response data
- Added `raw` property to `Vehicle` model for storing original API response data for forward-compatibility and debugging
- Added `from_dict` class method to `Vehicle` model for mapping raw API response into structured model
- Added example usage script (`examples/usage.py`) that demonstrates how to use the `LeapmotorApiClient` to connect to the API, retrieve vehicle status, and display it in a human-readable format
- Added `pre-commit` dependency in `pyproject.toml` for managing git hooks and ensuring code quality before commits

### Changed
- Updated `BatteryStatus` to use `ChargeState` enum instead of raw integers
- Updated `BatteryStatus` logic for charging and discharging states
- Renamed `nickname` field in `Vehicle` model to `vehicle_nickname` for clarity
- Refactored `get_vehicle_status` method into `LeapmotorApiClient` to utilize new `VehicleStatus.from_dict` for parsing API response into structured model

### Removed
- Battery fields that map raw api into `BatteryStatus` model (e.g., `soc` and `chargeState` properties that were previously calculated based on raw api values)


## [0.1.0] - 2026-04-30

### Added
- Initial release with login, vehicle status, and remote commands
- Async client support
- AES encryption utilities for API communication
- Vehicle image generation
- Typed models for API responses
