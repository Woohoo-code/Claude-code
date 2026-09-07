"""Find and (best-effort) fetch 3D/footprint models for BOM parts online.

Two stages:
1. Ask `claude -p` (with WebSearch/WebFetch allowed) to look up each
   distinct MPN and write a manifest of candidate model/datasheet URLs -
   it can't download binary files itself, only find and report links.
2. We read that manifest and attempt to download any link that points
   directly at a model file (by extension), bounded in size and count,
   through the environment's proxy/CA bundle. Anything behind a login
   wall or without a direct file link is left as a manifest entry for a
   human to fetch manually.
"""

from __future__ import annotations

import csv
import os
import shutil
import ssl
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from .bom import load_bom

_MODEL_EXTENSIONS = (".step", ".stp", ".iges", ".igs", ".wrl", ".glb", ".gltf")
_MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024

FIND_PROMPT_TEMPLATE = """\
You are sourcing 3D/footprint models for a PCBA bill of materials. Using
web search, look up each of these distinct parts:

{parts_list}

For each part, try to find:
- The manufacturer's datasheet URL.
- A direct, publicly downloadable 3D model or footprint file (STEP, IGES,
  WRL, GLB, or GLTF) - prefer the manufacturer's own site or a free,
  no-login page. Do not use paywalled or login-gated links.

Write `models/manifest.csv` in the current directory with header:
MPN,Manufacturer,Datasheet_URL,Model_URL,Model_Format,Source,License_Note

One row per part. If no direct model file link exists, leave Model_URL
blank and use License_Note to say where a human could get one (e.g.
"available via SnapEDA account" or "generic package - use pcba-builder's
generated KiCad footprint instead"). Do not fabricate URLs - leave a field
blank rather than guess.
"""


def _ssl_context() -> ssl.SSLContext:
    ca_bundle = "/root/.ccr/ca-bundle.crt"
    if os.path.exists(ca_bundle):
        return ssl.create_default_context(cafile=ca_bundle)
    return ssl.create_default_context()


def build_find_prompt(project_dir: Path) -> str | None:
    bom_path = project_dir / "bom.csv"
    if not bom_path.exists():
        return None
    instances, _warnings = load_bom(bom_path)
    seen = {}
    for inst in instances:
        key = inst.line.mpn or inst.line.description
        if key and key not in seen:
            seen[key] = inst.line
    if not seen:
        return None
    parts_list = "\n".join(
        f"- MPN: {line.mpn or '(none given)'} | Manufacturer: {line.manufacturer or '?'} | "
        f"Description: {line.description}"
        for line in seen.values()
    )
    return FIND_PROMPT_TEMPLATE.format(parts_list=parts_list)


def run_online_search(project_dir: Path, model: str | None) -> int:
    prompt = build_find_prompt(project_dir)
    if prompt is None:
        print("error: no bom.csv (or no parts in it) - run `pcba-builder build` first")
        return 1
    if not shutil.which("claude"):
        print("error: the `claude` CLI was not found on PATH")
        return 1
    (project_dir / "models").mkdir(exist_ok=True)
    cmd = [
        "claude",
        "-p",
        prompt,
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        "Write Edit Read WebSearch WebFetch",
        "--add-dir",
        str(project_dir),
    ]
    if model:
        cmd += ["--model", model]
    return subprocess.run(cmd, cwd=project_dir).returncode


def download_found_models(project_dir: Path, max_files: int = 25) -> list[str]:
    """Best-effort download of direct model file links from models/manifest.csv.
    Returns a list of human-readable log lines."""
    manifest_path = project_dir / "models" / "manifest.csv"
    log: list[str] = []
    if not manifest_path.exists():
        log.append("No models/manifest.csv found - nothing to download.")
        return log

    ctx = _ssl_context()
    downloaded = 0
    with manifest_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if downloaded >= max_files:
                log.append(f"Stopped after {max_files} downloads (limit).")
                break
            mpn = (row.get("MPN") or "unknown").strip()
            url = (row.get("Model_URL") or "").strip()
            if not url:
                continue
            ext = next((e for e in _MODEL_EXTENSIONS if url.lower().endswith(e)), None)
            if not ext:
                log.append(f"{mpn}: skipped (URL doesn't look like a direct model file): {url}")
                continue
            safe_mpn = "".join(c if c.isalnum() or c in "-_." else "_" for c in mpn)
            dest = project_dir / "models" / f"{safe_mpn}{ext}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "pcba-builder/0.1"})
                with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                    data = resp.read(_MAX_DOWNLOAD_BYTES + 1)
                    if len(data) > _MAX_DOWNLOAD_BYTES:
                        log.append(f"{mpn}: skipped (exceeds {_MAX_DOWNLOAD_BYTES} byte limit)")
                        continue
                    dest.write_bytes(data)
                log.append(f"{mpn}: downloaded {len(data)} bytes -> {dest.name}")
                downloaded += 1
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                log.append(f"{mpn}: download failed ({exc}) - left as manifest link: {url}")
    return log
