"""T-match part values per antenna, filled in from the openEMS results by
design_match.py (see antenna/README.md). Imported by pcb/gen_board.py.

Each branch is: S1 (selector, series) -> C (shunt to GND) -> S2 (series) -> antenna.
Fitting S1 selects the antenna; leaving it off disconnects the branch.
"""

MATCH = {
    "433": {"refs": ("R301", "C301", "L301"), "s1": "0R", "c": "DNP", "s2": "0R"},
    "315": {"refs": ("R311", "C311", "L311"), "s1": "DNP", "c": "DNP", "s2": "0R"},
    "868": {"refs": ("R321", "C321", "L321"), "s1": "0R", "c": "DNP", "s2": "0R"},
    "915": {"refs": ("R331", "C331", "L331"), "s1": "DNP", "c": "DNP", "s2": "0R"},
}
