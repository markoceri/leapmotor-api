"""Dynamic car image compositor.

Composites layered car images from the picture package based on the
current vehicle status.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

from .models import VehicleStatus

try:
    from PIL import Image
except ImportError as exc:
    raise ImportError(
        "Pillow is required for image compositing. "
        "Install it with: pip install leapmotor-api[image]"
    ) from exc


# The canonical layer order, from back to front.
# Layers rendered earlier are below layers rendered later.
# Right-side doors go BELOW the body (far side in 3/4 view),
# left-side doors go ABOVE the body (near side).
def _build_layer_list(status: VehicleStatus | None) -> list[str]:
    """Return the ordered list of layer filenames to composite."""
    layers: list[str] = []

    if status is None:
        # No status available — return just the body with everything closed
        return [
            "carpic_rightbehind_close.png",
            "carpic_rightfront_close.png",
            "carpic_body.png",
            "carpic_hood_close.png",
            "carpic_leftbehind_close.png",
            "carpic_leftfront_close.png",
            "carpic_leftbehind_window_close.png",
            "carpic_leftfront_window_close.png",
        ]

    doors = status.doors
    windows = status.windows
    is_charging = status.battery.is_charging

    # --- Right side (far side, below body) ---
    # Right rear door
    if doors.rbcm_right_rear_door_status:
        layers.append("carpic_rightbehind_open.png")
    else:
        layers.append("carpic_rightbehind_close.png")

    # Right front door
    if doors.rbcm_driver_door_status:
        layers.append("carpic_rightfront_open.png")
    else:
        layers.append("carpic_rightfront_close.png")

    # --- Body ---
    layers.append("carpic_body.png")

    # --- Hood (no API status, always closed) ---
    layers.append("carpic_hood_close.png")

    # --- Left side (near side, above body) ---
    # Left rear door
    if doors.lbcm_left_rear_door_status:
        layers.append("carpic_leftbehind_open.png")
    else:
        layers.append("carpic_leftbehind_close.png")

    # Left front door (driver)
    if doors.lbcm_driver_door_status:
        layers.append("carpic_leftfront_open.png")
    else:
        layers.append("carpic_leftfront_close.png")

    # --- Tailgate (trunk) ---
    if doors.bbcm_back_door_status:
        layers.append("carpic_tailgate_open.png")

    # --- Windows (glass shown when closed / percent == 0) ---
    if (windows.left_front_window_percent or 0) == 0:
        layers.append("carpic_leftfront_window_close.png")

    if (windows.left_rear_window_percent or 0) == 0:
        layers.append("carpic_leftbehind_window_close.png")

    # --- Charging ---
    if is_charging:
        layers.append("carpic_charge_open.png")
        layers.append("carpic_charge1.png")  # static frame for still image

    return layers


class CarImagePackage:
    """Holds extracted car picture layers and composites them on demand.

    Usage::

        pkg = CarImagePackage.from_zip(zip_bytes)
        png_bytes = pkg.compose(vehicle_status)

    The instance caches the decoded PIL images, so repeated ``compose()``
    calls with different statuses are efficient.
    """

    def __init__(self, images: dict[str, Image.Image]) -> None:
        self._images = images

    @classmethod
    def from_zip(cls, zip_bytes: bytes) -> CarImagePackage:
        """Create a package from raw ZIP bytes (as returned by the API)."""
        images: dict[str, Image.Image] = {}
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for entry in zf.namelist():
                lower = entry.lower()
                if not lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    continue
                basename = entry.rsplit("/", 1)[-1]
                raw = zf.read(entry)
                img = Image.open(io.BytesIO(raw)).convert("RGBA")
                images[basename] = img
        return cls(images)

    @property
    def layer_names(self) -> list[str]:
        """Return the list of available layer filenames."""
        return sorted(self._images.keys())

    def get_tripsum(self) -> Image.Image | None:
        """Return the complete car preview image, if available."""
        return self._images.get("carpic_for_tripsum.png")

    def compose(
        self,
        status: VehicleStatus | None = None,
        *,
        charge_frame: int = 1,
        format: str = "PNG",
    ) -> bytes:
        """Composite the car image layers based on vehicle status.

        Args:
            status: Current vehicle status. If None, all doors/windows closed.
            charge_frame: Charging animation frame (1-15). Only used when charging.
            format: Output image format (PNG, JPEG, WEBP).

        Returns:
            The composited image as bytes.
        """
        layer_names = _build_layer_list(status)

        # If charging and a specific frame is requested, swap the default frame
        if status and status.battery.is_charging and 1 <= charge_frame <= 15:
            # Replace carpic_charge1.png with the requested frame
            for i, name in enumerate(layer_names):
                if name == "carpic_charge1.png":
                    layer_names[i] = f"carpic_charge{charge_frame}.png"
                    break

        # Find the canvas size from the body image
        body = self._images.get("carpic_body.png")
        if body is None:
            raise ValueError("Package missing carpic_body.png")

        canvas = Image.new("RGBA", body.size, (0, 0, 0, 0))

        for name in layer_names:
            layer = self._images.get(name)
            if layer is None:
                continue
            # All layers are the same size — alpha-composite directly
            canvas = Image.alpha_composite(canvas, layer)

        # Convert and export
        buf = io.BytesIO()
        if format.upper() == "JPEG":
            # JPEG doesn't support alpha
            rgb = Image.new("RGB", canvas.size, (0, 0, 0))
            rgb.paste(canvas, mask=canvas.split()[3])
            rgb.save(buf, format="JPEG", quality=90)
        else:
            canvas.save(buf, format=format.upper())
        return buf.getvalue()
