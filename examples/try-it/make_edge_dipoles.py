#!/usr/bin/env python3
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
"""Generate a small fcc Ni crystal with an edge-dislocation QUADRUPOLE (full PBC).

numpy-only, no LAMMPS required. Four edge dislocations
(b = +/- a/2[1-10], lines along [-1-12] = z, glide planes (111)) are
inserted as isotropic-elasticity (Volterra) displacement fields in the
classic QUADRUPOLE arrangement -- two opposite dipoles on two glide
planes -- in a FULLY periodic orthogonal box: the plastic shears of the
two dipoles cancel, so no box tilt is needed, there are no free surfaces,
and the total Burgers vector content of the box is zero.

The output `edge-dipoles.dump` is a LAMMPS dump file with NO metadata
beyond positions -- everything the figure will say about the dislocations
(b, xi, character, a) is computed from the data by `ovzm`/DXA. Ground
truth for the tests: exactly 4 perfect a/2<110> segments, all 90 deg
edge, net b = 0, a ~ 3.52 A.
"""
import numpy as np

A0 = 3.52          # Ni lattice constant (A)
NU = 0.30          # Poisson ratio for the Volterra field
NX, NY, NZ = 36, 16, 4   # periods along x/y/z (see periods below)

# orthonormal crystal frame of the box: x=[1-10], y=[111], z=[-1-12]
EX = np.array([1.0, -1.0, 0.0]); EX /= np.linalg.norm(EX)
EY = np.array([1.0, 1.0, 1.0]);  EY /= np.linalg.norm(EY)
EZ = np.array([-1.0, -1.0, 2.0]); EZ /= np.linalg.norm(EZ)
R = np.vstack([EX, EY, EZ])          # cubic -> box rotation

PX = A0 / np.sqrt(2.0)               # period along [1-10]
PY = A0 * np.sqrt(3.0)               # period along [111]
PZ = A0 * np.sqrt(6.0) / 2.0         # period along [-1-12]
B = A0 / np.sqrt(2.0)                # |b| of a/2<110>


def fcc_block():
    """fcc lattice points inside the box, by EXACT integer construction.

    In the box frame the fcc primitive vectors are
        v1 = (PX, 0, 0),  v2 = (PX/2, 0, PZ/2),  v3 = (PX/2, PY/3, PZ/6),
    so every atom is  x = m * PX/2,  y = k * PY/3,  z = n * PZ/6  with
        m = (2i + j + k) mod 2*NX,   k mod 3*NY,   n = (3j + k) mod 6*NZ.
    Enumerating i in [0,NX), j in [0,2*NZ), k in [0,3*NY) yields every atom
    of the periodic supercell exactly once -- no epsilon filtering, no
    duplicate or missing boundary rows (4*NX*NY*NZ*... = 24*NX*NY*NZ atoms).
    """
    lx, ly, lz = NX * PX, NY * PY, NZ * PZ
    i = np.arange(NX)
    j = np.arange(2 * NZ)
    k = np.arange(3 * NY)
    I, J, K = np.meshgrid(i, j, k, indexing="ij")
    m = (2 * I + J + K) % (2 * NX)
    n = (3 * J + K) % (6 * NZ)
    pos = np.stack([m.ravel() * PX / 2,
                    K.ravel() * PY / 3,
                    n.ravel() * PZ / 6], axis=1)
    return pos, (lx, ly, lz)


def edge_displacement(x, y):
    """Isotropic Volterra field of an edge dislocation, b=B along x."""
    r2 = x * x + y * y
    ux = B / (2 * np.pi) * (np.arctan2(y, x) + x * y / (2 * (1 - NU) * r2))
    uy = -B / (2 * np.pi) * ((1 - 2 * NU) / (4 * (1 - NU)) * np.log(r2 / (B * B))
                             + (x * x - y * y) / (4 * (1 - NU) * r2))
    return ux, uy


def main(out="edge-dipoles.dump"):
    pos, (lx, ly, lz) = fcc_block()
    # quadrupole: (x, y, sign) -- two opposite dipoles on two (111) planes,
    # all cores BETWEEN atomic planes (avoid the singularity)
    cores = [(0.25 * lx + PX / 4, 0.25 * ly + PY / 12, +1),
             (0.75 * lx + PX / 4, 0.25 * ly + PY / 12, -1),
             (0.25 * lx + PX / 4, 0.75 * ly + PY / 12, -1),
             (0.75 * lx + PX / 4, 0.75 * ly + PY / 12, +1)]
    ux = np.zeros(len(pos)); uy = np.zeros(len(pos))
    for ix in range(-8, 9):          # periodic images: quadrupole decays fast,
    #  +-8 makes the boundary mismatch invisible to PTM
        for iy in range(-8, 9):
            for (cx0, cy0, sgn) in cores:
                dx = pos[:, 0] - cx0 - ix * lx
                dy = pos[:, 1] - cy0 - iy * ly
                a, b = edge_displacement(dx, dy)
                ux += sgn * a
                uy += sgn * b
    pos[:, 0] += ux
    pos[:, 1] += uy
    L = np.array([lx, ly, lz])
    pos -= np.floor(pos / L) * L      # wrap into the periodic box
    n = len(pos)
    with open(out, "w") as f:
        f.write("ITEM: TIMESTEP\n0\n")
        f.write(f"ITEM: NUMBER OF ATOMS\n{n}\n")
        f.write("ITEM: BOX BOUNDS pp pp pp\n")
        f.write(f"0.0 {lx:.6f}\n0.0 {ly:.6f}\n0.0 {lz:.6f}\n")
        f.write("ITEM: ATOMS id type x y z\n")
        for i, p in enumerate(pos, 1):
            f.write(f"{i} 1 {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}\n")
    print(f"wrote {out}: {n} atoms, box {lx:.1f} x {ly:.1f} x {lz:.1f} A, full PBC"
          f" (edge-dislocation quadrupole, b = +/- a/2[1-10], net b = 0)")


if __name__ == "__main__":
    main()
