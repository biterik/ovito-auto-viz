# ovito-auto-viz

Declarative, reproducible OVITO visualization of LAMMPS files.
You describe the figure in a small YAML **viz card** — view, atom styling,
analysis pipeline, annotations, output quality — and the `ovzm` CLI turns it
into a rendered image, a movie, or a ready-to-open OVITO session. Everything
on the figure (Burgers vectors, line directions, character angles, composition,
colorbar) is **computed from the data itself**, so nucleated defects without
any metadata are labeled just as well as constructed ones.

**Author:** Erik Bitzek ([ORCID 0000-0001-7430-3694](https://orcid.org/0000-0001-7430-3694),
<e.bitzek@mpi-susmat.de>) — ¹ Max-Planck-Institut for Sustainable Materials,
Düsseldorf, Germany; ² Institute of Materials Simulation (WW8),
Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU), Fürth, Germany.
Built with Claude/LLM assistance.

**Funding:** Deutsche Forschungsgemeinschaft (DFG, German Research
Foundation) — NFDI 38/1, project number 460247524
(**[NFDI-MatWerk](https://nfdi-matwerk.de) consortium**).

**License:** BSD-3-Clause. **Citation:** see [`CITATION.cff`](CITATION.cff)
(GitHub's "Cite this repository" button). The
[`ovito`](https://pypi.org/project/ovito/) Python module is a dependency
(free of charge, including DXA), not vendored.

## Attribution of figures

Every figure records who made it. `meta.creator` is **mandatory** (the run
aborts without it); `project`, `funding`, `affiliation`, `email`, `orcid`
are optional. Because people work on several projects with different
funding and even different affiliations, attribution is resolved
**per key, git-config style**:

1. the card's own `meta:` block (most specific),
2. an **`ovzm-project.yaml`** found by walking UP the directory tree from
   the card and from the input data — put one in each simulation project
   root (e.g. `SIMULATIONS/EAM-DISLOCS-Ni-Cu/ovzm-project.yaml`); a file in
   a subdirectory (thread) overrides the project root's,
3. a personal `~/.config/ovzm/identity.yaml` (or `$OVZM_IDENTITY`) —
   typically just `creator: Jane Doe`,
4. `--ask` prompts interactively as the last resort (creator only).

A project file for a single-user project:

```yaml
# SIMULATIONS/EAM-DISLOCS-Ni-Cu/ovzm-project.yaml
project: EAM-DISLOCS-Ni-Cu
funding: NFDI-MatWerk (DFG 460247524)
creator: Erik Bitzek
people:
  Erik Bitzek:
    affiliation: MPI for Sustainable Materials, Duesseldorf / FAU WW8, Fuerth
    orcid: 0000-0001-7430-3694
```

For multi-user projects, omit the top-level `creator` (each user's identity
file supplies their name) and list everyone under `people:` — the resolved
creator's entry fills in their affiliation/email/ORCID for that project.
All resolved values land in the `.prov.yaml` and inside the PNG; every YAML
the tool writes carries the tool-credit header ("created with
ovito-auto-viz … funded by NFDI-MatWerk").

## Install

```bash
pip install -e .          # from this repo; installs the `ovzm` CLI
```

Headless Linux (cluster, CI) additionally needs the GL runtime the module
links against:

```bash
apt-get install libopengl0 libegl1 libgl1 libglx0 libxkbcommon0   # or distro equivalent
```

Rendering uses the Tachyon software ray-tracer by default — no GPU or display
required. On HPC, install into a venv under scratch (never `$HOME`) and run
renders inside a batch job.

## Quickstart

```yaml
# my-figure.yaml
name: d90-glideplane
extends: dxa-standard          # preset from presets/
input:
  file: dump_min_sgcmc_d90_T300.1530000.gz
crystal:
  x: [-1, 0, 1]                # or "auto" -> parsed from x-101_y1-21_z111 filenames
  y: [1, -2, 1]
  z: [1, 1, 1]
  lattice: fcc
view:
  direction: top               # named view, or a Miller direction like [111]
atoms:
  show: non_fcc
  names: {1: Ni, 2: Cu}
  colors: {1: [0.62, 0.66, 0.72], 2: [0.90, 0.45, 0.10]}
```

```bash
ovzm render  my-figure.yaml            # -> <input>__<name>.png + .prov.yaml sidecar
ovzm grid    comparison.yaml           # same card over grid.inputs -> one labeled grid
ovzm session my-figure.yaml            # -> .ovito file: open in the GUI, pipeline + camera preset
ovzm import  something.ovito           # best-effort reverse: GUI session -> card YAML
ovzm info    dump.gz                   # types, box, frames, filename-parsed orientation
ovzm prov    figure.png                # print the provenance embedded in the image
ovzm validate my-figure.yaml           # schema check with readable errors
ovzm schema                            # print the JSON schema
```

Every render writes a `.prov.yaml` sidecar AND embeds the same YAML into the
PNG itself (compressed `tEXt` chunk, key `ovzm_prov`) — image and provenance
cannot be separated; `ovzm prov figure.png` recovers it from the image alone.

### Comparison grids

`ovzm grid` renders the SAME card over several inputs (`grid.inputs`,
optional `grid.labels`/`grid.cols`) into one figure with **identical camera,
magnification, styling, and colorbar limits** across panels — the manual-GUI
failure mode this tool exists to kill. Tripod and legend are drawn once
(first panel; `grid.tripod: all` for every panel); each panel carries only
its title, and the per-panel analysis results (composition, DXA, …) live in
the grid's provenance under `panels:`.

## Required minimum information

`ovzm` refuses to guess what cannot be auto-detected. The contract:

| info | auto-detected from | if not detectable |
|------|--------------------|-------------------|
| input file | — | always required in the card |
| species names (multi-type files) | type names in the file (data files); dumps have none | **hard error** — add `atoms.names: {1: Ni, 2: Cu}` or run with `--ask` to be prompted |
| crystal orientation | `x-101_y1-21_z111`-style filenames | b/ξ labels fall back to DXA's lattice frame, flagged in the label block |
| lattice (for DXA) | — | preset default (`fcc` in `dxa-standard`); set `crystal.lattice` |
| view | — | preset default (`front`); set `view.direction` |
| what is shown | — | preset default (`non_fcc` in `dxa-standard`); set `atoms.show` |
| colorbar units | — | set `annotate.colorbar.units`; limits are resolved automatically and recorded in the prov file |

`ovzm info <file>` prints what a file does and does not carry (types, frames,
box, filename-encoded orientation) — use it before writing a card.

## Naming convention

Every figure has an ID: `<input-stem>__<card-name>[__<tag>]`. The card name
encodes the figure's identity (view + analysis, e.g. `d90-dxa-top`); the
optional `output.tag` distinguishes variants. Image and provenance sidecar
share the ID exactly:

```
dump_min_sgcmc_d90.1530000__d90-dxa-top.png
dump_min_sgcmc_d90.1530000__d90-dxa-top.png.prov.yaml
```

Multiple figures from the same input differ in card name; the same card on
multiple inputs differs in stem. The `.prov.yaml` records the ID, input
SHA-256, the resolved card, AND the fully resolved scene: per-type species
names / colors / radii, colorbar limits + units, camera, composition, and the
complete DXA result (per-segment b, ξ, character, net Burgers vector, and the
measured lattice-constant estimate). The image itself can therefore stay
visually clean — nothing is lost as long as the sidecar travels with it.

## What gets labeled automatically

With `annotate.labels: auto` (the default in `dxa-standard`), the label block
is composed from the data: timestep; total composition (e.g. `x(Cu) = 0.0100`)
plus shown-atom counts; DXA segment count and total line length; per-family
breakdown (perfect, Shockley, stair-rod, Hirth, Frank); the **net Burgers
vector with its character** (`net b = 1/2[-101], 90° edge`); and per-segment
`b = 1/6[-211] (Shockley partial), ξ = [1-21], 60° mixed, L = 100 Å`.

Frame discipline: DXA's `true_burgers_vector` lives in DXA's own lattice
frame, which can differ from the card's crystal frame by a cubic symmetry
operation. All geometry (Miller indices in the card frame, line directions,
character angles) is therefore computed from the segment's *spatial* Burgers
vector; the true vector is used only for family classification and the
|b_spatial|/|b_true| lattice-constant estimate. Character names are
conservative: `edge` ≥ 85°, `screw` ≤ 5°, otherwise the angle plus `mixed`.
If a dcreator `.disparam` is around it can serve as a cross-check, but
nothing requires metadata — nucleated dislocations label identically.

The coordinate tripod is labeled with the crystal axes (`x=[-101]`, …) and a
`view.fit_margin` (default 1.15) keeps all overlays outside the projected
cell. **Whenever atoms carry color information there is a legend**: a
continuous colorbar for `color_coding` (limits resolved from the shown data
when `range: auto`, units from `annotate.colorbar.units`), or a discrete
per-type legend when coloring by species.

## Presets

Cards inherit via `extends:` (chains allowed; search path: `$OVZM_PRESET_PATH`,
`./presets/`, repo `presets/`). Shipped:

- `dxa-standard` — PTM + DXA, non-fcc atoms only, Miller tripod, auto labels.
- `segregation-map` — all atoms colored by type, solute rendered larger.

Output quality presets: `draft` (1280×720, fast), `slide` (1920×1080),
`paper` (3200×2400, ambient occlusion). Background `white`/`black`/`transparent`.

## Multimillion-atom workflow

The intended pattern for big data is **analyze once, render many**: the
expensive step is PTM/DXA, not rendering. Typical defect views delete the
fcc/bulk atoms (`atoms.show: non_fcc`), which cuts the rendered particle count
by ~100×. For files too large for a laptop, run the same card on the cluster
headless inside a batch job; only PNGs come back. Positions at `%.4f` Å are
well above every OVITO method's noise floor.

## Documentation

- `docs/SCHEMA.md` — every card key, generated from `schema/vizcard.schema.json`
  (regenerate with `python tools/gen-schema-md.py`).
- Put `# yaml-language-server: $schema=<path>/vizcard.schema.json` at the top
  of a card for editor autocompletion.
- `skills/ovito-auto-viz/SKILL.md` — teaches LLM/agent sessions the card
  format so "render the standard DXA view of X" becomes a one-liner.

## Using it with Claude (the agent skill)

`skills/ovito-auto-viz/SKILL.md` is an [Agent Skill](https://github.com/anthropics/skills):
a plain instruction file (no code) that teaches a Claude session when to use
`ovzm`, what it must ASK the user instead of guessing (species names, crystal
orientation, figure creator, colorbar units), and how to compose cards from
the presets. The tool itself never requires any AI — the skill is an optional
adapter on top.

Install:

- **Claude Code** (CLI): copy the skill folder into your skills directory —

  ```bash
  mkdir -p ~/.claude/skills
  cp -R skills/ovito-auto-viz ~/.claude/skills/
  ```

  It then triggers automatically on requests like "render the standard DXA
  view of this dump" in any project where `ovzm` is installed.

- **Claude Desktop / Cowork**: add the skill via the app's
  Settings → Capabilities/Skills (upload or point it at
  `skills/ovito-auto-viz/`), or ask Claude in a session to package
  `SKILL.md` as an installable `.skill` file for your account.

Usage is then conversational: *"glide-plane view of
`SGCMC-D90/dump.1530000.gz`, Cu segregation, paper quality"* — the session
writes the card (asking for whatever the required-information table says it
cannot detect), runs `ovzm render`, and shows you the PNG plus the card so
you can version it with the project.

## Known issues / roadmap

- **Sessions contain pipeline + styling + camera, not overlays**: the ovito
  Python module (observed on 3.15.5) writes corrupt `.ovito` files when
  viewport overlays are in the scene, so `ovzm session` skips them. Use
  `ovzm render` for annotated output.
- Keep the OVITO GUI and the `ovito` module on matching versions when
  exchanging session files.
- Roadmap: comparison-grid shared colorbar for multi-property panels; per-grain tripods for polycrystals (orientations from a grains
  file or grain segmentation, drawn via a custom viewport overlay); movie
  polish (frame ranges); `.zst` input; CI smoke-renders of the presets on a
  generated example structure; broader `ovzm import` modifier coverage.
