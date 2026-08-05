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
"""Auto-generated annotations: everything is computed from the data itself.

Metadata (e.g. dcreator .disparam files) is never REQUIRED — nucleated
dislocations carry no metadata, so labels derive from DXA/PTM output.

Frame discipline (the "80° edge" lesson): DXA's true_burgers_vector lives in
DXA's OWN lattice frame, which may differ from the card's crystal frame by a
cubic symmetry operation. All geometry (line direction, character angle,
crystal-frame Miller indices) therefore uses the segment's SPATIAL Burgers
vector (simulation frame); true_burgers_vector is used only for the
frame-independent family classification and the |b_spatial|/|b_true| lattice
constant estimate.
"""
from __future__ import annotations

import numpy as np

from .crystal import Orientation, burgers_str, miller_str, smallest_ints

FAMILY_NAMES_FCC = {
    "1/2<110>": "perfect",
    "1/6<112>": "Shockley partial",
    "1/6<110>": "stair-rod",
    "1/3<100>": "Hirth",
    "1/3<111>": "Frank",
}


def classify_family(b_lattice) -> str:
    b = np.asarray(b_lattice, dtype=float)
    for denom, fam in ((2, "1/2<110>"), (6, "1/6<112>"), (6, "1/6<110>"),
                       (3, "1/3<100>"), (3, "1/3<111>")):
        cand = b * denom
        if np.allclose(cand, np.round(cand), atol=2e-2):
            ints = np.abs(np.sort(np.abs(np.round(cand).astype(int))))[::-1]
            key = {"1/2<110>": [1, 1, 0], "1/6<112>": [2, 1, 1],
                   "1/6<110>": [1, 1, 0], "1/3<100>": [1, 0, 0],
                   "1/3<111>": [1, 1, 1]}[fam]
            if list(ints) == sorted(key, reverse=True):
                return fam
    return "other"


def segment_line_direction(points: np.ndarray) -> np.ndarray:
    """Dominant line direction of a segment polyline (sim frame, unit)."""
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return np.array([0.0, 0.0, 0.0])
    d = pts[-1] - pts[0]
    n = np.linalg.norm(d)
    if n < 1e-6:  # closed loop: use PCA of the points instead
        c = pts - pts.mean(axis=0)
        _, _, vt = np.linalg.svd(c, full_matrices=False)
        return vt[0]
    return d / n


def character_angle(b_sim, xi_sim) -> float:
    """Angle between (spatial) Burgers vector and line direction, deg [0,90]."""
    b_sim = np.asarray(b_sim, dtype=float)
    xi_sim = np.asarray(xi_sim, dtype=float)
    nb, nx = np.linalg.norm(b_sim), np.linalg.norm(xi_sim)
    if nb < 1e-9 or nx < 1e-9:
        return float("nan")
    c = abs(float(np.dot(b_sim, xi_sim)) / (nb * nx))
    return float(np.degrees(np.arccos(min(1.0, c))))


def character_name(angle: float) -> str:
    """Conservative naming: only near-pure characters get a name."""
    if np.isnan(angle):
        return "?"
    if angle >= 85:
        return "edge"
    if angle <= 5:
        return "screw"
    return "mixed"


def _b_in_crystal_frame(sb_sim, tb_lat, orientation: Orientation):
    """Spatial b (sim frame, Å) -> Miller string in the CARD's crystal frame,
    scaled so its length equals |true_b| (lattice units)."""
    sb = np.asarray(sb_sim, dtype=float)
    n_sb = np.linalg.norm(sb)
    n_tb = float(np.linalg.norm(tb_lat))
    if n_sb < 1e-9 or n_tb < 1e-9:
        return burgers_str(tb_lat)
    b_cr = orientation.sim_to_crystal(sb) / n_sb * n_tb
    return burgers_str(b_cr)


def dxa_summary(data, orientation: Orientation | None, *, max_segments=6) -> dict:
    """Extract everything label-worthy from a DXA-carrying DataCollection."""
    out = {"segments": [], "families": {}, "total_length": 0.0}
    disl = getattr(data, "dislocations", None)
    if disl is None:
        return out
    segs = sorted(disl.segments, key=lambda s: -s.length)
    a_estimates = []
    for seg in segs:
        tb = np.asarray(seg.true_burgers_vector, dtype=float)
        sb = np.asarray(seg.spatial_burgers_vector, dtype=float)
        fam = classify_family(tb)
        out["families"].setdefault(fam, [0, 0.0])
        out["families"][fam][0] += 1
        out["families"][fam][1] += seg.length
        out["total_length"] += seg.length
        xi_sim = segment_line_direction(np.asarray(seg.points))
        ang = character_angle(sb, xi_sim)
        n_tb, n_sb = np.linalg.norm(tb), np.linalg.norm(sb)
        if n_tb > 1e-9 and n_sb > 1e-9:
            a_estimates.append(n_sb / n_tb)
        entry = {
            "family": fam,
            "family_name": FAMILY_NAMES_FCC.get(fam, fam),
            "length": float(seg.length),
            "char_angle": ang,
            "char": character_name(ang),
            "is_loop": bool(getattr(seg, "is_loop", False)),
            "is_infinite": bool(getattr(seg, "is_infinite_line", False)),
            "spatial_b_sim": [float(x) for x in sb],
        }
        if orientation is not None:
            entry["b"] = _b_in_crystal_frame(sb, tb, orientation)
            entry["xi"] = miller_str(smallest_ints(orientation.sim_to_crystal(xi_sim)))
            entry["frame"] = "crystal (card)"
        else:
            # no orientation known: indices are in DXA's own lattice frame
            entry["b"] = burgers_str(tb)
            entry["frame"] = "DXA lattice"
        out["segments"].append(entry)

    # net Burgers vector over all segments (spatial frame, sign-consistent
    # only if DXA oriented the lines consistently — skip if it cancels out)
    if segs:
        net = np.sum([np.asarray(s.spatial_burgers_vector) for s in segs], axis=0)
        max_b = max(np.linalg.norm(np.asarray(s.spatial_burgers_vector)) for s in segs)
        if np.linalg.norm(net) <= 0.3 * max_b and len(segs) > 1:
            out["net"] = {"b": "0", "zero": True}
        elif np.linalg.norm(net) > 0.3 * max_b and a_estimates:
            a_est = float(np.mean(a_estimates))
            xi_main = segment_line_direction(np.asarray(segs[0].points))
            ang = character_angle(net, xi_main)
            net_entry = {"char_angle": ang, "char": character_name(ang)}
            if orientation is not None:
                net_entry["b"] = burgers_str(orientation.sim_to_crystal(net) / a_est)
            out["net"] = net_entry
        if a_estimates:
            out["a_estimate"] = round(float(np.mean(a_estimates)), 4)
    out["n_segments"] = len(segs)
    out["shown_segments"] = out["segments"][:max_segments]
    return out


def composition_summary(data) -> dict:
    parts = getattr(data, "particles", None)
    if parts is None or parts.particle_types is None:
        return {}
    tprop = parts.particle_types
    counts = {}
    arr = np.asarray(tprop)
    for t in tprop.types:
        counts[t.name or f"type {t.id}"] = int(np.sum(arr == t.id))
    total = int(len(arr))
    return {"counts": counts, "total": total}


def build_label_text(card, data, orientation, dxa, full_data=None) -> str:
    """Compose the auto-annotation text block.

    `data` is the (possibly filtered) pipeline output; `full_data` the
    unfiltered source frame, used for the overall composition.
    """
    lines = []
    ts = data.attributes.get("Timestep")
    if ts is not None:
        lines.append(f"step {ts}")
    comp = composition_summary(full_data if full_data is not None else data)
    if comp and len(comp["counts"]) > 1:
        parts = ", ".join(f"{n}: {c}" for n, c in comp["counts"].items())
        minority_name, minority = min(comp["counts"].items(), key=lambda kv: kv[1])
        lines.append(f"{comp['total']} atoms ({parts})")
        lines.append(f"x({minority_name}) = {minority/comp['total']:.4f}")
        shown = composition_summary(data)
        if shown and shown["total"] != comp["total"]:
            lines.append(f"{shown['total']} atoms shown "
                         f"({', '.join(f'{n}: {c}' for n, c in shown['counts'].items())})")
    if dxa and dxa.get("n_segments"):
        lines.append(f"DXA: {dxa['n_segments']} segment(s), "
                     f"L = {dxa['total_length']:.0f} Å")
        if dxa.get("net", {}).get("b"):
            net = dxa["net"]
            if net.get("zero"):
                lines.append("  net b = 0 (closed box)")
            else:
                lines.append(f"  net b = {net['b']}, {net['char_angle']:.0f}° {net['char']}")
        for s in dxa["shown_segments"]:
            xi = f", ξ = {s['xi']}" if "xi" in s else ""
            ch = (f", {s['char_angle']:.0f}° {s['char']}"
                  if not np.isnan(s["char_angle"]) else "")
            tag = (" (PBC-infinite)" if s["is_infinite"]
                   else " (loop)" if s["is_loop"] else "")
            fam = f" ({s['family_name']})" if s["family"] != "other" else ""
            lines.append(f"  b = {s['b']}{fam}{xi}{ch}, L = {s['length']:.0f} Å{tag}")
        if any(s.get("frame") == "DXA lattice" for s in dxa["shown_segments"]):
            lines.append("  [b indices in DXA lattice frame — no crystal orientation given]")
        if dxa["n_segments"] > len(dxa["shown_segments"]):
            lines.append(f"  ... {dxa['n_segments'] - len(dxa['shown_segments'])} more")
    extra = (card.get("annotate", {}) or {}).get("extra")
    if extra:
        lines += [str(x) for x in (extra if isinstance(extra, list) else [extra])]
    return "\n".join(lines)
