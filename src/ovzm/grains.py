# ---------------------------------------------------------------------------
# ovito-auto-viz -- declarative, reproducible OVITO visualization
# https://github.com/biterik/ovito-auto-viz
# Author: Erik Bitzek <e.bitzek@mpi-susmat.de>  (ORCID 0000-0001-7430-3694)
#   1) Max-Planck-Institut for Sustainable Materials, Duesseldorf, Germany
#   2) Institute of Materials Simulation (WW8), Friedrich-Alexander-
#      Universitaet Erlangen-Nuernberg (FAU), Fuerth, Germany
# Funded by the Deutsche Forschungsgemeinschaft (DFG) -- NFDI 38/1,
# project number 460247524 (NFDI-MatWerk consortium).
# License: BSD-3-Clause (see LICENSE)
# ---------------------------------------------------------------------------
"""Per-grain coordinate tripods: parsing, validation, and frame math.

The card's `grains:` block (or an external grains file of the same shape)
lists one entry per grain: a REQUIRED origin (Å, sim frame) and REQUIRED
x/y/z Miller triplets — the crystal directions of THIS grain lying along the
simulation-box axes, identical semantics to the top-level `crystal:` block.
Origins and orientations are always user-provided; ovzm never guesses them
(no segmentation, no metadata sniffing). An incomplete block is a hard,
readable error, never a silent fallback.

This module is deliberately free of any `ovito` import so that validation
(`ovzm validate`) and the unit tests run without the ovito module installed;
the actual overlay drawing lives in scene.py.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import yaml

from .crystal import Orientation, miller_str

DEFAULT_SIZE_FRACTION = 0.05   # of the largest box edge ...
DEFAULT_SIZE_MIN_A = 10.0      # ... but never shorter than this (Å)


class GrainsError(ValueError):
    """A malformed `grains:` block — always names the offending grain/key."""


def _err(msg: str) -> GrainsError:
    return GrainsError(f"grains: {msg}")


def axis_label(v) -> str:
    """Miller label for a tripod arm.

    Integer triplets use the existing Miller formatting (smallest-integer
    reduction, '[4-30]' style). Float triplets (segmentation-derived
    orientations) are rendered from the values as given, <=3 decimals.
    """
    arr = np.asarray(v, dtype=float)
    if np.allclose(arr, np.round(arr), atol=1e-9):
        return miller_str([int(round(x)) for x in arr])
    body = " ".join(f"{x:.3f}".rstrip("0").rstrip(".") for x in arr)
    return f"[{body}]"


def _check_triplet(val, what: str, grain: str):
    if (not isinstance(val, (list, tuple)) or len(val) != 3
            or not all(isinstance(x, (int, float)) and not isinstance(x, bool)
                       for x in val)):
        raise _err(f"grain '{grain}': {what} must be a triplet of numbers, "
                   f"got {val!r}")
    return [float(x) for x in val]


def _check_arm_axes(val, where: str):
    """'box' or a list of exactly 3 Miller triplets."""
    if val == "box":
        return "box"
    if isinstance(val, (list, tuple)) and len(val) == 3:
        return [_check_triplet(t, f"axes[{i}]", where) for i, t in enumerate(val)]
    raise _err(f"{where}: axes must be 'box' or a list of exactly 3 Miller "
               f"triplets, got {val!r}")


def _load_grains_file(path: Path) -> list:
    if not path.is_file():
        raise _err(f"grains file not found: {path}")
    try:
        doc = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise _err(f"grains file {path} is not valid YAML: {exc}")
    if not isinstance(doc, dict) or not isinstance(doc.get("grains"), list):
        raise _err(f"grains file {path} must be a mapping with a top-level "
                   "'grains:' list")
    return doc["grains"]


def _arms_for(orientation: Orientation, xyz_given, arm_axes):
    """The three arms of one tripod: unit sim-frame directions + labels.

    'box' mode: arms along the sim-box axes ex/ey/ez, labeled with the
    grain's x/y/z triplets (mirrors the corner tripod, per grain).
    Triplet mode: each arm along that crystal direction of the grain,
    transformed to the sim frame via the grain's orientation matrix.
    """
    arms = []
    if arm_axes == "box":
        for i, (unit, given) in enumerate(zip(np.eye(3), xyz_given)):
            arms.append({"direction_sim": [float(c) for c in unit],
                         "label": axis_label(given)})
    else:
        for t in arm_axes:
            d = orientation.crystal_to_sim(t)
            n = float(np.linalg.norm(d))
            if n < 1e-9:
                raise _err(f"axes triplet {t} is a null direction")
            arms.append({"direction_sim": [float(c) for c in d / n],
                         "label": axis_label(t)})
    return arms


def resolve_grains(card: dict):
    """Parse + validate the card's `grains:` block. Returns None if absent.

    Raises GrainsError (a ValueError) with a readable, grain-naming message
    on any problem — this runs in `ovzm validate` as well as before every
    render. The returned dict is fully resolved except for the default
    tripod size and the origin-inside-box check, which need the simulation
    cell (finalize_grains()).
    """
    block = card.get("grains")
    if block is None:
        return None
    if not isinstance(block, dict):
        raise _err("must be a mapping with 'file' or 'items'")

    has_file, has_items = "file" in block, "items" in block
    if has_file == has_items:  # both or neither
        raise _err("provide exactly ONE of 'file' (external grains file) or "
                   "'items' (inline list) — "
                   + ("both were given" if has_file else "neither was given"))

    file_sha256 = None
    if has_file:
        base = Path(card.get("_card_dir", "."))
        p = Path(block["file"])
        path = (p if p.is_absolute() else base / p).resolve()
        raw_items = _load_grains_file(path)
        file_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        source = str(path)
    else:
        raw_items = block["items"]
        source = "inline"
    if not isinstance(raw_items, list) or not raw_items:
        raise _err(f"{'file ' + source if has_file else 'items'} must contain "
                   "a non-empty list of grains")

    tripod_cfg = block.get("tripod") or {}
    if not isinstance(tripod_cfg, dict):
        raise _err("tripod must be a mapping (size / axes / show_names)")
    size = tripod_cfg.get("size")
    if size is not None:
        if not isinstance(size, (int, float)) or isinstance(size, bool) or size <= 0:
            raise _err(f"tripod.size must be a positive length in Å, got {size!r}")
        size = float(size)
    default_axes = _check_arm_axes(tripod_cfg.get("axes", "box"), "tripod")
    show_names = bool(tripod_cfg.get("show_names", False))

    grains = []
    seen_names = set()
    for i, item in enumerate(raw_items):
        auto_name = f"g{i + 1}"
        if not isinstance(item, dict):
            raise _err(f"grain #{i + 1} must be a mapping, got {item!r}")
        name = str(item.get("name") or auto_name)
        for key in ("origin", "x", "y", "z"):
            if key not in item:
                raise _err(f"grain '{name}': missing required key '{key}'")
        origin = _check_triplet(item["origin"], "origin", name)
        x = _check_triplet(item["x"], "x", name)
        y = _check_triplet(item["y"], "y", name)
        z = _check_triplet(item["z"], "z", name)
        try:
            orientation = Orientation(x, y, z)
        except ValueError as exc:  # reuse crystal.py's error text, name the grain
            raise _err(f"grain '{name}': {exc}")
        arm_axes = (_check_arm_axes(item["axes"], f"grain '{name}'")
                    if "axes" in item else default_axes)
        if name in seen_names:
            raise _err(f"duplicate grain name '{name}'")
        seen_names.add(name)
        grains.append({
            "name": name,
            "origin": origin,
            "x": x, "y": y, "z": z,
            "orientation": orientation,
            "arm_mode": "box" if arm_axes == "box" else "axes",
            "arm_axes": arm_axes,
            "arms": _arms_for(orientation, (x, y, z), arm_axes),
        })

    return {
        "source": source,
        "file_sha256": file_sha256,
        "tripod": {"size": size, "show_names": show_names,
                   "default_axes": default_axes},
        "grains": grains,
    }


def finalize_grains(resolved: dict, cell) -> dict:
    """Resolve what needs the simulation cell: the default arm length and
    the origin-inside-box warning (outside box + 10% margin: WARN, still
    drawn — a tripod deliberately placed outside is legal)."""
    m = np.asarray(cell, dtype=float)  # ovito cell: 3x4 (edges | origin)
    edges, cell_origin = m[:, :3], (m[:, 3] if m.shape[1] == 4 else np.zeros(3))
    if resolved["tripod"]["size"] is None:
        longest = float(max(np.linalg.norm(edges[:, i]) for i in range(3)))
        resolved["tripod"]["size"] = max(DEFAULT_SIZE_FRACTION * longest,
                                         DEFAULT_SIZE_MIN_A)
    inv = np.linalg.inv(edges)
    for g in resolved["grains"]:
        frac = inv @ (np.asarray(g["origin"]) - cell_origin)
        if np.any(frac < -0.1) or np.any(frac > 1.1):
            print(f"[ovzm] warning: grain '{g['name']}' origin "
                  f"{g['origin']} lies outside the simulation box "
                  "(+10% margin); its tripod is drawn anyway",
                  file=sys.stderr)
    return resolved


def grains_prov(resolved: dict) -> dict:
    """The resolved grains block for the .prov.yaml (plain YAML-safe types):
    source + file hash, the fully resolved per-grain list, and the resolved
    tripod styling — enough to reconstruct every tripod without the card."""
    tri = resolved["tripod"]
    out = {
        "source": resolved["source"],
        "tripod": {"size_A": tri["size"], "show_names": tri["show_names"]},
        "grains": [],
    }
    if resolved["file_sha256"]:
        out["file_sha256"] = resolved["file_sha256"]
    for g in resolved["grains"]:
        out["grains"].append({
            "name": g["name"],
            "origin_A": g["origin"],
            "x": g["x"], "y": g["y"], "z": g["z"],
            "arm_mode": g["arm_mode"],
            "arm_axes": ("box" if g["arm_axes"] == "box"
                         else [list(t) for t in g["arm_axes"]]),
            "arms": [{"direction_sim": [round(c, 6) for c in a["direction_sim"]],
                      "label": a["label"]} for a in g["arms"]],
        })
    return out
