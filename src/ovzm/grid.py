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
"""ovzm grid: render the SAME card over N inputs with identical camera,
scale, styling, and colorbar limits, composited into one labeled figure.

Comparability rules:
- one camera for all panels (direction/projection from the card; field of
  view = the largest tight-fit over all panels, so every panel is at the
  same magnification);
- range:auto colorbars are resolved on the FIRST panel and the same limits
  are applied to every other panel;
- the tripod and the legend are drawn once (first panel) unless
  grid.tripod: all;
- each panel carries only a short title (grid.labels or the input stem);
  the full information lives in the grid's .prov.yaml (and inside the PNG).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from ovito.modifiers import ColorCodingModifier
from ovito.vis import TextLabelOverlay

from .card import load_card
from .crystal import resolve_orientation
from .grains import finalize_grains, grains_prov, resolve_grains
from .labels import dxa_summary
from .pipelinebuild import (apply_color_mode, build_pipeline,
                            check_species_names, resolve_auto_color_ranges,
                            style_atoms, style_structure_types)
from .scene import (add_grain_tripods, add_overlays, make_renderer,
                    make_viewport, resolve_output)


def _panel_stem(path: str) -> str:
    stem = Path(path).name
    for ext in (".gz", ".zst", ".bz2"):
        stem = stem[:-len(ext)] if stem.endswith(ext) else stem
    return Path(stem).stem


def _resolve_grid_inputs(card: dict) -> list[str]:
    import glob as globmod
    grid = card.get("grid") or {}
    inputs = grid.get("inputs")
    if not inputs:
        raise SystemExit("[ovzm] grid mode needs grid.inputs: [file1, file2, ...]")
    base = Path(card.get("_card_dir", "."))
    out = []
    for item in inputs:
        p = Path(item)
        if not p.is_absolute():
            p = base / p
        matches = sorted(globmod.glob(str(p)))
        if not matches:
            raise SystemExit(f"[ovzm] grid input matched nothing: {p}")
        out += matches
    return out


def run_grid(card_path: str, out_override: str | None = None, *,
             ask: bool = False):
    import ovito
    from .runner import _provenance, _resolved_scene, _embed_prov_png

    from .runner import resolve_meta
    card = load_card(card_path)
    inputs = _resolve_grid_inputs(card)
    resolve_meta(card, ask=ask,
                 search_dirs=(card.get("_card_dir"), str(Path(inputs[0]).parent)))
    grid_cfg = card.get("grid") or {}
    grains = resolve_grains(card)          # hard error on a malformed block
    labels = grid_cfg.get("labels") or [_panel_stem(f) for f in inputs]
    if len(labels) != len(inputs):
        raise SystemExit("[ovzm] grid.labels must match grid.inputs in length")

    # ---- pass 1: build all pipelines, find shared camera + color ranges
    panels = []
    shared_ranges = None
    for i, inp in enumerate(inputs):
        orientation = resolve_orientation(card, inp)
        pipe = build_pipeline(card, inp)
        if i == 0:
            check_species_names(pipe, card)
        apply_color_mode(pipe, card)
        style_atoms(pipe, None, card)
        data = pipe.compute()
        if i == 0:
            shared_ranges = resolve_auto_color_ranges(pipe, data)
            if shared_ranges:
                data = pipe.compute()
        else:
            # apply the FIRST panel's limits for comparability
            for mod in pipe.modifiers:
                if isinstance(mod, ColorCodingModifier) and shared_ranges:
                    mod.start_value = shared_ranges[0]["start"]
                    mod.end_value = shared_ranges[0]["end"]
        style_structure_types(pipe, data, card)
        full_data = pipe.source.compute()
        dxa = dxa_summary(data, orientation)
        if getattr(data, "dislocations", None) is not None:
            try:
                data.dislocations.vis.line_width = float(
                    (card.get("annotate") or {}).get("dxa_line_width", 2.0))
                data.dislocations.vis.show_burgers_vectors = False
            except Exception:
                pass
        panels.append(dict(input=inp, pipe=pipe, data=data,
                           full_data=full_data, dxa=dxa,
                           orientation=orientation, label=str(labels[i])))

    if grains is not None:  # default size / origin check against panel 1's box
        finalize_grains(grains, panels[0]["data"].cell)

    # shared camera: fit each panel, keep the widest field of view
    vp = make_viewport(card, panels[0]["orientation"])
    margin = float((card.get("view") or {}).get("fit_margin", 1.1))
    max_fov, cam_pos = None, None
    for p in panels:
        p["pipe"].add_to_scene()
        vp.zoom_all()
        if max_fov is None or vp.fov > max_fov:
            max_fov, cam_pos = vp.fov, vp.camera_pos
        p["pipe"].remove_from_scene()
    vp.fov = max_fov * margin
    vp.camera_pos = cam_pos

    # ---- pass 2: render panels with the shared camera
    w, h, renderer_name, bg, alpha = resolve_output(card)
    renderer = make_renderer(renderer_name)
    tripod_all = (grid_cfg.get("tripod") == "all")
    tmpdir = Path(tempfile.mkdtemp(prefix="ovzm-grid-"))
    panel_files = []
    for i, p in enumerate(panels):
        p["pipe"].add_to_scene()
        vp.overlays.clear()
        if i == 0 or tripod_all:
            add_overlays(vp, card, p["pipe"], p["data"], p["orientation"],
                         label_text=None)   # tripod + legend, no text block
        if grains is not None:
            # grain tripods are data annotation, not legend: EVERY panel.
            # (grid.tripod first|all governs only the corner tripod.)
            add_grain_tripods(vp, grains)
        title = TextLabelOverlay(text=p["label"])
        title.font_size = 0.035
        from .scene import _qt_alignment
        title.alignment = _qt_alignment("top_left")
        title.offset_x, title.offset_y = 0.01, -0.01
        vp.overlays.append(title)
        f = tmpdir / f"panel{i}.png"
        vp.render_image(filename=str(f), size=(w, h), renderer=renderer,
                        background=bg, alpha=alpha)
        panel_files.append(f)
        p["pipe"].remove_from_scene()

    # ---- composite
    from PIL import Image
    n = len(panel_files)
    cols = int(grid_cfg.get("cols") or 0) or (2 if n <= 4 else 3)
    cols = min(cols, n)
    rows = (n + cols - 1) // cols
    gutter = 6
    canvas = Image.new("RGBA" if alpha else "RGB",
                       (cols * w + (cols - 1) * gutter,
                        rows * h + (rows - 1) * gutter),
                       (255, 255, 255, 0) if alpha else (255, 255, 255))
    for i, f in enumerate(panel_files):
        img = Image.open(f)
        canvas.paste(img, ((i % cols) * (w + gutter), (i // cols) * (h + gutter)))

    name = card.get("name", "viz")
    tag = (card.get("output") or {}).get("tag")
    fid = f"{name}__grid" + (f"__{tag}" if tag else "")
    out_path = Path(out_override) if out_override else Path.cwd() / f"{fid}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)

    # ---- provenance: per-panel resolved scenes under one figure_id
    scenes = []
    for p in panels:
        colorbars = [dict(cb) for cb in (shared_ranges or [])]
        sc = _resolved_scene(p["pipe"], vp, card, colorbars, p["dxa"],
                             p["full_data"], p["orientation"])
        sc["panel_label"] = p["label"]
        sc["input"] = p["input"]
        scenes.append(sc)
    scene_block = {"grid": {"cols": cols, "rows": rows,
                            "panel_size": [w, h]},
                   "panels": scenes}
    if grains is not None:
        scene_block["grains"] = grains_prov(grains)
    prov = _provenance(card, inputs, out_path, scene_block)
    _embed_prov_png(out_path)
    print(f"[ovzm] wrote {out_path}  ({n} panels, {cols}x{rows})")
    print(f"[ovzm] provenance: {prov} (also embedded in the PNG)")
    return out_path
