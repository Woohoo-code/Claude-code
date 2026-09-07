"""Minimal pure-Python glTF Binary (.glb) writer.

No external 3D libraries - just enough of the glTF 2.0 spec to emit a
scene of colored boxes: one box per BOM part (sized from its package's
body width/height/component height) sitting on a board slab, positioned
the same way as the KiCad export's grid layout. It's a shape/size preview
of the assembly, not a faithful 3D model of any real part.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from .bom import PartInstance
from .packages import Package

_BOARD_COLOR = (0.05, 0.35, 0.1)
_BOARD_THICKNESS_MM = 1.6

# Unit box centered at origin, spanning -0.5..0.5 on each axis, 24 verts
# (4 per face) so each face gets a flat normal.
_FACES = [
    # (normal, 4 corner offsets forming a CCW quad viewed from outside)
    ((0, 0, 1), [(-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]),
    ((0, 0, -1), [(0.5, -0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5)]),
    ((0, 1, 0), [(-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5)]),
    ((0, -1, 0), [(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5), (-0.5, -0.5, 0.5)]),
    ((1, 0, 0), [(0.5, -0.5, 0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5)]),
    ((-1, 0, 0), [(-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5)]),
]


class _GlbBuilder:
    def __init__(self):
        self.buffer = bytearray()
        self.buffer_views: list[dict] = []
        self.accessors: list[dict] = []
        self.materials: list[dict] = []
        self.meshes: list[dict] = []
        self.nodes: list[dict] = []
        self._material_cache: dict[tuple, int] = {}
        self._box_positions_idx = None
        self._box_normals_idx = None
        self._box_indices_idx = None

    def _pad_to(self, align: int) -> None:
        rem = len(self.buffer) % align
        if rem:
            self.buffer.extend(b"\x00" * (align - rem))

    def _add_view(self, data: bytes, target: int | None) -> int:
        self._pad_to(4)
        offset = len(self.buffer)
        self.buffer.extend(data)
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        if target is not None:
            view["target"] = target
        self.buffer_views.append(view)
        return len(self.buffer_views) - 1

    def _add_accessor(self, data: bytes, count: int, comp_type: int, type_: str,
                       target: int, mins=None, maxs=None) -> int:
        view_idx = self._add_view(data, target)
        acc = {
            "bufferView": view_idx,
            "componentType": comp_type,
            "count": count,
            "type": type_,
        }
        if mins is not None:
            acc["min"] = mins
        if maxs is not None:
            acc["max"] = maxs
        self.accessors.append(acc)
        return len(self.accessors) - 1

    def _ensure_box_geometry(self) -> tuple[int, int, int]:
        if self._box_positions_idx is not None:
            return self._box_positions_idx, self._box_normals_idx, self._box_indices_idx

        positions = []
        normals = []
        indices = []
        for normal, corners in _FACES:
            base = len(positions)
            for corner in corners:
                positions.append(corner)
                normals.append(normal)
            indices += [base, base + 1, base + 2, base, base + 2, base + 3]

        pos_bytes = b"".join(struct.pack("<3f", *p) for p in positions)
        norm_bytes = b"".join(struct.pack("<3f", *n) for n in normals)
        idx_bytes = b"".join(struct.pack("<H", i) for i in indices)

        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        zs = [p[2] for p in positions]

        self._box_positions_idx = self._add_accessor(
            pos_bytes, len(positions), 5126, "VEC3", 34962,
            mins=[min(xs), min(ys), min(zs)], maxs=[max(xs), max(ys), max(zs)],
        )
        self._box_normals_idx = self._add_accessor(
            norm_bytes, len(normals), 5126, "VEC3", 34962
        )
        self._box_indices_idx = self._add_accessor(
            idx_bytes, len(indices), 5123, "SCALAR", 34963,
            mins=[min(indices)], maxs=[max(indices)],
        )
        return self._box_positions_idx, self._box_normals_idx, self._box_indices_idx

    def _material_for(self, color: tuple[float, float, float]) -> int:
        key = tuple(round(c, 3) for c in color)
        if key in self._material_cache:
            return self._material_cache[key]
        idx = len(self.materials)
        self.materials.append(
            {
                "pbrMetallicRoughness": {
                    "baseColorFactor": [key[0], key[1], key[2], 1.0],
                    "metallicFactor": 0.15,
                    "roughnessFactor": 0.75,
                }
            }
        )
        self._material_cache[key] = idx
        return idx

    def add_box(self, color, center_m, size_m, name: str) -> None:
        pos_idx, norm_idx, idx_idx = self._ensure_box_geometry()
        mat_idx = self._material_for(color)
        mesh_idx = len(self.meshes)
        self.meshes.append(
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": pos_idx, "NORMAL": norm_idx},
                        "indices": idx_idx,
                        "material": mat_idx,
                    }
                ]
            }
        )
        self.nodes.append(
            {
                "name": name,
                "mesh": mesh_idx,
                "translation": list(center_m),
                "scale": list(size_m),
            }
        )

    def to_glb_bytes(self) -> bytes:
        gltf = {
            "asset": {"version": "2.0", "generator": "pcba-builder"},
            "scene": 0,
            "scenes": [{"nodes": list(range(len(self.nodes)))}],
            "nodes": self.nodes,
            "meshes": self.meshes,
            "materials": self.materials,
            "accessors": self.accessors,
            "bufferViews": self.buffer_views,
            "buffers": [{"byteLength": len(self.buffer)}],
        }
        json_bytes = json.dumps(gltf).encode("utf-8")
        pad = (4 - len(json_bytes) % 4) % 4
        json_bytes += b" " * pad

        bin_bytes = bytes(self.buffer)
        pad = (4 - len(bin_bytes) % 4) % 4
        bin_bytes += b"\x00" * pad

        json_chunk = struct.pack("<II", len(json_bytes), 0x4E4F534A) + json_bytes
        bin_chunk = struct.pack("<II", len(bin_bytes), 0x004E4942) + bin_bytes
        total_len = 12 + len(json_chunk) + len(bin_chunk)
        header = struct.pack("<4sII", b"glTF", 2, total_len)
        return header + json_chunk + bin_chunk


def export_glb(
    project_dir: Path,
    project_name: str,
    resolved: list[tuple[PartInstance, Package]],
    positions: list[tuple[float, float]],
    board_w_mm: float,
    board_h_mm: float,
) -> Path:
    builder = _GlbBuilder()

    builder.add_box(
        _BOARD_COLOR,
        center_m=(board_w_mm / 2000.0, -_BOARD_THICKNESS_MM / 2000.0, board_h_mm / 2000.0),
        size_m=(board_w_mm / 1000.0, _BOARD_THICKNESS_MM / 1000.0, board_h_mm / 1000.0),
        name="board",
    )

    for (inst, pkg), (x, y) in zip(resolved, positions):
        builder.add_box(
            pkg.color,
            center_m=(x / 1000.0, pkg.body_z_mm / 2000.0, y / 1000.0),
            size_m=(pkg.body_w_mm / 1000.0, pkg.body_z_mm / 1000.0, pkg.body_h_mm / 1000.0),
            name=inst.refdes,
        )

    out_path = project_dir / f"{project_name}.glb"
    out_path.write_bytes(builder.to_glb_bytes())
    return out_path
