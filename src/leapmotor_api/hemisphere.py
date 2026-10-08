"""Keep GPS coordinates in the right hemisphere across polls.

Signal-based vehicles (C10/B10) report each coordinate twice: signed in
signals ``2``/``3`` and as an absolute value in ``3724``/``3725`` (or
``2191``/``2190``). Two cloud defects put West/South cars in the wrong
hemisphere (see https://github.com/markoceri/leapmotor-api/issues/17):

* some polls omit the signed pair, leaving only the absolute value;
* the signed slot occasionally carries the absolute value itself.

:class:`HemisphereGuard` remembers the last trusted sign per VIN and axis and
applies three rules:

1. A negative reading is always trusted: a lost sign can only surface as a
   positive number, so a minus is proof.
2. An absolute-value reading gets the remembered sign back.
3. A positive signed reading that contradicts a remembered West/South sign is
   accepted only if it is a plausible move from the last trusted position
   (a real crossing passes through zero, a dropped sign jumps by twice the
   magnitude), or after ``confirm_polls`` distinct frames in a row agree.
   A trusted reading in between resets the count, and a stale frame the cloud
   re-serves (same ``collect_time``) is counted once.

The state lives in memory. Callers that want it to survive a restart persist
:meth:`HemisphereGuard.export_state` and pass it back to the constructor.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from .models import VehicleStatus

DEFAULT_MAX_JUMP_DEG = 0.5
DEFAULT_CONFIRM_POLLS = 3


@dataclass(slots=True)
class _AxisMemory:
    sign: int
    last: float
    pending: int = 0
    pending_frame: datetime | None = None


class HemisphereGuard:
    """Per-VIN memory of the coordinate sign, fed by consecutive vehicle statuses."""

    def __init__(
        self,
        state: Mapping[str, Any] | None = None,
        *,
        max_jump_deg: float = DEFAULT_MAX_JUMP_DEG,
        confirm_polls: int = DEFAULT_CONFIRM_POLLS,
    ) -> None:
        self.max_jump_deg = max_jump_deg
        self.confirm_polls = max(1, confirm_polls)
        self._memory: dict[tuple[str, str], _AxisMemory] = {}
        self._lock = threading.Lock()
        if state:
            self._load_state(state)

    def apply(self, vin: str, status: VehicleStatus) -> VehicleStatus:
        """Correct ``status.location`` in place using the memory for *vin*, and return *status*."""
        location = status.location
        with self._lock:
            location.latitude = self._apply_axis(
                vin, "latitude", location.latitude, location.latitude_signed, status.collect_time
            )
            location.longitude = self._apply_axis(
                vin, "longitude", location.longitude, location.longitude_signed, status.collect_time
            )
        return status

    def export_state(self) -> dict[str, dict[str, dict[str, float]]]:
        """Return the remembered signs as a JSON-serializable dict, keyed by VIN."""
        state: dict[str, dict[str, dict[str, float]]] = {}
        with self._lock:
            for (vin, axis), memory in self._memory.items():
                state.setdefault(vin, {})[axis] = {"sign": memory.sign, "last": memory.last}
        return state

    def _load_state(self, state: Mapping[str, Any]) -> None:
        for vin, axes in state.items():
            if not isinstance(axes, dict):
                continue
            for axis in ("latitude", "longitude"):
                entry = axes.get(axis)
                if not isinstance(entry, dict):
                    continue
                sign, last = entry.get("sign"), entry.get("last")
                if sign in (1, -1) and isinstance(last, (int, float)):
                    self._memory[(vin, axis)] = _AxisMemory(sign=int(sign), last=float(last))

    def _apply_axis(
        self, vin: str, axis: str, value: float | None, signed: bool | None, frame: datetime | None
    ) -> float | None:
        if not isinstance(value, (int, float)):
            return value
        key = (vin, axis)
        memory = self._memory.get(key)

        # Rule 1: a minus cannot be invented, so it is proof.
        if value < 0:
            self._memory[key] = _AxisMemory(sign=-1, last=value)
            return value

        if memory is None:
            # Only a signed reading may teach the sign; an absolute value is passed through as is.
            if signed is not False:
                self._memory[key] = _AxisMemory(sign=1, last=value)
            return value

        if memory.sign > 0 or value == 0:
            memory.last = value
            memory.pending = 0
            memory.pending_frame = None
            return value

        # Remembered West/South, positive reading.
        if signed is False:
            # Rule 2: the absolute-value signals never carry the sign. The frame
            # breaks a run of contradicting signed frames.
            memory.last = -value
            memory.pending = 0
            memory.pending_frame = None
            return -value

        # Rule 3: a positive signed reading against a remembered minus.
        if value - memory.last <= self.max_jump_deg:
            self._memory[key] = _AxisMemory(sign=1, last=value)
            return value
        if frame is None or frame != memory.pending_frame:
            memory.pending += 1
            memory.pending_frame = frame
        if memory.pending >= self.confirm_polls:
            self._memory[key] = _AxisMemory(sign=1, last=value)
            return value
        return -value
