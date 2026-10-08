"""Tests for leapmotor_api.hemisphere module (issue #17)."""

from __future__ import annotations

import json
from typing import Any

from leapmotor_api.hemisphere import HemisphereGuard
from leapmotor_api.models import VehicleStatus

VIN = "VIN1"
# Lisbon: 38.72 N, 9.14 W.
LAT = 38.72
LON = 9.14


def _status(signal: dict[str, Any], sts: int | None = None) -> VehicleStatus:
    if sts is not None:
        signal = {**signal, "sts": sts}
    return VehicleStatus.from_dict({"signal": signal})


def _signed(lon: float, lat: float = LAT, sts: int | None = None) -> VehicleStatus:
    return _status({"2": lon, "3": lat, "3724": abs(lon), "3725": abs(lat)}, sts)


def _unsigned(lon: float, lat: float = LAT, sts: int | None = None) -> VehicleStatus:
    return _status({"3724": lon, "3725": lat}, sts)


def _lon(guard: HemisphereGuard, status: VehicleStatus, vin: str = VIN) -> float | None:
    return guard.apply(vin, status).location.longitude


class TestMissingSignedPair:
    """Gap 1: polls without signals 2/3 keep the remembered sign."""

    def test_absolute_value_gets_remembered_sign(self) -> None:
        guard = HemisphereGuard()
        assert _lon(guard, _signed(-LON)) == -LON
        assert _lon(guard, _unsigned(LON)) == -LON
        assert _lon(guard, _unsigned(LON + 0.01)) == -(LON + 0.01)

    def test_south_latitude(self) -> None:
        guard = HemisphereGuard()
        guard.apply(VIN, _signed(151.2, lat=-33.87))
        status = guard.apply(VIN, _unsigned(151.2, lat=33.87))
        assert status.location.latitude == -33.87
        assert status.location.longitude == 151.2

    def test_east_car_untouched(self) -> None:
        guard = HemisphereGuard()
        assert _lon(guard, _signed(14.28)) == 14.28
        assert _lon(guard, _unsigned(14.28)) == 14.28

    def test_absolute_value_does_not_teach_sign(self) -> None:
        guard = HemisphereGuard()
        assert _lon(guard, _unsigned(LON)) == LON
        assert guard.export_state() == {}
        # The first signed reading still decides.
        assert _lon(guard, _signed(-LON)) == -LON

    def test_memory_is_per_vin(self) -> None:
        guard = HemisphereGuard()
        guard.apply("WEST", _signed(-LON))
        guard.apply("EAST", _signed(14.28))
        assert _lon(guard, _unsigned(LON), vin="WEST") == -LON
        assert _lon(guard, _unsigned(14.28), vin="EAST") == 14.28


class TestWrongSignedSlot:
    """Gap 2: a positive value in the signed slot is not believed blindly."""

    def test_single_bad_frame_is_mirrored_back(self) -> None:
        guard = HemisphereGuard()
        guard.apply(VIN, _signed(-LON))
        assert _lon(guard, _signed(LON)) == -LON
        assert guard.export_state()[VIN]["longitude"]["sign"] == -1

    def test_negative_is_always_trusted(self) -> None:
        guard = HemisphereGuard()
        # A bad first frame teaches East; the next minus corrects it at once.
        assert _lon(guard, _signed(LON)) == LON
        assert _lon(guard, _signed(-LON)) == -LON
        assert _lon(guard, _unsigned(LON)) == -LON

    def test_crossing_near_meridian_is_accepted(self) -> None:
        guard = HemisphereGuard()
        guard.apply(VIN, _signed(-0.12))
        assert _lon(guard, _signed(0.05)) == 0.05
        assert _lon(guard, _unsigned(0.3)) == 0.3

    def test_flip_far_from_meridian_needs_consecutive_frames(self) -> None:
        guard = HemisphereGuard(confirm_polls=3)
        guard.apply(VIN, _signed(-LON, sts=1_000))
        assert _lon(guard, _signed(14.28, sts=2_000)) == -14.28
        assert _lon(guard, _signed(14.28, sts=3_000)) == -14.28
        assert _lon(guard, _signed(14.28, sts=4_000)) == 14.28
        assert _lon(guard, _unsigned(14.28)) == 14.28

    def test_trusted_frame_resets_the_count(self) -> None:
        guard = HemisphereGuard(confirm_polls=2)
        guard.apply(VIN, _signed(-LON, sts=1_000))
        assert _lon(guard, _signed(LON, sts=2_000)) == -LON
        assert _lon(guard, _signed(-LON, sts=3_000)) == -LON
        assert _lon(guard, _signed(LON, sts=4_000)) == -LON
        assert _lon(guard, _unsigned(LON, sts=5_000)) == -LON
        assert _lon(guard, _signed(LON, sts=6_000)) == -LON

    def test_stale_frame_counts_once(self) -> None:
        """A frame the cloud re-serves unchanged is not new evidence."""
        guard = HemisphereGuard(confirm_polls=2)
        guard.apply(VIN, _signed(-LON, sts=1_000))
        for _ in range(5):
            assert _lon(guard, _signed(LON, sts=2_000)) == -LON
        assert _lon(guard, _signed(LON, sts=3_000)) == LON


class TestState:
    def test_round_trip_through_json(self) -> None:
        guard = HemisphereGuard()
        guard.apply(VIN, _signed(-LON))
        state = json.loads(json.dumps(guard.export_state()))
        assert state == {VIN: {"latitude": {"sign": 1, "last": LAT}, "longitude": {"sign": -1, "last": -LON}}}

        restored = HemisphereGuard(state)
        assert _lon(restored, _unsigned(LON)) == -LON

    def test_invalid_state_is_ignored(self) -> None:
        guard = HemisphereGuard({VIN: {"longitude": {"sign": 0, "last": "x"}}, "BAD": None})
        assert guard.export_state() == {}

    def test_status_without_location(self) -> None:
        guard = HemisphereGuard()
        status = guard.apply(VIN, VehicleStatus.from_dict({"signal": {"1204": 80}}))
        assert status.location.longitude is None
        assert guard.export_state() == {}
