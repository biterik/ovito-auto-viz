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
"""Build an OVITO pipeline from the `pipeline:` section of a viz card."""
from __future__ import annotations

import numpy as np
from ovito.io import import_file
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

LATTICES = {
    "fcc": DislocationAnalysisModifier.Lattice.FCC,
    "bcc": DislocationAnalysisModifier.Lattice.BCC,
    "hcp": DislocationAnalysisModifier.Lattice.HCP,
    "diamond": DislocationAnalysisModifier.Lattice.CubicDiamond,
}

STRUCTURE_IDS = {  # PTM/CNA StructureType integer ids share this layout
    "other": 0, "fcc": 1, "hcp": 2, "bcc": 3, "ico": 4,
}

COLORMAPS = {
    "viridis": "Viridis", "magma": "Magma", "plasma": "Plasma",
    "hot": "Hot", "jet": "Jet", "grayscale": "Grayscale",
    "rainbow": "Rainbow", "blue-white-red": "BlueWhiteRed",
}


def _color_coding(spec: dict) -> ColorCodingModifier:
    kwargs = {"property": spec["property"]}
    rng = spec.get("range")
    auto_range = not rng or rng == "auto"
    if not auto_range:
        kwargs["start_value"], kwargs["end_value"] = float(rng[0]), float(rng[1])
    mod = ColorCodingModifier(**kwargs)
    mod._ovzm_auto_range = auto_range   # resolved against the data in the runner
    mod._ovzm_map = spec.get("map", "viridis")
    cmap = spec.get("map", "viridis")
    try:
        mod.gradient = getattr(ColorCodingModifier, COLORMAPS.get(cmap, cmap))()
    except AttributeError:
        pass  # keep default gradient
    return mod


def resolve_auto_color_ranges(pipe, data):
    """Set start/end of range:auto ColorCodingModifiers from the (filtered)
    data actually shown, so the colorbar spans what is visible."""
    import numpy as np
    resolved = []
    for mod in pipe.modifiers:
        if not isinstance(mod, ColorCodingModifier):
            continue
        if getattr(mod, "_ovzm_auto_range", False):
            prop = str(mod.property)
            name = prop.split("/")[-1]
            comp = None
            if name not in data.particles and "." in name:
                name, comp = name.rsplit(".", 1)
            if name in data.particles:
                arr = np.asarray(data.particles[name])
                if comp is not None and arr.ndim > 1:
                    prop_obj = data.particles[name]
                    idx = (list(prop_obj.component_names).index(comp)
                           if comp in getattr(prop_obj, "component_names", []) else 0)
                    arr = arr[:, idx]
                mod.start_value = float(np.min(arr))
                mod.end_value = float(np.max(arr))
        resolved.append({
            "property": str(mod.property),
            "start": float(mod.start_value),
            "end": float(mod.end_value),
            "map": getattr(mod, "_ovzm_map", "default"),
        })
    return resolved


def build_modifier(step: dict):
    """One card pipeline entry ({name: {params}} or bare name) -> list of modifiers."""
    if isinstance(step, str):
        name, p = step, {}
    else:
        (name, p), = step.items()
        p = p or {}

    if name == "ptm":
        m = PolyhedralTemplateMatchingModifier(
            rmsd_cutoff=float(p.get("rmsd_cutoff", 0.1)))
        m.output_orientation = bool(p.get("orientations", False))
        return [m]
    if name == "cna":
        m = CommonNeighborAnalysisModifier()
        if "cutoff" in p:
            m.mode = CommonNeighborAnalysisModifier.Mode.FixedCutoff
            m.cutoff = float(p["cutoff"])
        return [m]
    if name == "dxa":
        m = DislocationAnalysisModifier(
            input_crystal_structure=LATTICES[p.get("lattice", "fcc")])
        if "circuit_length" in p:
            m.trial_circuit_length = int(p["circuit_length"])
        m.only_perfect_dislocations = bool(p.get("only_perfect", False))
        if p.get("line_smoothing") is not None:
            m.line_smoothing_level = int(p["line_smoothing"])
        return [m]
    if name == "grain_segmentation":
        m = GrainSegmentationModifier()
        if "merge_threshold" in p:
            m.merging_threshold = float(p["merge_threshold"])
        return [m]
    if name == "color_coding":
        return [_color_coding(p)]
    if name == "slice":
        m = SliceModifier(normal=tuple(p.get("normal", (0, 0, 1))),
                          distance=float(p.get("distance", 0)))
        if "width" in p:
            m.slab_width = float(p["width"])
        m.inverse = bool(p.get("inverse", False))
        return [m]
    if name == "wrap":
        return [WrapPeriodicImagesModifier()]
    if name == "select_type":
        return [SelectTypeModifier(property=p.get("property", "Particle Type"),
                                   types=set(p["types"]))]
    if name == "select_expression":
        return [ExpressionSelectionModifier(expression=p["expr"])]
    if name == "delete_selected":
        return [DeleteSelectedModifier()]
    raise ValueError(f"unknown pipeline entry '{name}'")


def _atoms_show_filter(show: str):
    """atoms.show shortcuts -> modifiers appended AFTER analysis steps."""
    if show in (None, "all"):
        return []
    if show == "non_fcc":
        expr = "StructureType != 1"
    elif show == "non_bcc":
        expr = "StructureType != 3"
    elif show == "defects_only":  # anything not matching the majority lattice
        expr = "StructureType == 0"
    else:
        expr = show  # raw boolean expression, atoms where expr is TRUE are kept
    # select the complement (kept-expression == 0) and delete it
    return [ExpressionSelectionModifier(expression=f"({expr}) == 0"),
            DeleteSelectedModifier()]


def build_pipeline(card: dict, input_path: str):
    pipe = import_file(input_path)
    for step in card.get("pipeline", []) or []:
        for mod in build_modifier(step):
            pipe.modifiers.append(mod)
    atoms = card.get("atoms", {}) or {}
    for mod in _atoms_show_filter(atoms.get("show")):
        pipe.modifiers.append(mod)
    return pipe


def _remove_color_property(frame, data):
    """User modifier: drop the Color property written by PTM/CNA so particles
    fall back to their per-type colors."""
    if "Color" in data.particles:
        del data.particles_["Color"]


def apply_color_mode(pipe, card: dict):
    """atoms.color_by: 'structure' (PTM/CNA colors, default) or 'type'."""
    atoms = card.get("atoms", {}) or {}
    mode = atoms.get("color_by")
    if mode is None:
        mode = "type" if atoms.get("colors") else "structure"
    if mode == "type":
        pipe.modifiers.append(_remove_color_property)


GRAY = (0.45, 0.45, 0.45)


def check_species_names(pipe, card: dict):
    """Multi-type inputs MUST have a species mapping — dump files carry no
    element names, and unlabeled 'type 1/type 2' figures are ambiguous.
    Raise a clear, actionable error (the CLI --ask flag or the driving agent
    resolves it interactively)."""
    src = pipe.source.data
    if src is None or src.particles is None:
        return
    tprop = src.particles.particle_types
    if tprop is None:
        return
    types = list(tprop.types)
    if len(types) < 2:
        return
    names = (card.get("atoms", {}) or {}).get("names") or {}
    missing = [t.id for t in types
               if str(t.id) not in {str(k) for k in names} and not t.name]
    if missing:
        raise SystemExit(
            "[ovzm] this file has {} atom types but no species mapping for "
            "type(s) {}.\nDump files do not carry element names — add to the "
            "card:\n\n  atoms:\n    names: {{{}}}\n\nor rerun with --ask to "
            "be prompted.".format(
                len(types), missing,
                ", ".join(f"{i}: <element>" for i in missing)))


def style_structure_types(pipe, data):
    """Make the 'Other' structure type visible on white backgrounds."""
    parts = getattr(data, "particles", None)
    if parts is None or "Structure Type" not in parts:
        return
    src = pipe.source.data
    # structure types live on the modifier output, not the source; recolor at
    # render time is handled by OVITO reusing the modifier's type colors, so
    # adjust them on the PTM/CNA modifier itself.
    from ovito.modifiers import (CommonNeighborAnalysisModifier,
                                 PolyhedralTemplateMatchingModifier)
    for mod in pipe.modifiers:
        if isinstance(mod, (PolyhedralTemplateMatchingModifier,
                            CommonNeighborAnalysisModifier)):
            for st in mod.structures:
                if st.id == 0:  # OTHER
                    st.color = GRAY


def style_atoms(pipe, data, card: dict):
    """Apply radius/color styling at the pipeline SOURCE, so it takes effect
    for rendering (styling a computed snapshot would be render-inert)."""
    atoms = card.get("atoms", {}) or {}
    radius = atoms.get("radius")
    colors = atoms.get("colors") or {}
    names = atoms.get("names") or {}
    src = pipe.source.data
    if src is None or src.particles is None:
        return
    if isinstance(radius, (int, float)):
        src.particles_.vis.radius = float(radius)
    tprop = src.particles.particle_types
    if tprop is None or (not isinstance(radius, dict) and not colors and not names):
        return
    tprop_m = src.particles_.particle_types_
    for t in list(tprop_m.types):
        tm = tprop_m.make_mutable(t)
        # name FIRST: naming a type (e.g. 'Ni') resets its color/radius to the
        # element defaults, which would clobber card-specified values.
        for key, n in names.items():
            if str(key) == str(t.id):
                tm.name = str(n)
        if isinstance(radius, dict):
            for key, r in radius.items():
                if str(key) == str(t.id) or key == t.name:
                    tm.radius = float(r)
        for key, c in colors.items():
            if str(key) == str(t.id) or key == t.name:
                tm.color = tuple(float(x) for x in c)
