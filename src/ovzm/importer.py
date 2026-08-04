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
"""ovzm import: best-effort .ovito session state -> viz-card YAML.

Every modifier the schema knows maps to its card key; anything unmappable is
listed in a `warnings:` block at the top of the emitted YAML instead of being
silently dropped.
"""
from __future__ import annotations

import sys

import yaml

import ovito
from ovito.modifiers import (
    CommonNeighborAnalysisModifier,
    ColorCodingModifier,
    DeleteSelectedModifier,
    DislocationAnalysisModifier,
    ExpressionSelectionModifier,
    GrainSegmentationModifier,
    PolyhedralTemplateMatchingModifier,
    SelectTypeModifier,
    SliceModifier,
    WrapPeriodicImagesModifier,
)

_LATTICE_NAMES = {}


def _lattice_name(val):
    from ovito.modifiers import DislocationAnalysisModifier as D
    for name, member in (("fcc", D.Lattice.FCC), ("bcc", D.Lattice.BCC),
                         ("hcp", D.Lattice.HCP),
                         ("diamond", D.Lattice.CubicDiamond)):
        if val == member:
            return name
    return str(val)


def modifier_to_card(mod):
    """Return (card_entry | None, warning | None)."""
    if isinstance(mod, PolyhedralTemplateMatchingModifier):
        return {"ptm": {"rmsd_cutoff": round(float(mod.rmsd_cutoff), 6)}}, None
    if isinstance(mod, CommonNeighborAnalysisModifier):
        p = {}
        if mod.mode == CommonNeighborAnalysisModifier.Mode.FixedCutoff:
            p["cutoff"] = float(mod.cutoff)
        return {"cna": p}, None
    if isinstance(mod, DislocationAnalysisModifier):
        return {"dxa": {
            "lattice": _lattice_name(mod.input_crystal_structure),
            "circuit_length": int(mod.trial_circuit_length),
        }}, None
    if isinstance(mod, GrainSegmentationModifier):
        return {"grain_segmentation": {
            "merge_threshold": float(mod.merging_threshold)}}, None
    if isinstance(mod, ColorCodingModifier):
        return {"color_coding": {
            "property": str(mod.property),
            "range": [float(mod.start_value), float(mod.end_value)],
        }}, None
    if isinstance(mod, SliceModifier):
        return {"slice": {"normal": [float(x) for x in mod.normal],
                          "distance": float(mod.distance),
                          "width": float(mod.slab_width),
                          "inverse": bool(mod.inverse)}}, None
    if isinstance(mod, WrapPeriodicImagesModifier):
        return "wrap", None
    if isinstance(mod, SelectTypeModifier):
        return {"select_type": {"property": str(mod.property),
                                "types": sorted(mod.types)}}, None
    if isinstance(mod, ExpressionSelectionModifier):
        return {"select_expression": {"expr": str(mod.expression)}}, None
    if isinstance(mod, DeleteSelectedModifier):
        return "delete_selected", None
    return None, f"unmapped modifier: {type(mod).__name__} — configure it manually"


def import_session(ovito_path: str) -> str:
    ovito.scene.load(ovito_path)
    warnings = []
    card = {"name": "imported"}
    pipes = list(ovito.scene.pipelines)
    if not pipes:
        raise RuntimeError("session contains no pipelines")
    if len(pipes) > 1:
        warnings.append(f"session has {len(pipes)} pipelines; importing the first")
    pipe = pipes[0]

    # input file
    try:
        src = pipe.source
        files = getattr(src, "source_path", None)
        if files:
            card["input"] = {"file": str(files)}
    except Exception:
        warnings.append("could not determine the input file")

    # modifiers
    steps = []
    for mod in pipe.modifiers:
        entry, warn = modifier_to_card(mod)
        if entry is not None:
            steps.append(entry)
        if warn:
            warnings.append(warn)
    if steps:
        card["pipeline"] = steps

    # camera
    try:
        vp = ovito.scene.viewports.active_vp
        card["view"] = {
            "projection": "ortho" if vp.type == type(vp).Type.Ortho else "perspective",
            "direction_sim_frame": [round(float(x), 4) for x in vp.camera_dir],
        }
        warnings.append("view.direction_sim_frame is the raw sim-frame camera; "
                        "replace with a named view or Miller direction + crystal block")
    except Exception:
        warnings.append("could not read the viewport camera")

    doc = {}
    if warnings:
        doc["warnings"] = warnings
    doc.update(card)
    from . import YAML_CREDIT_HEADER
    return (YAML_CREDIT_HEADER
            + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
