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
"""ovzm run modes: render an image/movie, or save a ready-to-open .ovito session."""
from __future__ import annotations

import glob
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

import ovito

from .card import load_card
from .crystal import resolve_orientation
from .labels import build_label_text, dxa_summary
from .pipelinebuild import (apply_color_mode, build_pipeline,
                            check_species_names, resolve_auto_color_ranges,
                            style_atoms, style_structure_types)
from .scene import add_overlays, make_renderer, make_viewport, resolve_output


def _resolve_input(card: dict) -> str:
    inp = (card.get("input") or {}).get("file")
    if not inp:
        raise ValueError("card has no input.file")
    base = Path(card.get("_card_dir", "."))
    p = Path(inp)
    if not p.is_absolute():
        p = base / p
    matches = sorted(glob.glob(str(p)))
    if not matches:
        raise FileNotFoundError(f"input.file matched nothing: {p}")
    if len(matches) > 1:
        print(f"[ovzm] input glob matched {len(matches)} files; using them as frames",
              file=sys.stderr)
        return matches  # multi-file trajectory
    return matches[0]


def _figure_id(card: dict, input_path) -> str:
    """Naming convention: <input-stem>__<card-name>[__<tag>].

    The card name is the figure's identity (view + analysis choices); the
    optional output.tag distinguishes variants of the same card. Image and
    .prov.yaml share this ID exactly.
    """
    stem = Path(input_path if isinstance(input_path, str) else input_path[0]).name
    for ext in (".gz", ".zst", ".bz2"):
        stem = stem[:-len(ext)] if stem.endswith(ext) else stem
    stem = Path(stem).stem
    fid = f"{stem}__{card.get('name', 'viz')}"
    tag = (card.get("output") or {}).get("tag")
    return f"{fid}__{tag}" if tag else fid


def _auto_outname(card: dict, input_path: str, suffix: str) -> Path:
    out = (card.get("output") or {}).get("file", "auto")
    if out != "auto":
        p = Path(out)
        base = Path(card.get("_card_dir", "."))
        return p if p.is_absolute() else base / p
    return Path.cwd() / f"{_figure_id(card, input_path)}{suffix}"


def _resolved_scene(pipe, vp, card, colorbars, dxa, full_data, orientation):
    """The fully RESOLVED scene for the .prov.yaml — everything needed to
    interpret the image without the image carrying it: species mapping with
    actual colors/radii, colorbar limits+units, camera, analysis results."""
    scene: dict = {}
    src = pipe.source.data
    if src is not None and src.particles is not None and src.particles.particle_types is not None:
        types = []
        for t in src.particles.particle_types.types:
            types.append({
                "id": int(t.id),
                "name": t.name or None,
                "color_rgb": [round(float(c), 4) for c in t.color],
                "radius_A": round(float(t.radius), 4) if t.radius else None,
            })
        scene["particle_types"] = types
    if colorbars:
        cb_card = ((card.get("annotate") or {}).get("colorbar")
                   if isinstance((card.get("annotate") or {}).get("colorbar"), dict)
                   else {})
        for cb in colorbars:
            cb["units"] = cb_card.get("units")
            cb["title"] = cb_card.get("title", cb["property"].split("/")[-1])
        scene["colorbars"] = colorbars
    scene["camera"] = {
        "direction_sim_frame": [round(float(x), 6) for x in vp.camera_dir],
        "projection": "ortho" if vp.type == type(vp).Type.Ortho else "perspective",
        "fov": float(vp.fov),
    }
    if orientation is not None:
        lx, ly, lz = orientation.axis_labels()
        scene["crystal_axes"] = {"x": lx, "y": ly, "z": lz}
    from .labels import composition_summary
    comp = composition_summary(full_data) if full_data is not None else {}
    if comp:
        scene["composition"] = comp
    if dxa and dxa.get("n_segments"):
        scene["dxa"] = {
            "n_segments": dxa["n_segments"],
            "total_length_A": round(dxa["total_length"], 1),
            "families": {k: {"count": v[0], "length_A": round(v[1], 1)}
                         for k, v in dxa["families"].items()},
            "net": dxa.get("net"),
            "lattice_constant_estimate_A": dxa.get("a_estimate"),
            "segments": [
                {k: v for k, v in s.items()}
                for s in dxa["segments"]
            ],
        }
    return scene


def _provenance(card: dict, input_path, out_path: Path, scene: dict | None = None):
    files = input_path if isinstance(input_path, list) else [input_path]
    finfo = []
    for f in files:
        p = Path(f)
        h = hashlib.sha256()
        if p.stat().st_size <= 500 * 1024 * 1024:
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            digest = h.hexdigest()
        else:
            digest = f"size:{p.stat().st_size}"  # too big to hash routinely
        finfo.append({"path": str(p), "sha256": digest})
    from . import TOOL_CREDIT, YAML_CREDIT_HEADER, __version__
    meta = card.get("meta") or {}
    prov = {
        "figure_id": out_path.stem if out_path.suffix != ".yaml" else out_path.name,
        "creator": meta.get("creator"),
        "affiliation": meta.get("affiliation") or None,
        "project": meta.get("project") or None,
        "funding": meta.get("funding") or None,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": f"ovito-auto-viz (ovzm) {__version__}",
        "tool_credit": TOOL_CREDIT,
        "ovito_version": ovito.version_string,
        "inputs": finfo,
        "resolved_card": {
            k: (({kk: vv for kk, vv in v.items() if not kk.startswith("_")})
                if isinstance(v, dict) else v)
            for k, v in card.items() if not k.startswith("_")
        },
    }
    if scene:
        prov["resolved_scene"] = scene
    side = out_path.with_suffix(out_path.suffix + ".prov.yaml")
    side.write_text(YAML_CREDIT_HEADER
                    + yaml.safe_dump(prov, sort_keys=False, allow_unicode=True))
    return side


PROJECT_FILE = "ovzm-project.yaml"
META_KEYS = ("creator", "project", "funding", "affiliation", "email", "orcid")


def _identity_defaults() -> dict:
    """PERSONAL defaults (who am I): $OVZM_IDENTITY or
    ~/.config/ovzm/identity.yaml. Typically just:
        creator: Jane Doe
    Project-scoped facts (project, funding, affiliation) belong in the
    project file, not here — people work on multiple projects."""
    import os
    path = os.environ.get("OVZM_IDENTITY") or str(
        Path.home() / ".config" / "ovzm" / "identity.yaml")
    p = Path(path)
    if p.is_file():
        try:
            return yaml.safe_load(p.read_text()) or {}
        except Exception:
            pass
    return {}


def _find_project_file(search_dirs):
    """Walk UP from each start dir (card dir first, then the input data's
    dir) looking for ovzm-project.yaml — git-config style. First hit wins,
    so a thread/ subdir file overrides the project root's."""
    seen = set()
    for start in search_dirs:
        if not start:
            continue
        d = Path(start).resolve()
        while True:
            if str(d) in seen:
                break
            seen.add(str(d))
            cand = d / PROJECT_FILE
            if cand.is_file():
                return cand
            if d.parent == d:
                break
            d = d.parent
    return None


def resolve_meta(card: dict, *, ask: bool = False, search_dirs=()):
    """Fill meta.* hierarchically, per key:

        card meta:  >  ovzm-project.yaml (walk-up)  >  ~/.config/ovzm/identity.yaml

    A project file may also carry a `people:` map (creator name ->
    {affiliation, email, orcid, funding}) so multi-user projects can give
    each person their own affiliation. The CREATOR is mandatory — a figure
    without an author is not archivable; project/funding/affiliation may
    stay empty."""
    meta = dict(card.get("meta") or {})
    sources = {k: "card" for k in meta if meta.get(k)}
    proj_path = _find_project_file(search_dirs)
    proj = {}
    if proj_path is not None:
        try:
            proj = yaml.safe_load(proj_path.read_text()) or {}
        except Exception as exc:
            print(f"[ovzm] warning: could not read {proj_path}: {exc}",
                  file=sys.stderr)
    ident = _identity_defaults()
    for key in META_KEYS:
        if not meta.get(key):
            if proj.get(key):
                meta[key] = proj[key]
                sources[key] = str(proj_path)
            elif ident.get(key):
                meta[key] = ident[key]
                sources[key] = "user identity file"
    if not meta.get("creator") and ask:
        ans = input("[ovzm] who is creating this figure (name)? ").strip()
        if ans:
            meta["creator"] = ans
            sources["creator"] = "interactive"
    # per-person enrichment from the project file's people: map
    people = proj.get("people") or {}
    person = people.get(str(meta.get("creator", "")))
    if isinstance(person, dict):
        for key, val in person.items():
            if key in META_KEYS and not meta.get(key):
                meta[key] = val
                sources[key] = f"{proj_path} (people: {meta['creator']})"
    if not meta.get("creator"):
        raise SystemExit(
            "[ovzm] no creator given — every figure needs an author.\n"
            "Provide it via ONE of:\n"
            "  1. the card:            meta: {creator: Your Name}\n"
            f"  2. a project file:      {PROJECT_FILE} in the project root\n"
            "     (found by walking up from the card / the input data)\n"
            "  3. a personal file:     ~/.config/ovzm/identity.yaml or $OVZM_IDENTITY\n"
            "  4. interactively:       rerun with --ask\n"
            "project / funding / affiliation may stay empty; the creator may not.")
    meta["_sources"] = sources
    card["meta"] = meta


def _ask_species(pipe, card):
    """--ask: prompt interactively for missing species names."""
    src = pipe.source.data
    if src is None or src.particles is None or src.particles.particle_types is None:
        return
    types = list(src.particles.particle_types.types)
    if len(types) < 2:
        return
    names = dict((card.setdefault("atoms", {}) or {}).get("names") or {})
    for t in types:
        if str(t.id) not in {str(k) for k in names} and not t.name:
            ans = input(f"[ovzm] species name for atom type {t.id}? ").strip()
            if ans:
                names[str(t.id)] = ans
    card["atoms"]["names"] = names


def _embed_prov_png(out_path: Path):
    """Embed the .prov.yaml sidecar INTO the PNG as a compressed tEXt chunk
    (key 'ovzm_prov'), so image and provenance cannot be separated.
    Read back with `ovzm prov <image.png>`. Lossless re-save."""
    out_path = Path(out_path)
    if out_path.suffix.lower() != ".png":
        return
    side = out_path.with_suffix(out_path.suffix + ".prov.yaml")
    if not side.exists():
        return
    try:
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo
        img = Image.open(out_path)
        meta = PngInfo()
        meta.add_text("ovzm_prov", side.read_text(), zip=True)
        img.save(out_path, pnginfo=meta)
    except Exception as exc:
        print(f"[ovzm] note: could not embed provenance in PNG: {exc}",
              file=sys.stderr)


def read_embedded_prov(image_path: str) -> str | None:
    from PIL import Image
    img = Image.open(image_path)
    return img.text.get("ovzm_prov") if hasattr(img, "text") else None


def _prepare(card_path: str, *, ask: bool = False):
    card = load_card(card_path)
    input_path = _resolve_input(card)
    first = input_path[0] if isinstance(input_path, list) else input_path
    resolve_meta(card, ask=ask,
                 search_dirs=(card.get("_card_dir"), str(Path(first).parent)))
    orientation = resolve_orientation(card, first)
    pipe = build_pipeline(card, input_path)
    if ask:
        _ask_species(pipe, card)
    check_species_names(pipe, card)        # hard requirement for multi-type input
    apply_color_mode(pipe, card)
    style_atoms(pipe, None, card)          # per-type names/colors/radii (source-level)
    data = pipe.compute()
    colorbars = resolve_auto_color_ranges(pipe, data)  # range:auto -> real limits
    if colorbars:
        data = pipe.compute()              # re-evaluate with resolved ranges
    style_structure_types(pipe, data)      # visible 'Other' color on white bg
    full_data = pipe.source.compute()      # unfiltered frame, for composition
    dxa = dxa_summary(data, orientation)
    if getattr(data, "dislocations", None) is not None:
        try:
            data.dislocations.vis.line_width = float(
                (card.get("annotate") or {}).get("dxa_line_width", 2.0))
            data.dislocations.vis.show_burgers_vectors = False
        except Exception:
            pass
    label_text = build_label_text(card, data, orientation, dxa, full_data)
    vp = make_viewport(card, orientation)
    pipe.add_to_scene()
    vp.zoom_all()
    # fit margin: enlarge the field of view so overlays (tripod, labels,
    # legend) land OUTSIDE the projected cell rather than on top of it
    margin = float((card.get("view") or {}).get("fit_margin", 1.15))
    vp.fov = vp.fov * margin
    zoom = (card.get("view") or {}).get("zoom", "fit")
    if isinstance(zoom, (int, float)):
        vp.fov = vp.fov / float(zoom)
    add_overlays(vp, card, pipe, data, orientation, label_text)
    scene = _resolved_scene(pipe, vp, card, colorbars, dxa, full_data, orientation)
    return card, input_path, pipe, data, vp, dxa, scene


def run_render(card_path: str, out_override: str | None = None, *,
               ask: bool = False) -> Path:
    card, input_path, pipe, data, vp, dxa, scene = _prepare(card_path, ask=ask)
    w, h, renderer_name, bg, alpha = resolve_output(card)
    renderer = make_renderer(renderer_name)
    n_frames = pipe.num_frames if hasattr(pipe, "num_frames") else pipe.source.num_frames
    movie = n_frames > 1 and (card.get("output") or {}).get("movie", n_frames > 1)
    suffix = ".mp4" if movie else ".png"
    out_path = Path(out_override) if out_override else _auto_outname(card, input_path, suffix)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if movie:
        fps = int((card.get("output") or {}).get("fps", 10))
        vp.render_anim(filename=str(out_path), size=(w, h), fps=fps,
                       renderer=renderer, background=bg)
    else:
        vp.render_image(filename=str(out_path), size=(w, h), renderer=renderer,
                        background=bg, alpha=alpha)
    prov = _provenance(card, input_path, out_path, scene)
    _embed_prov_png(out_path)
    print(f"[ovzm] wrote {out_path}")
    print(f"[ovzm] provenance: {prov}" +
          (" (also embedded in the PNG)" if out_path.suffix == ".png" else ""))
    if dxa.get("n_segments"):
        print(f"[ovzm] DXA: {dxa['n_segments']} segments, "
              f"total {dxa['total_length']:.0f} Å")
    return out_path


def run_session(card_path: str, out_override: str | None = None, *,
                ask: bool = False) -> Path:
    card, input_path, pipe, data, vp, dxa, scene = _prepare(card_path, ask=ask)
    out_path = (Path(out_override) if out_override
                else _auto_outname(card, input_path, ".ovito"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # adopt our configured camera into the session's viewport layout.
    # NOTE: overlays are deliberately NOT saved into the session — the ovito
    # Python module (observed on 3.15.5) writes corrupt .ovito files when
    # viewport overlays are present in the scene. Labels/tripod/colorbar are
    # a render-path feature; the session gives you data + pipeline + camera.
    try:
        ovito.scene.viewports.active_vp.type = vp.type
        ovito.scene.viewports.active_vp.camera_dir = vp.camera_dir
        ovito.scene.viewports.active_vp.camera_pos = vp.camera_pos
        ovito.scene.viewports.active_vp.fov = vp.fov
    except Exception as exc:  # session still usable without camera transfer
        print(f"[ovzm] note: could not transfer camera to session viewport: {exc}",
              file=sys.stderr)
    print("[ovzm] note: overlays (tripod/labels/colorbar) are not embedded in "
          "sessions; use 'ovzm render' for the annotated image", file=sys.stderr)
    ovito.scene.save(str(out_path))
    prov = _provenance(card, input_path, out_path, scene)
    print(f"[ovzm] wrote session {out_path} — open it in the OVITO GUI")
    print(f"[ovzm] provenance: {prov}")
    return out_path
