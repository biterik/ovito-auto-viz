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
"""Guards against the class of bug that broke `color_coding` on every OVITO
version (0.4.1): ovzm-private state attached to OVITO objects.

OVITO's Python objects are pybind11 wrappers without a __dict__, so
`mod._anything = x` raises AttributeError (verified 3.12 .. 3.16). ovzm keeps
such facts in `pipelinebuild._OBJECT_META` instead.

Part 1 is a static source lint that runs everywhere (no ovito needed).
Part 2 exercises the real color_coding path and the overlay text rendering
against the installed ovito module (skipped when it is absent).
"""
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "ovzm"

# `<expr>._name = ...` where <expr> is not `self`/`cls`/a module-level global.
_PRIVATE_ASSIGN = re.compile(r"^\s*(?!self\b)(?!cls\b)[A-Za-z_][\w\.\[\]\"']*\._\w+\s*=[^=]",
                             re.M)


def test_no_private_attributes_set_on_foreign_objects():
    offenders = []
    for py in sorted(SRC.glob("*.py")):
        for m in _PRIVATE_ASSIGN.finditer(py.read_text()):
            line = m.group(0).strip()
            # module-level globals of our own (e.g. `_QAPP = ...`) never have
            # a dot before the underscore; anything that does is suspect.
            offenders.append(f"{py.name}: {line}")
    assert not offenders, (
        "ovzm must not attach private attributes to OVITO objects "
        "(pybind11 objects have no __dict__); use pipelinebuild.set_meta():\n  "
        + "\n  ".join(offenders))


# --------------------------------------------------------------------------
ovito = pytest.importorskip("ovito", reason="compat tests need the ovito module")


def _tiny_pipeline(tmp_path):
    """A 4x4x4 fcc block written as a LAMMPS data file, imported by ovito."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from make_fcc import main as write_fcc  # noqa: E402
    data = tmp_path / "fcc.data"
    write_fcc(str(data), n=4)
    from ovito.io import import_file
    return import_file(str(data))


def test_color_coding_builds_and_resolves_auto_range(tmp_path):
    from ovito.modifiers import ColorCodingModifier
    from ovzm.pipelinebuild import (build_modifier, get_meta,
                                    resolve_auto_color_ranges)
    (mod,) = build_modifier({"color_coding": {"property": "Position.X",
                                              "map": "magma"}})
    assert isinstance(mod, ColorCodingModifier)
    assert get_meta(mod, "auto_range") is True
    assert get_meta(mod, "map") == "magma"
    assert type(mod.gradient).__name__ == "Magma"

    pipe = _tiny_pipeline(tmp_path)
    pipe.modifiers.append(mod)
    data = pipe.compute()
    resolved = resolve_auto_color_ranges(pipe, data)
    assert len(resolved) == 1
    r = resolved[0]
    assert r["map"] == "magma"
    assert r["start"] < r["end"]
    assert abs(r["start"] - float(mod.start_value)) < 1e-9
    assert abs(r["end"] - float(mod.end_value)) < 1e-9

    (fixed,) = build_modifier({"color_coding": {"property": "Position.X",
                                                "range": [1.0, 2.0]}})
    assert get_meta(fixed, "auto_range") is False
    assert (fixed.start_value, fixed.end_value) == (1.0, 2.0)


def test_unknown_color_map_fails_loudly():
    from ovzm.pipelinebuild import build_modifier
    with pytest.raises(SystemExit):
        build_modifier({"color_coding": {"property": "Position.X",
                                         "map": "plasma"}})  # not in OVITO


def test_overlay_text_is_not_clipped(tmp_path):
    """ovito >= 3.16 clips ALL overlay text when an overlay is constructed
    before a QGuiApplication exists (empty default font family). Render a
    long label and its short prefix with identical settings: the long one
    must be much wider. (An absolute width would depend on the version's
    font metrics -- 3.16 draws the same font_size ~30 % smaller than 3.15.)"""
    import numpy as np
    from PIL import Image
    from ovito.vis import TachyonRenderer, TextLabelOverlay, Viewport
    from ovzm.scene import ensure_gui_app

    ensure_gui_app()
    pipe = _tiny_pipeline(tmp_path)
    pipe.add_to_scene()
    long = ("b = 1/2[-110] (perfect), xi = [-1-12], 90 deg edge, "
            "L = 17 A (PBC-infinite)")
    widths = {}
    try:
        for key, text in (("short", long[:12]), ("long", long)):
            vp = Viewport(type=Viewport.Type.Ortho, camera_dir=(0, 1, 0))
            vp.zoom_all()
            vp.fov *= 6            # push the atoms far from the label
            lab = TextLabelOverlay(text=text, font_size=0.08)
            lab.offset_y = -0.02
            vp.overlays.append(lab)
            out = tmp_path / f"{key}.png"
            vp.render_image(filename=str(out), size=(1200, 200),
                            renderer=TachyonRenderer(shadows=False,
                                                     antialiasing=False),
                            background=(1, 1, 1))
            band = np.asarray(Image.open(out).convert("L"))[:60]
            cols = np.where((band < 128).any(axis=0))[0]
            assert cols.size, f"no text rendered for {key!r}"
            widths[key] = int(cols.max() - cols.min())
    finally:
        pipe.remove_from_scene()
    assert widths["long"] > 3 * widths["short"], (
        f"long label appears clipped: {widths}")
