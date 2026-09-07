"""Package geometry database and pin-position/labeling generator.

Pins are labeled and positioned from the package's physical shape and size
(JEDEC/IPC-style conventions), not from any part-specific silicon pinout -
we don't know what a given MPN's pin 3 *does*, only where pin 3 physically
is and how big it is. That's what "label pins from shape and size" means
here.

Numbering convention used throughout (documented, not universal - some
vendors differ): pin 1 is marked by a dot/notch; numbering proceeds
counterclockwise viewed from the top, starting at pin 1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Pin:
    number: str
    x_mm: float
    y_mm: float
    pad_w_mm: float
    pad_h_mm: float
    shape: str  # "rect", "roundrect", "circle" (circle => through-hole)
    drill_mm: float | None = None
    is_pin1: bool = False


@dataclass
class Package:
    name: str
    kind: str
    body_w_mm: float
    body_h_mm: float
    body_z_mm: float  # height above board, for 3D preview
    pins: list[Pin]
    color: tuple[float, float, float] = (0.15, 0.15, 0.15)


def _row_pins(count: int, pitch: float, y_mm: float, start_num: int, x0: float,
              pad_w: float, pad_h: float, step: int = 1) -> list[Pin]:
    pins = []
    for i in range(count):
        pins.append(
            Pin(
                number=str(start_num + i * step),
                x_mm=round(x0 + i * pitch * (1 if step > 0 else -1), 3),
                y_mm=y_mm,
                pad_w_mm=pad_w,
                pad_h_mm=pad_h,
                shape="rect",
            )
        )
    return pins


def _dual_row_gullwing(total_pins: int, pitch: float, row_span: float,
                        pad_w: float, pad_h: float) -> list[Pin]:
    """SOIC/TSSOP-style: pin1 top-left, down the left column, up the right column."""
    per_side = total_pins // 2
    pins: list[Pin] = []
    x_left = -row_span / 2
    x_right = row_span / 2
    span_len = (per_side - 1) * pitch
    y0 = span_len / 2
    for i in range(per_side):
        pins.append(Pin(str(i + 1), x_left, round(y0 - i * pitch, 3), pad_w, pad_h, "rect"))
    for i in range(per_side):
        pins.append(
            Pin(str(per_side + i + 1), x_right, round(-y0 + i * pitch, 3), pad_w, pad_h, "rect")
        )
    pins[0].is_pin1 = True
    return pins


def _sot23_like(total_pins: int, pitch: float, row_span: float,
                 pad_w: float, pad_h: float) -> list[Pin]:
    """3/5/6-lead SOT: split bottom row / top row, counterclockwise from pin 1."""
    bottom = (total_pins + 1) // 2
    top = total_pins - bottom
    pins: list[Pin] = []
    x0 = -(bottom - 1) * pitch / 2
    for i in range(bottom):
        pins.append(Pin(str(i + 1), round(x0 + i * pitch, 3), -row_span / 2, pad_w, pad_h, "rect"))
    x0t = (top - 1) * pitch / 2
    for i in range(top):
        pins.append(
            Pin(str(bottom + i + 1), round(x0t - i * pitch, 3), row_span / 2, pad_w, pad_h, "rect")
        )
    pins[0].is_pin1 = True
    return pins


def _qfn(total_pins: int, pitch: float, body: float, pad_w: float, pad_h: float,
         has_epad: bool) -> list[Pin]:
    """Quad flat no-lead: pins on all 4 sides, counterclockwise from pin 1 (top-left)."""
    per_side = total_pins // 4
    pins: list[Pin] = []
    edge = body / 2 + pad_h / 2
    span = (per_side - 1) * pitch
    n = 1
    # left side, top -> bottom
    for i in range(per_side):
        pins.append(Pin(str(n), -edge, round(span / 2 - i * pitch, 3), pad_h, pad_w, "rect"))
        n += 1
    # bottom side, left -> right
    for i in range(per_side):
        pins.append(Pin(str(n), round(-span / 2 + i * pitch, 3), -edge, pad_w, pad_h, "rect"))
        n += 1
    # right side, bottom -> top
    for i in range(per_side):
        pins.append(Pin(str(n), edge, round(-span / 2 + i * pitch, 3), pad_h, pad_w, "rect"))
        n += 1
    # top side, right -> left
    for i in range(per_side):
        pins.append(Pin(str(n), round(span / 2 - i * pitch, 3), edge, pad_w, pad_h, "rect"))
        n += 1
    if has_epad:
        pins.append(
            Pin("EP", 0.0, 0.0, body * 0.55, body * 0.55, "rect")
        )
    pins[0].is_pin1 = True
    return pins


def _dip(total_pins: int, pitch: float, row_span: float, drill: float,
          pad: float) -> list[Pin]:
    per_side = total_pins // 2
    pins: list[Pin] = []
    span_len = (per_side - 1) * pitch
    y0 = span_len / 2
    for i in range(per_side):
        pins.append(
            Pin(str(i + 1), -row_span / 2, round(y0 - i * pitch, 3), pad, pad, "circle", drill)
        )
    for i in range(per_side):
        pins.append(
            Pin(
                str(per_side + i + 1), row_span / 2, round(-y0 + i * pitch, 3), pad, pad,
                "circle", drill,
            )
        )
    pins[0].is_pin1 = True
    return pins


def _header(count: int, pitch: float, drill: float | None, pad: float) -> list[Pin]:
    x0 = -(count - 1) * pitch / 2
    shape = "circle" if drill else "rect"
    pins = [
        Pin(str(i + 1), round(x0 + i * pitch, 3), 0.0, pad, pad, shape, drill)
        for i in range(count)
    ]
    pins[0].is_pin1 = True
    return pins


def _chip_2pin(pitch: float, pad_w: float, pad_h: float) -> list[Pin]:
    return [
        Pin("1", -pitch / 2, 0.0, pad_w, pad_h, "rect", is_pin1=True),
        Pin("2", pitch / 2, 0.0, pad_w, pad_h, "rect"),
    ]


# name -> (kind, builder args, body size, height, color)
_CHIP_SIZES_MM = {
    "0201": (0.6, 0.3, 0.4, 0.25, 0.25),
    "0402": (1.0, 0.5, 0.6, 0.6, 0.35),
    "0603": (1.6, 0.8, 0.95, 0.95, 0.45),
    "0805": (2.0, 1.25, 1.15, 1.4, 0.5),
    "1206": (3.2, 1.6, 1.6, 1.6, 0.55),
    "1210": (3.2, 2.5, 1.6, 2.5, 0.55),
    "2512": (6.3, 3.2, 3.0, 3.2, 0.55),
}

_ALIASES = {
    "SOT23": "SOT-23-3",
    "SOT-23": "SOT-23-3",
    "SOT323": "SOT-23-3",
}


def normalize_package_name(raw: str) -> str | None:
    if not raw:
        return None
    s = raw.upper().strip()
    s = re.sub(r"\(.*?\)", "", s).strip()
    s = re.sub(r"\s+", "-", s)
    s = s.replace("--", "-")
    if s in _ALIASES:
        s = _ALIASES[s]

    if s in _CHIP_SIZES_MM:
        return s
    m = re.match(r"^SOT-?23-?(\d)$", s)
    if m:
        return f"SOT-23-{m.group(1)}"
    m = re.match(r"^SOIC-?(\d+)", s)
    if m:
        return f"SOIC-{m.group(1)}"
    m = re.match(r"^TSSOP-?(\d+)", s)
    if m:
        return f"TSSOP-{m.group(1)}"
    m = re.match(r"^(?:VQFN|QFN)-?(\d+)", s)
    if m:
        return f"QFN-{m.group(1)}"
    m = re.match(r"^DIP-?(\d+)", s)
    if m:
        return f"DIP-{m.group(1)}"
    m = re.match(r"^TO-?220", s)
    if m:
        return "TO-220"
    m = re.match(r"^TO-?92", s)
    if m:
        return "TO-92"
    m = re.match(r"^(?:HDR|HEADER)-?1X-?(\d+)", s)
    if m:
        return f"HDR-1X{m.group(1)}"
    m = re.match(r"^JST-?PH-?(\d+)", s)
    if m:
        return f"JST-PH-{m.group(1)}"
    return None


def build_package(name: str) -> Package | None:
    key = normalize_package_name(name)
    if key is None:
        return None

    if key in _CHIP_SIZES_MM:
        bw, bh, pitch, pad_w, pad_h = _CHIP_SIZES_MM[key]
        return Package(key, "chip_2pin", bw, bh, max(bh * 0.5, 0.35),
                       _chip_2pin(pitch, pad_w, pad_h), color=(0.65, 0.55, 0.35))

    m = re.match(r"^SOT-23-(\d)$", key)
    if m:
        n = int(m.group(1))
        pitch, row_span, pad_w, pad_h = 0.95, 2.6, 0.6, 0.9
        body = (1.6, 2.9) if n <= 3 else (1.75, 3.0)
        return Package(key, "sot", *body, 1.0,
                       _sot23_like(n, pitch, row_span, pad_w, pad_h),
                       color=(0.1, 0.1, 0.1))

    m = re.match(r"^SOIC-(\d+)$", key)
    if m:
        n = int(m.group(1))
        pitch = 1.27
        row_span = 5.4 if n <= 8 else 7.6
        body_w = row_span - 1.4
        body_h = ((n // 2 - 1) * pitch) + 2.0
        return Package(key, "soic", body_w, body_h, 1.75,
                       _dual_row_gullwing(n, pitch, row_span, 0.6, 1.55),
                       color=(0.08, 0.08, 0.08))

    m = re.match(r"^TSSOP-(\d+)$", key)
    if m:
        n = int(m.group(1))
        pitch = 0.65
        row_span = 6.4
        body_w = 4.4
        body_h = ((n // 2 - 1) * pitch) + 1.4
        return Package(key, "tssop", body_w, body_h, 1.0,
                       _dual_row_gullwing(n, pitch, row_span, 0.35, 1.2),
                       color=(0.08, 0.08, 0.08))

    m = re.match(r"^QFN-(\d+)$", key)
    if m:
        n = int(m.group(1))
        pitch = 0.5
        body = 4.0 if n <= 20 else 5.0
        return Package(key, "qfn", body, body, 0.9,
                       _qfn(n, pitch, body, 0.25, 0.7, has_epad=True),
                       color=(0.05, 0.05, 0.05))

    m = re.match(r"^DIP-(\d+)$", key)
    if m:
        n = int(m.group(1))
        pitch = 2.54
        row_span = 7.62 if n <= 16 else 15.24
        body_w = row_span + 1.5
        body_h = ((n // 2 - 1) * pitch) + 3.0
        return Package(key, "dip", body_w, body_h, 4.0,
                       _dip(n, pitch, row_span, 0.8, 1.6),
                       color=(0.1, 0.1, 0.1))

    if key == "TO-220":
        pins = _header(3, 2.54, 1.0, 1.9)
        for p in pins:
            p.shape = "circle"
        return Package(key, "to220", 10.0, 4.5, 9.0, pins, color=(0.2, 0.2, 0.2))

    if key == "TO-92":
        pins = _header(3, 1.27, 0.45, 0.8)
        for p in pins:
            p.shape = "circle"
        return Package(key, "to92", 4.0, 4.0, 5.0, pins, color=(0.15, 0.1, 0.05))

    m = re.match(r"^HDR-1X(\d+)$", key)
    if m:
        n = int(m.group(1))
        return Package(key, "header", n * 2.54 + 2.0, 3.0, 6.0,
                       _header(n, 2.54, 1.0, 1.7), color=(0.05, 0.05, 0.1))

    m = re.match(r"^JST-PH-(\d+)$", key)
    if m:
        n = int(m.group(1))
        return Package(key, "header", n * 2.0 + 2.5, 4.0, 4.5,
                       _header(n, 2.0, 0.7, 1.1), color=(0.9, 0.9, 0.85))

    return None


def known_package_names() -> list[str]:
    names = list(_CHIP_SIZES_MM.keys())
    names += [f"SOT-23-{n}" for n in (3, 5, 6)]
    names += [f"SOIC-{n}" for n in (8, 14, 16)]
    names += [f"TSSOP-{n}" for n in (8, 14, 16, 20)]
    names += [f"QFN-{n}" for n in (16, 20, 24, 32)]
    names += [f"DIP-{n}" for n in (8, 14, 16)]
    names += ["TO-220", "TO-92"]
    names += [f"HDR-1X{n}" for n in (2, 3, 4, 6, 8, 10)]
    names += [f"JST-PH-{n}" for n in (2, 3, 4)]
    return names
