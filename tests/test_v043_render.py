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
"""v0.4.3 features through the real OVITO pipeline and renderer.

- ptm.structures: an icosahedral cluster is classified ICO only when the
  template is enabled, and the ico structure colour reaches the image when
  dxa runs first;
- view.fov: the same absolute field of view for different box sizes, and
  recorded as such in the provenance;
- annotate.tripod_font_size / tripod_outline reach the tripod overlay.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ovito = pytest.importorskip("ovito")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_fcc import main as write_fcc  # noqa: E402

from ovzm.runner import _prepare, run_render  # noqa: E402

PHI = (1 + math.sqrt(5)) / 2


def write_ico_cluster(path, nn=2.5, box=30.0):
    """13-atom icosahedron (centre + 12 vertices) in a large box: PTM
    classifies the centre atom ICO -- if, and only if, the ICO template is
    enabled. Vertex coordinates (0, +-1, +-phi) and cyclic permutations,
    scaled so the centre-vertex distance is `nn` Angstrom."""
    verts = []
    for a in (-1, 1):
        for b in (-PHI, PHI):
            verts += [(0, a, b), (a, b, 0), (b, 0, a)]
    verts = np.array(verts, float)
    verts *= nn / np.linalg.norm(verts[0])
    pts = np.vstack([[0, 0, 0], verts]) + box / 2
    lines = ["ico cluster (ovzm test)", "", f"{len(pts)} atoms", "1 atom types", "",
             f"0 {box} xlo xhi", f"0 {box} ylo yhi", f"0 {box} zlo zhi", "",
             "Masses", "", "1 58.69", "", "Atoms # atomic", ""]
    lines += [f"{i + 1} 1 {x:.6f} {y:.6f} {z:.6f}" for i, (x, y, z) in enumerate(pts)]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(autouse=True)
def _clean_scene():
    yield
    for p in list(ovito.scene.pipelines):
        p.remove_from_scene()


def card_file(tmp_path, body, name="c.yaml"):
    p = tmp_path / name
    p.write_text("name: t\nmeta: {creator: test}\n" + body, encoding="utf-8")
    return str(p)


def structure_counts(data):
    st = np.asarray(data.particles["Structure Type"])
    return {int(k): int(v) for k, v in zip(*np.unique(st, return_counts=True))}


# --- ptm.structures ---------------------------------------------------------

def test_ico_template_enables_icosahedral_classification(tmp_path):
    write_ico_cluster(tmp_path / "ico.data")
    common = ("input: {file: ico.data}\natoms: {show: all, names: {1: Ni}}\n"
              "annotate: {colorbar: false, tripod: xyz}\n")
    _, _, _, data, *_ = _prepare(card_file(tmp_path, common + "pipeline: [{ptm: {}}]\n"))
    assert structure_counts(data).get(4, 0) == 0, "ICO is off by default"
    ovito.scene.pipelines.clear()
    _, _, _, data, *_ = _prepare(card_file(
        tmp_path, common + "pipeline: [{ptm: {structures: [ico]}}]\n", "c2.yaml"))
    assert structure_counts(data).get(4, 0) == 1, "the centre atom must be ICO"


def test_ico_colour_reaches_the_image_with_dxa_first(tmp_path):
    from PIL import Image
    write_ico_cluster(tmp_path / "ico.data")
    card = card_file(tmp_path,
                     "input: {file: ico.data}\n"
                     "crystal: {x: [1,0,0], y: [0,1,0], z: [0,0,1], lattice: fcc}\n"
                     "pipeline: [{dxa: {lattice: fcc}}, {ptm: {structures: [ico]}}]\n"
                     # all 13 atoms, small radii: viewed along y no vertex hides the centre
                     "atoms: {show: all, names: {1: Ni}, radius: 0.4,\n"
                     "        structure_colors: {ico: [1.0, 0.0, 0.0], other: [0.6, 0.6, 0.6]}}\n"
                     "view: {fov: 6}\n"
                     # an isolated cluster is all 'defect' for DXA: hide its mesh
                     "annotate: {colorbar: false, tripod: 'off', labels: 'off', defect_mesh: false}\n"
                     "output: {width: 200, height: 200, background: white, renderer: tachyon-fast}\n")
    out = run_render(card, str(tmp_path / "ico.png"))
    px = np.asarray(Image.open(out).convert("RGB"), float) / 255
    red = (px[..., 0] > 0.6) & (px[..., 1] < 0.35) & (px[..., 2] < 0.35)
    # one red atom of radius 0.4 A in a 12 x 12 A field: ~0.35 % of the pixels
    assert red.mean() > 0.001, f"no ico-coloured atom in the image (red fraction {red.mean():.4f})"


# --- view.fov ---------------------------------------------------------------

def test_view_fov_is_absolute_and_independent_of_box_size(tmp_path):
    fovs_fit, fovs_abs = [], []
    for n in (4, 7):
        write_fcc(str(tmp_path / f"fcc{n}.data"), n=n)
        base = (f"input: {{file: fcc{n}.data}}\natoms: {{show: all, names: {{1: Ni}}}}\n"
                "annotate: {colorbar: false}\n")
        _, _, _, _, vp, _, _ = _prepare(card_file(tmp_path, base, f"fit{n}.yaml"))
        fovs_fit.append(vp.fov)
        ovito.scene.pipelines.clear()
        _, _, _, _, vp, _, scene = _prepare(card_file(
            tmp_path, base + "view: {fov: 25.0, zoom: 3}\n", f"abs{n}.yaml"))
        fovs_abs.append(vp.fov)
        assert scene["camera"]["fov"] == pytest.approx(25.0)
        assert scene["camera"]["fov_source"].startswith("view.fov")
        ovito.scene.pipelines.clear()
    assert fovs_fit[1] > 1.5 * fovs_fit[0], "fit must follow the box size"
    assert fovs_abs == [pytest.approx(25.0)] * 2, "view.fov overrides fit and zoom"


def test_view_fov_shows_the_requested_height(tmp_path):
    """Ortho fov is a HALF-height in A: a 2 x 28 A tall cell rendered with
    fov = 14 fills the image height (the cell edges touch top and bottom)."""
    from PIL import Image
    write_fcc(str(tmp_path / "fcc.data"), n=8)     # 8 x 3.52 = 28.16 A cube
    card = card_file(tmp_path,
                     "input: {file: fcc.data}\natoms: {show: all, names: {1: Ni}, radius: 0.3}\n"
                     "view: {direction: front, fov: 28.16}\n"
                     "annotate: {colorbar: false, tripod: 'off', labels: 'off'}\n"
                     "output: {width: 300, height: 300, background: white, renderer: tachyon-fast}\n")
    out = run_render(card, str(tmp_path / "fov.png"))
    px = np.asarray(Image.open(out).convert("L"), float) / 255
    rows = np.where((px < 0.9).any(axis=1))[0]
    ink = (rows.max() - rows.min() + 1) / px.shape[0]
    # visible height = 2 x 28.16 A, cell = 28.16 A -> the atoms span ~half the image
    assert 0.40 < ink < 0.60, f"ink spans {ink:.2f} of the image height"


# --- tripod font size / outline ----------------------------------------------

def test_tripod_font_size_and_outline(tmp_path):
    from ovito.vis import CoordinateTripodOverlay
    write_fcc(str(tmp_path / "fcc.data"), n=4)
    base = ("input: {file: fcc.data}\natoms: {show: all, names: {1: Ni}}\n"
            "crystal: {x: [1,0,0], y: [0,1,0], z: [0,0,1], lattice: fcc}\n")

    def tripod(card_text, name):
        _, _, _, _, vp, _, _ = _prepare(card_file(tmp_path, base + card_text, name))
        t = [o for o in vp.overlays if isinstance(o, CoordinateTripodOverlay)]
        ovito.scene.pipelines.clear()
        return t[0]

    t0 = tripod("annotate: {colorbar: false}\n", "d.yaml")
    assert t0.font_size == pytest.approx(0.4) and not t0.outline_enabled   # unchanged default
    t1 = tripod("annotate: {colorbar: false, tripod_font_size: 0.8}\n", "f.yaml")
    assert t1.font_size == pytest.approx(0.8) and t1.outline_enabled
    t2 = tripod("annotate: {colorbar: false, tripod_font_size: 0.8, tripod_outline: false}\n",
                "g.yaml")
    assert t2.font_size == pytest.approx(0.8) and not t2.outline_enabled


# --- atoms.radius (uniform) with named types -------------------------------

def test_uniform_radius_wins_over_element_radius_of_named_types(tmp_path):
    """`radius: 0.4` + `names: {1: Ni}` rendered Ni at its element radius
    (1.24 A) before 0.4.3: naming a type sets a per-type radius, which beats
    the global vis.radius."""
    write_fcc(str(tmp_path / "fcc.data"), n=3)
    _, _, pipe, *_ = _prepare(card_file(
        tmp_path, "input: {file: fcc.data}\n"
                  "atoms: {show: all, names: {1: Ni}, radius: 0.4}\n"
                  "annotate: {colorbar: false}\n"))
    t = pipe.source.data.particles.particle_types.types[0]
    assert t.name == "Ni" and t.radius == pytest.approx(0.4)
