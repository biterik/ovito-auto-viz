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
"""Crystal-frame <-> simulation-frame math and Miller-index formatting."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Miller formatting


def miller_str(v, *, frac=None) -> str:
    """[-1,0,1] -> '[-101]'; overbar-free ASCII form. frac prefixes e.g. '1/2'."""
    ints = smallest_ints(v)
    if any(abs(i) > 9 for i in ints):
        # multi-digit indices concatenate ambiguously ('[2-1311]');
        # space-separate them: '[2 -13 11]'
        body = " ".join(str(i) for i in ints)
    else:
        body = "".join(_digit(i) for i in ints)
    return f"{frac}[{body}]" if frac else f"[{body}]"


def _digit(i: int) -> str:
    return str(i) if 0 <= i <= 9 else (f"-{abs(i)}" if i < 0 else str(i))


def smallest_ints(v, tol=1e-3):
    """Scale a rational direction to smallest integer triplet."""
    v = np.asarray(v, dtype=float)
    if np.allclose(v, 0):
        return [0, 0, 0]
    # try multipliers up to 12 (covers 1/2<110>, 1/6<112>, 1/3<111>, 1/6<110>)
    for m in range(1, 13):
        w = v * m / np.max(np.abs(v[np.abs(v) > tol]))
        for scale in range(1, 13):
            cand = w * scale
            if np.allclose(cand, np.round(cand), atol=5e-2):
                ints = np.round(cand).astype(int)
                g = np.gcd.reduce(np.abs(ints[ints != 0])) if np.any(ints) else 1
                return list(ints // max(g, 1))
    return [int(round(x)) for x in v]


def burgers_str(b_lattice) -> str:
    """True Burgers vector in lattice coords -> '1/6[112]'-style string.

    DXA reports true_burgers_vector in fractional lattice units, e.g.
    [0.5, 0, -0.5] for a/2[10-1] or [1/6, 1/6, -1/3]... find nice fraction.
    """
    b = np.asarray(b_lattice, dtype=float)
    if np.allclose(b, 0):
        return "[000]"
    for denom in (1, 2, 3, 6, 4, 12):
        cand = b * denom
        if np.allclose(cand, np.round(cand), atol=2e-2):
            ints = np.round(cand).astype(int)
            g = np.gcd.reduce(np.abs(ints[ints != 0])) if np.any(ints) else 1
            ints = ints // max(g, 1)
            denom2 = denom // max(g, 1) if denom % max(g, 1) == 0 else denom
            frac = None if denom2 <= 1 else f"1/{denom2}"
            return miller_str(ints, frac=frac)
    return "[" + " ".join(f"{x:+.2f}" for x in b) + "]"


# ---------------------------------------------------------------------------
# Orientation


class Orientation:
    """Maps cubic-crystal directions to simulation-box directions.

    Defined by the crystal directions along the sim x/y/z axes,
    e.g. x=[-101], y=[1,-2,1], z=[111].
    """

    def __init__(self, x, y=None, z=None):
        x = np.asarray(x, dtype=float)
        if y is None and z is not None:
            z = np.asarray(z, dtype=float)
            y = np.cross(z, x)
        elif z is None and y is not None:
            y = np.asarray(y, dtype=float)
            z = np.cross(x, y)
        else:
            y = np.asarray(y, dtype=float)
            z = np.asarray(z, dtype=float)
        M = np.array([x / np.linalg.norm(x),
                      y / np.linalg.norm(y),
                      z / np.linalg.norm(z)])
        if not np.allclose(M @ M.T, np.eye(3), atol=1e-3):
            raise ValueError("crystal axes are not mutually orthogonal: "
                             f"x={[float(v) for v in x]}, "
                             f"y={[float(v) for v in y]}, "
                             f"z={[float(v) for v in z]}")
        if np.linalg.det(M) < 0:
            raise ValueError("crystal axes form a left-handed frame")
        self.M = M            # rows: crystal directions of sim x,y,z (unit)
        self.axes = (smallest_ints(x), smallest_ints(y), smallest_ints(z))

    def crystal_to_sim(self, v):
        """Crystal-frame vector -> sim-frame components (unit-preserving)."""
        return self.M @ np.asarray(v, dtype=float)

    def sim_to_crystal(self, v):
        return self.M.T @ np.asarray(v, dtype=float)

    def axis_labels(self):
        return tuple(miller_str(a) for a in self.axes)


_FNAME_RE = re.compile(r"x(-?[0-9]+)_y(-?[0-9]+)_z(-?[0-9]+)")


def _split_triplet(tok: str):
    """'-101' -> [-1,0,1]; '1-21' -> [1,-2,1] (single digits, sign prefixes)."""
    out, sign = [], 1
    for ch in tok:
        if ch == "-":
            sign = -1
        else:
            out.append(sign * int(ch))
            sign = 1
    if len(out) != 3:
        raise ValueError(f"cannot parse Miller triplet '{tok}'")
    return out


def orientation_from_filename(name: str) -> Orientation | None:
    """Parse the x-101_y1-21_z111 convention out of a file name, if present."""
    m = _FNAME_RE.search(Path(name).name)
    if not m:
        return None
    x, y, z = (_split_triplet(t) for t in m.groups())
    return Orientation(x, y, z)


def resolve_orientation(card: dict, input_file: str) -> Orientation | None:
    cr = card.get("crystal", {}) or {}
    if all(k in cr for k in ("x",)) and (("y" in cr) or ("z" in cr)):
        if cr.get("x") == "auto":
            return orientation_from_filename(input_file)
        return Orientation(cr["x"], cr.get("y"), cr.get("z"))
    if cr.get("orientation", "auto") == "auto" or cr.get("x") == "auto":
        return orientation_from_filename(input_file)
    return None
