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
"""Viewport/camera setup, overlays, renderers, output presets."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from ovito.vis import (
    ColorLegendOverlay,
    CoordinateTripodOverlay,
    OpenGLRenderer,
    TachyonRenderer,
    TextLabelOverlay,
    Viewport,
)

try:
    from ovito.vis import OSPRayRenderer
except ImportError:
    OSPRayRenderer = None

from ovito.modifiers import ColorCodingModifier

from .crystal import Orientation

# ---------------------------------------------------------------------------
# named views: camera DIRECTION in the sim frame (looking along this vector)

NAMED_VIEWS = {
    "top":    ((0, 0, -1), (0, 1, 0)),
    "bottom": ((0, 0, 1), (0, 1, 0)),
    "front":  ((0, 1, 0), (0, 0, 1)),
    "back":   ((0, -1, 0), (0, 0, 1)),
    "left":   ((1, 0, 0), (0, 0, 1)),
    "right":  ((-1, 0, 0), (0, 0, 1)),
}

OUTPUT_PRESETS = {
    # name: (width, height, renderer)
    "draft": (1280, 720, "tachyon-fast"),
    "slide": (1920, 1080, "tachyon"),
    "paper": (3200, 2400, "tachyon-ao"),
}


def make_renderer(name: str):
    if name in ("opengl", "gl"):
        return OpenGLRenderer()
    if name == "tachyon-fast":
        return TachyonRenderer(shadows=False, ambient_occlusion=False,
                               antialiasing=True)
    if name == "tachyon":
        return TachyonRenderer(shadows=True, ambient_occlusion=False,
                               antialiasing=True)
    if name == "tachyon-ao":
        return TachyonRenderer(shadows=True, ambient_occlusion=True,
                               antialiasing=True)
    if name == "ospray":
        if OSPRayRenderer is None:
            raise RuntimeError("OSPRay renderer not available in this ovito build")
        return OSPRayRenderer()
    raise ValueError(f"unknown renderer '{name}'")


def resolve_view(card: dict, orientation: Orientation | None):
    view = card.get("view", {}) or {}
    direction = view.get("direction", "front")
    up = view.get("up")
    if isinstance(direction, str):
        if direction not in NAMED_VIEWS:
            raise ValueError(f"unknown named view '{direction}'; "
                             f"use one of {sorted(NAMED_VIEWS)} or a Miller triplet")
        cam_dir, default_up = NAMED_VIEWS[direction]
        cam_dir = np.asarray(cam_dir, dtype=float)
        up_vec = np.asarray(up, dtype=float) if up else np.asarray(default_up, float)
    else:
        # Miller direction in the CRYSTAL frame: camera looks along -d (i.e. at
        # the structure from the +d side), which is the intuitive reading of
        # "view from [111]".
        if orientation is None:
            raise ValueError("Miller view direction requires crystal orientation "
                             "(crystal.x/y/z or an auto-parsable filename)")
        d = orientation.crystal_to_sim(direction)
        cam_dir = -d / np.linalg.norm(d)
        if up is not None and not isinstance(up, str):
            up_vec = orientation.crystal_to_sim(up)
        else:
            up_vec = np.asarray((0, 0, 1), dtype=float)
            if abs(np.dot(up_vec, cam_dir)) > 0.95:
                up_vec = np.asarray((0, 1, 0), dtype=float)
    projection = view.get("projection", "ortho")
    return cam_dir, up_vec, projection


def make_viewport(card: dict, orientation: Orientation | None) -> Viewport:
    cam_dir, up_vec, projection = resolve_view(card, orientation)
    vp = Viewport()
    vp.type = (Viewport.Type.Ortho if projection == "ortho"
               else Viewport.Type.Perspective)
    vp.camera_dir = tuple(cam_dir)
    # camera_up is set implicitly by OVITO from camera_dir; for exact up-vector
    # control we rely on the default heuristic unless it degenerates.
    return vp


# ---------------------------------------------------------------------------
# overlays


def add_overlays(vp: Viewport, card: dict, pipe, data, orientation, label_text):
    ann = card.get("annotate", {}) or {}

    # --- coordinate tripod with Miller labels
    tripod_cfg = ann.get("tripod", "miller")
    if tripod_cfg and tripod_cfg != "off":
        tripod = CoordinateTripodOverlay()
        tripod.size = float(ann.get("tripod_size", 0.08))
        tripod.alignment = _qt_alignment(ann.get("tripod_corner", "bottom_left"))
        tripod.style = CoordinateTripodOverlay.Style.Solid
        tripod.offset_x = 0.06   # keep Miller labels inside the frame
        tripod.offset_y = 0.05
        if tripod_cfg == "miller" and orientation is not None:
            lx, ly, lz = orientation.axis_labels()
            tripod.axis1_label = f"x={lx}"
            tripod.axis2_label = f"y={ly}"
            tripod.axis3_label = f"z={lz}"
        vp.overlays.append(tripod)

    # --- colorbar: ALWAYS present when atoms carry color information.
    # (a) continuous colorbar for any ColorCodingModifier in the pipeline
    have_continuous = False
    if ann.get("colorbar", True):
        for mod in pipe.modifiers:
            if isinstance(mod, ColorCodingModifier):
                leg = ColorLegendOverlay(modifier=mod)
                cb = ann.get("colorbar") if isinstance(ann.get("colorbar"), dict) else {}
                title = cb.get("title", str(mod.property).split("/")[-1])
                units = cb.get("units")
                leg.title = f"{title} [{units}]" if units else title
                leg.alignment = _qt_alignment(cb.get("corner", "top_right"))
                leg.font_size = float(cb.get("font_size", 0.05))
                leg.format_string = cb.get("format", "%g")
                leg.offset_y = -0.06 if cb.get("corner", "top_right").startswith("top") else 0.02
                leg.offset_x = -0.01
                vp.overlays.append(leg)
                have_continuous = True
                break
    # (b) discrete per-type legend when atoms are colored by type
    if ann.get("colorbar", True) and not have_continuous:
        atoms = card.get("atoms", {}) or {}
        mode = atoms.get("color_by") or ("type" if atoms.get("colors") else "structure")
        source_prop = ("particles/Particle Type" if mode == "type"
                       else "particles/Structure Type")
        try:
            leg = ColorLegendOverlay(property=source_prop)
            cb = ann.get("colorbar") if isinstance(ann.get("colorbar"), dict) else {}
            corner = cb.get("corner", "top_right")
            leg.alignment = _qt_alignment(corner)
            leg.font_size = float(cb.get("font_size", 0.045))
            leg.offset_y = -0.06 if corner.startswith("top") else 0.02
            leg.offset_x = -0.01
            vp.overlays.append(leg)
        except Exception as exc:
            import sys
            print(f"[ovzm] note: discrete type legend unavailable ({exc})",
                  file=sys.stderr)

    # --- auto label block (one TextLabelOverlay per line: multi-line text is
    # not reliably rendered by a single overlay)
    if label_text and ann.get("labels", "auto") != "off":
        corner = ann.get("labels_corner", "top_left")
        fs = float(ann.get("labels_font_size", 0.019))
        color = tuple(ann.get("labels_color", (0, 0, 0)))
        lines = label_text.split("\n")
        step = fs * 1.3
        top = corner.startswith("top")
        for i, line in enumerate(lines):
            lab = TextLabelOverlay(text=line)
            lab.alignment = _qt_alignment(corner)
            lab.font_size = fs
            lab.text_color = color
            lab.offset_x = 0.01 if corner.endswith("left") else -0.01
            lab.offset_y = (-(0.012 + i * step)) if top else (0.012 + (len(lines) - 1 - i) * step)
            vp.overlays.append(lab)


def _qt_alignment(corner: str):
    from ovito.qt_compat import QtCore
    m = {
        "top_left": QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft,
        "top_right": QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignRight,
        "bottom_left": QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignLeft,
        "bottom_right": QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignRight,
    }
    return m[corner]


def resolve_output(card: dict):
    out = card.get("output", {}) or {}
    preset = out.get("preset", "slide")
    if preset not in OUTPUT_PRESETS:
        raise ValueError(f"unknown output preset '{preset}'; "
                         f"use one of {sorted(OUTPUT_PRESETS)}")
    w, h, renderer = OUTPUT_PRESETS[preset]
    w = int(out.get("width", w))
    h = int(out.get("height", h))
    renderer = out.get("renderer", renderer)
    background = out.get("background", "white")
    bg = {"white": (1, 1, 1), "black": (0, 0, 0),
          "transparent": (1, 1, 1)}.get(background, background)
    alpha = background == "transparent"
    return w, h, renderer, tuple(bg), alpha
