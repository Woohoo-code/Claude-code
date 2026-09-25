"""Single source of truth for the four printed antennas.

Used by both the openEMS model (sim_antenna.py) and the board generator
(pcb/gen_board.py), so what is simulated is exactly what is fabricated.
Board mm, origin at the top-left corner, +y down.

Board layout: a solid ground region GND_X0..GND_X1 x GND_Y0..BOARD on
both layers, surrounded on three sides by copper-free strips that carry
four inverted-F antennas (IFAs):

  top strip   (y < GND_Y0)  : 433 MHz  - radio A (low band)
  left strip  (x < GND_X0)  : 315 MHz  - radio A (after the 315 MHz BOM swap)
  right strip (x > GND_X1)  : 868 MHz (upper) and 915 MHz (lower) - radio B

Each IFA = a shorting leg from the ground edge, a feed leg from the ground
edge (1 mm gap = the feed), and an arm. The arm's last segment ("tail") is
the frequency knob; TAP (short-to-feed spacing) sets the feed resistance,
and the residual mismatch is taken out by the T-match on the board.
"""

BOARD = 100.0
GND_X0, GND_X1, GND_Y0 = 22.0, 82.0, 20.0
TRACE_W = 1.5
FEED_GAP = 1.0

# Tuned in openEMS (see antenna/README.md and antenna/results/).
PARAMS = {
    "433": {"tap": 3.0, "tail": 52.0},
    # 315 MHz is electrically small on this board (a quarter wave is 238 mm),
    # so its arm carries a series loading inductor near the feed end.
    "315": {"tap": 4.0, "tail": 50.0, "load_nh": 56.0, "load_at": (2.0, 42.0)},
    "868": {"tap": 4.0, "tail": 10.0},
    "915": {"tap": 4.0, "tail": 8.0},
}
FREQ_MHZ = {"433": 433.92, "315": 315.0, "868": 868.3, "915": 915.0}


def antenna(name, tap=None, tail=None):
    """Return dict(short=[pts], feed=[pts], arm=[pts], feed_pt=(x,y),
    gap_axis='x'|'y', gap_dir=+1|-1). `feed[0]` is the trace end at the
    feed gap; feed_pt is where the gap meets the ground edge."""
    p = PARAMS[name]
    tap = p["tap"] if tap is None else tap
    tail = p["tail"] if tail is None else tail
    if name == "433":       # ground edge y = GND_Y0, antenna above it
        sx, top = GND_X0 + 1.0, 3.0
        fx = sx + tap
        return {
            "short": [(sx, GND_Y0), (sx, top)],
            "feed": [(fx, GND_Y0 - FEED_GAP), (fx, top)],
            "arm": [(sx, top), (97.0, top), (97.0, 13.0), (97.0 - tail, 13.0)],
            "feed_pt": (fx, GND_Y0), "gap_axis": "y",
        }
    if name == "315":       # ground edge x = GND_X0, antenna to its left
        fy = 32.5                              # feed row (meets radio A's match)
        sy, x1, x2, x3 = fy - tap, 2.0, 8.0, 14.0
        return {
            "short": [(GND_X0, sy), (x1, sy)],
            "feed": [(GND_X0 - FEED_GAP, fy), (x1, fy)],
            "arm": [(x1, sy), (x1, 97.5), (x2, 97.5), (x2, 37.5), (x3, 37.5),
                    (x3, 37.5 + tail)],
            "feed_pt": (GND_X0, fy), "gap_axis": "x",
        }
    if name == "868":       # ground edge x = GND_X1; short on top, arm runs down
        sy = GND_Y0 + 1.5
        fy = sy + tap
        xa, xb, bottom = 97.0, 91.0, 50.0
        return {
            "short": [(GND_X1, sy), (xa, sy)],
            "feed": [(GND_X1 + FEED_GAP, fy), (xa, fy)],
            "arm": [(xa, sy), (xa, bottom), (xb, bottom), (xb, bottom - tail)],
            "feed_pt": (GND_X1, fy), "gap_axis": "x",
        }
    if name == "915":       # mirror image: short at the bottom, arm runs up
        sy = 96.0
        fy = sy - tap
        xa, xb, top = 97.0, 91.0, 67.0
        return {
            "short": [(GND_X1, sy), (xa, sy)],
            "feed": [(GND_X1 + FEED_GAP, fy), (xa, fy)],
            "arm": [(xa, sy), (xa, top), (xb, top), (xb, top + tail)],
            "feed_pt": (GND_X1, fy), "gap_axis": "x",
        }
    raise KeyError(name)


def split_at(pl, pt, gap=1.0):
    """Split polyline `pl` at point `pt` (on an axis-aligned segment),
    leaving a `gap` mm break centred on it. Returns (parts, axis)."""
    for i, ((x1, y1), (x2, y2)) in enumerate(zip(pl, pl[1:])):
        if x1 == x2 == pt[0] and min(y1, y2) < pt[1] < max(y1, y2):
            d = gap / 2 if y2 > y1 else -gap / 2
            return [pl[:i + 1] + [(pt[0], pt[1] - d)], [(pt[0], pt[1] + d)] + pl[i + 1:]], "y"
        if y1 == y2 == pt[1] and min(x1, x2) < pt[0] < max(x1, x2):
            d = gap / 2 if x2 > x1 else -gap / 2
            return [pl[:i + 1] + [(pt[0] - d, pt[1])], [(pt[0] + d, pt[1])] + pl[i + 1:]], "x"
    raise ValueError("load point not on the arm")


def load(name):
    """dict(at, axis, nh) for antennas with a loading inductor, else None."""
    p = PARAMS[name]
    if "load_nh" not in p:
        return None
    _, axis = split_at(antenna(name)["arm"], p["load_at"])
    return {"at": p["load_at"], "axis": axis, "nh": p["load_nh"]}


def arm_parts(name, **kw):
    """The arm as drawn: split around the loading inductor if there is one."""
    a = antenna(name, **kw)
    if "load_nh" not in PARAMS[name]:
        return [a["arm"]]
    return split_at(a["arm"], PARAMS[name]["load_at"])[0]


def shorted(name):
    return PARAMS[name].get("shorted", True)


def polylines(name, **kw):
    a = antenna(name, **kw)
    return [a["short"], a["feed"], a["arm"]]


def arm_length(name, **kw):
    a = antenna(name, **kw)
    pts = a["short"] + a["arm"][1:]
    return sum(abs(x2 - x1) + abs(y2 - y1) for (x1, y1), (x2, y2) in zip(pts, pts[1:]))


NAMES = ["433", "315", "868", "915"]
