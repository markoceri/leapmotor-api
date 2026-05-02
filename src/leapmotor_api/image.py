"""Dynamic car image compositor.

Composites layered car images from the picture package based on the
current vehicle status.
"""

from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import VehicleStatus

try:
    from PIL import Image
except ImportError as exc:
    raise ImportError(
        "Pillow is required for image compositing. Install it with: pip install leapmotor-api[image]"
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
    is_plugged = status.is_plugged
    is_charging = status.is_charging

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
    if is_plugged:
        layers.append("carpic_charge_open.png")
        layers.append("carpic_charge1.png")  # plugged but not yet charging
    elif is_charging:
        layers.append("carpic_charge_open.png")
        layers.append("carpic_charge2.png")  # static frame for still image

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

    def _composite_layers(
        self,
        layer_names: list[str],
    ) -> Image.Image:
        """Composite the given layers into a single RGBA canvas."""
        body = self._images.get("carpic_body.png")
        if body is None:
            raise ValueError("Package missing carpic_body.png")

        canvas = Image.new("RGBA", body.size, (0, 0, 0, 0))
        for name in layer_names:
            layer = self._images.get(name)
            if layer is None:
                continue
            canvas = Image.alpha_composite(canvas, layer)
        return canvas

    @staticmethod
    def _export(canvas: Image.Image, fmt: str = "PNG") -> bytes:
        """Export a canvas to bytes in the requested format."""
        buf = io.BytesIO()
        if fmt.upper() == "JPEG":
            rgb = Image.new("RGB", canvas.size, (0, 0, 0))
            rgb.paste(canvas, mask=canvas.split()[3])
            rgb.save(buf, format="JPEG", quality=90)
        else:
            canvas.save(buf, format=fmt.upper())
        return buf.getvalue()

    def compose(
        self,
        status: VehicleStatus | None = None,
        *,
        charge_frame: int = 2,
        format: str = "PNG",  # noqa: A002
    ) -> bytes:
        """Composite the car image layers based on vehicle status.

        Args:
            status: Current vehicle status. If None, all doors/windows closed.
            charge_frame: Charging animation frame (2-15). Only used when charging.
            format: Output image format (PNG, JPEG, WEBP).

        Returns:
            The composited image as bytes.
        """
        layer_names = _build_layer_list(status)

        # If charging and a specific frame is requested, swap the default frame
        if status and status.battery.is_charging and 2 <= charge_frame <= 15:
            for i, name in enumerate(layer_names):
                if name == "carpic_charge2.png":
                    layer_names[i] = f"carpic_charge{charge_frame}.png"
                    break

        canvas = self._composite_layers(layer_names)
        return self._export(canvas, format)

    def compose_animated(
        self,
        status: VehicleStatus | None = None,
        *,
        frame_duration: int = 200,
    ) -> tuple[bytes, str]:
        """Composite the car image; return animated WebP when charging, static PNG otherwise.

        Args:
            status: Current vehicle status.
            frame_duration: Milliseconds per frame for charging animation.

        Returns:
            Tuple of ``(image_bytes, media_type)``.
            ``media_type`` is ``"image/webp"`` when animated,
            ``"image/png"`` when static.
        """
        if not (status and status.battery.is_charging):
            return self.compose(status), "image/png"

        # Build the base canvas without the animated charge-level layer
        layer_names = _build_layer_list(status)
        base_layers = [n for n in layer_names if not n.startswith("carpic_charge") or n == "carpic_charge_open.png"]
        base_canvas = self._composite_layers(base_layers)

        # Generate 14 frames, each overlaying a different charge level
        frames: list[Image.Image] = []
        for i in range(2, 16):
            charge_layer = self._images.get(f"carpic_charge{i}.png")
            frame = Image.alpha_composite(base_canvas, charge_layer) if charge_layer else base_canvas.copy()
            frames.append(frame)

        buf = io.BytesIO()
        frames[0].save(
            buf,
            format="WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=frame_duration,
            loop=0,
            lossless=True,
        )
        return buf.getvalue(), "image/webp"
