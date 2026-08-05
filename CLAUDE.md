# CLAUDE.md — restart notes for ovito-auto-viz

Read this first when resuming work on this project. It records status, the
design decisions and their reasons, hard-won gotchas, and the agreed roadmap.
(Written 2026-08-04 at the end of the bootstrap session that built v0.1.0 →
v0.3.1. Erik = Erik Bitzek, sole author; sessions run via Claude Cowork with
the repo at ~/DEVEL/ovito-auto-viz on the Mac "M5".)

## Start here — handoff, end of session 2026-08-05

**Repo state:** `main` = `928f705` "0.3.2: ship presets and schema as package
data…", committed AND pushed; `origin/main` matches. Working tree clean apart
from whatever this file's latest edit adds.

**`CLAUDE.md` is now TRACKED and public on GitHub.** It was untracked until
that commit. It names the `~/Desktop/SIMULATIONS/...` paths and the full
roadmap. If publishing it was not intended:
`git rm --cached CLAUDE.md && echo CLAUDE.md >> .gitignore` (and remember the
content stays in the pushed history).

**Do this first: check CI.** `.github/workflows/ci.yml` is brand new and ran
for the first time on `928f705`. Nobody has seen the result —
https://github.com/biterik/ovito-auto-viz/actions. It was rehearsed
step-by-step locally (all green), but never on a GitHub runner. Most likely
snags, in order: the `render` job installs `ovito` from PyPI (large download;
the GL apt packages are already in the job); the py3.9 leg of the `packaging`
matrix (checked statically for 3.10-only syntax — clean — but not executed on
3.9); `actions/upload-artifact@v4` pinning. Note Claude cannot reach
api.github.com from the Cowork sandbox, so it cannot check runs for you —
paste the failing log in and it can fix from that.

**Environment reality (verified 2026-08-05), the thing that confused this
session:** see "Three separate Pythons" under Session workflow below. Short
version: Claude renders in the disposable Cowork cloud sandbox; the device
bridge is an aarch64 Linux VM with NO network that cannot run `ovzm`; Erik's
Mac conda env is his alone and Claude cannot execute there.

**Git from the bridge leaves a stale `.git/index.lock`.** Any `git` command
Claude runs via `device_bash` creates it and cannot remove it (unlink is
refused on the mount). It is zero bytes and harmless but blocks the next
local git command. Fix on the Mac:
`rm -f /Users/e.bitzek/DEVEL/ovito-auto-viz/.git/index.lock`.
Prefer read-only git via the bridge, and hand Erik copy-paste blocks.

**Skill:** `skills/ovito-auto-viz/SKILL.md` is installed in Erik's Cowork
account (delivered as a `.skill` file, updated for 0.3.2). Re-deliver a
repackaged `.skill` whenever that file changes — the account copy does NOT
track the repo.

**Next actions, in order:**
1. Confirm CI is green; fix whatever it turns up.
2. **PyPI** — now genuinely unblocked. Check the name `ovito-auto-viz` is
   free, set up trusted publishing from a GitHub Action, release 0.3.2.
   Never publish <0.3.2: those wheels are broken (see Status).
3. **Dislocation-dipole generator + physics tests** (roadmap 2, still open) —
   `tests/make_fcc.py` only makes a perfect crystal.
4. **README figure** — still blocked on Erik: his D90 data, or generated?
   Note `~/Desktop/SIMULATIONS/` is NOT a connected Cowork folder, so Claude
   currently cannot see the D90 dumps at all; Erik must "Add folder" first.
5. Legend defect (see below) — Erik's call.

## What this is

A standalone CLI tool (`ovzm`) + YAML "viz card" format for reproducible
OVITO visualization of LAMMPS files, with an optional agent skill
(`skills/ovito-auto-viz/`). Tool first, skill second — the card is the shared
interface for humans, scripts, and LLMs alike. See README.md for the user
view; this file is the developer/agent view.

## Status (2026-08-05)

- **v0.4.0 in the working tree** (0.3.1 released), public at
  https://github.com/biterik/ovito-auto-viz (branch `main`), DOI
  **10.5281/zenodo.21796154** (concept DOI, Zenodo auto-archives releases).
  PyPI: NOT yet published.
- **0.4.0 adds per-grain tripods (2026-08-05, roadmap-6 backlog item →
  done).** New `grains:` card block (`file` XOR `items`; per-grain REQUIRED
  origin + x/y/z with `crystal:` semantics; `tripod: {size, axes, show_names}`;
  arm modes `box` | 3 Miller triplets), drawn via a legacy-API
  `PythonViewportOverlay` in `scene.py:add_grain_tripods` (arms + arrowheads +
  halo labels ON TOP of atoms, world-anchored Å length). Logic lives in
  `src/ovzm/grains.py`, which deliberately imports no ovito so `ovzm validate`
  and the unit tests run in the packaging CI job (that job now installs numpy).
  Grid draws them on EVERY panel (verified pixel-identical); sessions skip
  them (overlay-corruption gotcha) with an extended warning; prov gains a
  resolved `grains:` block incl. grains-file sha256. Fixture:
  `tests/make_bicrystal.py`, an exact Σ5 [001] twist bicrystal (nxy must stay
  a multiple of 5 — that makes BOTH grains commensurate with the periodic box,
  so PTM classifies the interiors cleanly fcc; nxy=14 looked "broken" for
  exactly this reason). The stale `tripods:` schema placeholder was replaced
  by the real `grains:` schema.
- **0.4.0 also merges Erik's `0.4.0-structure-colors-and-view.patch`**
  (applied by hand 2026-08-05 — it no longer applied after the tripod work):
  `atoms.structure_colors` (card key → RGB for PTM/CNA/DXA structure types),
  pinned per-type colors in structure mode (`atoms.colors` entries override
  the structure color — "matrix by structure, solutes by species"),
  `view.center` (re-aim camera at a world point, keeps zoom_all distance),
  honoring `view.direction_sim_frame` + the resolved up vector. Two fixes
  beyond the patch, found by rendering: (1) **DXA carries its own
  `structures` list and runs after PTM in dxa-standard, so it must be
  recolored too** — this is also why the old Other→GRAY tweak never showed
  in DXA renders (GB atoms rendered 0.95-white); (2) the icosahedral type is
  named 'ICO' on 3.15.5, not 'Icosahedral'. Verified by render: fcc/other
  recolor + orange pinned solutes + GB-centered zoom all correct. The patch
  file itself can be deleted once committed.
- **0.3.2 fixes the packaging bug that would have broken the PyPI release.**
  `presets/` and `schema/` sat at the repo root and were not declared as
  package data, so a non-editable install shipped neither: `extends:` raised
  FileNotFoundError and `ovzm schema` printed `null` **silently**, because
  `validate()` treated a missing schema as "no problems". Fixed by moving both
  into the package (`src/ovzm/presets/`, `src/ovzm/schema/`) + package-data in
  `pyproject.toml` + `MANIFEST.in`; `load_schema()` now raises
  `SchemaUnavailableError` instead of returning None, and the CLI reports it
  cleanly with exit 1. Verified: wheel installed into a clean venv with the
  source tree absent — schema prints, both presets resolve, an invalid card is
  rejected, editable installs still work.
- **`tests/` and `.github/workflows/ci.yml` now exist.** `tests/make_fcc.py`
  generates a data-free 2048-atom fcc block; `tests/test_packaging.py` (10
  tests) guards the regression and must be run from a scratch dir so the
  cwd/REPO_ROOT fallbacks cannot mask it. CI has a `packaging` job (build
  wheel, assert package data present, install, test, CLI smoke on py3.9+3.12)
  and a `render` job (real ovito + DXA + Tachyon on the generated block,
  asserting the PNG is not blank).
- All features verified end-to-end on real data: the 568k-atom SGCMC dumps in
  `~/Desktop/SIMULATIONS/EAM-DISLOCS-Ni-Cu/SGCMC-D90-T300-dmu0p90/`
  (D90 = dissociated 90° edge, b = ½[-101], ξ = [1-21], two 60° Shockleys —
  use these numbers as regression ground truth; the `.disparam` files in the
  project root are the independent reference).
- Commands: render, grid, session, import, info, prov, validate, schema.
- `ovzm-project.yaml` attribution files exist in `examples/` and in the real
  `SIMULATIONS/EAM-DISLOCS-Ni-Cu/`.

## Design decisions that must survive refactors

1. **Frame discipline (the "80° edge" bug).** DXA's `true_burgers_vector`
   lives in DXA's own lattice frame — an arbitrary cubic-symmetry-equivalent
   choice that generally differs from the card's crystal frame. ALL geometry
   (Miller indices in the card frame, ξ, character angles, net b) must use
   `segment.spatial_burgers_vector` (sim frame); true_b is only for family
   classification and the a-estimate (= |b_spatial|/|b_true|).
2. **Labels are computed, never taken from metadata.** Nucleated dislocations
   have no metadata. `.disparam`/filenames are cross-checks and conveniences.
3. **Never guess species names.** LAMMPS type order is arbitrary; multi-type
   input without a name mapping is a hard error (card / project file /
   identity file / --ask).
4. **Attribution resolves per key, git-config style:** card `meta:` >
   `ovzm-project.yaml` (walk UP from card dir, then input dir) >
   `~/.config/ovzm/identity.yaml` > `--ask`. Creator mandatory. Project files
   may carry a `people:` map for per-person affiliation/ORCID.
5. **Provenance is total and inseparable:** `.prov.yaml` sidecar (resolved
   card + resolved scene: types/colors/radii, colorbar limits+units, camera,
   composition, full DXA result) AND the same YAML embedded in the PNG as a
   compressed text chunk, key `ovzm_prov`. Naming: figure ID =
   `<input-stem>__<card-name>[__<tag>]`, shared by image and sidecar.
6. **Grids exist for comparability:** one camera, one magnification (widest
   tight-fit), one set of colorbar limits (resolved on panel 1, forced on the
   rest) across all panels.
7. Attribution headers: every source file carries the author/funding header;
   every YAML the tool writes gets `YAML_CREDIT_HEADER` (see
   `src/ovzm/__init__.py`). Keep both when adding files.

## Gotchas verified the hard way (ovito module 3.15.5)

- `ovito.scene.save()` writes **corrupt** session files if viewport overlays
  are in the scene → `ovzm session` deliberately skips overlays. Re-test on
  module upgrades; consider reporting upstream (matsci.org).
- Naming a ParticleType (e.g. "Ni") RESETS its color/radius to element
  defaults → set names BEFORE card colors/radii (`style_atoms`).
- OVITO expression language: no leading `!(...)`; use `(expr) == 0`.
- Per-type styling must happen on `pipe.source.data` (with `make_mutable`),
  not on a computed DataCollection (render-inert).
- OVITO's expression selection/PTM classify the free surfaces as non-fcc —
  expected in `show: non_fcc` views; slice them away when they occlude.
- Headless Linux needs `libopengl0 libegl1 libgl1 libglx0 libxkbcommon0`;
  Tachyon renders without GPU/display.
- Cowork device bridge: `tar x --overwrite` required on the mounted FS
  (unlink is refused); `rm` impossible — move cruft to `_to_delete/`.

## Session workflow that worked

**Three separate Pythons — do not confuse them** (verified 2026-08-05):

1. **Erik's Mac (macOS, conda-forge).** The only place the README's install
   instructions apply. `pip` is NOT global on the Mac and must not be made
   global; installs go inside a conda env. Claude cannot execute anything
   here — there is no macOS shell in either Cowork mode.
2. **The Cowork cloud sandbox** (Claude's `bash`): disposable x86_64 Linux,
   Python 3.11, full network. **This is where Claude runs `ovzm`.**
   `pip install --break-system-packages` is fine precisely because the
   container is thrown away. Setup, ~2 min:
   `pip install --break-system-packages git+https://github.com/biterik/ovito-auto-viz.git`
   plus `apt-get install -y libopengl0 libegl1 libgl1 libglx0 libxkbcommon0`
   (the ovito wheel imports fine after that; verified with ovito 3.15.5).
   Installing from GitHub beats staging the source — the repo is public.
3. **The device-bridge VM** (`device_bash`): Ubuntu 22.04 **aarch64** Linux
   on the Mac with the connected folders mounted — NOT macOS. No conda and
   **no network**, so it can neither `pip install` nor `git push`, and it
   **cannot run `ovzm`**. Use it only for file access, inspection and local
   git. Same VM backs "run on your computer", so switching modes does not
   help.

Working loop: stage the dump from the Mac → render in the cloud sandbox →
`SendUserFile` the PNG + `.prov.yaml` → `device_commit_files` to write them
back to the Mac. Only folders Erik has connected are reachable — the
`SIMULATIONS/` tree is not connected by default and he must add it.

Erik runs all git/gh commands himself (hand him copy-paste blocks with
absolute paths, per his standing preference) — and he has to, since neither
Claude environment can push: the bridge VM has no network and the sandbox
has no write token for the repo. Check file mtimes on the Mac before
overwriting — he edits between sessions.

## Agreed roadmap (order matters)

1. **README figure** (glide-plane render or evolution grid at the top) —
   needs Erik's ok to show research data, else use item 2's output.
2. **Example-structure generator + tests + CI** — PARTLY DONE (2026-08-05).
   Done: `tests/make_fcc.py` (perfect fcc block, no dislocation), packaging
   regression tests, CI with a real render job. Still open: a generator that
   inserts a **dislocation dipole** (few 100k atoms) and pytest asserting the
   D90 ground truths (2 Shockleys, 60°, net ½⟨110⟩ 90°, a≈3.52 Å). That is
   what JOSS actually needs — the current tests prove the package installs and
   renders, not that the physics is right.
3. **PyPI** — unblocked by the 0.3.2 packaging fix (check name availability;
   trusted publishing via GitHub Action). Do NOT publish a version before
   0.3.2: earlier wheels are broken as described above.
4. **Visibility**: matsci.org announcement (OVITO + LAMMPS categories; also
   report the session-overlay bug), awesome-claude-skills PRs, JOSS paper.
5. **Ontologies/schemas from computational materials science** (Erik's idea,
   2026-08-04): make the prov machine-*interpretable*, not just
   machine-readable — map viz-card/prov terms to existing ontologies and/or
   emit a JSON-LD context alongside the YAML. Candidates to evaluate at
   restart (verify current state, all pre-2025 knowledge): **CMSO**
   (Computational Material Sample Ontology) and **atomRDF/pyscal-rdf**
   (NFDI-MatWerk, S. Menon et al.), **DISO** (Dislocation Ontology — direct
   fit for the DXA output), **PODO** (point defects), **PMDco** (Platform
   MaterialDigital core ontology), **EMMO**, and **PROV-O** for the
   provenance graph itself. Natural NFDI-MatWerk deliverable; possibly its
   own paper. Design sketch: `prov.yaml` gains an optional `@context` /
   `semantics:` block mapping keys → IRIs; `ovzm prov --jsonld` exports RDF.
6. Backlog: movie polish (frame ranges), `.zst` input, broader `ovzm import`
   modifier coverage, pair_coeff-sniffing to *suggest* species names.
   Per-grain tripods: DONE 2026-08-05 (v0.4.0, see Status; spec was
   `docs/TASK-per-grain-tripods.md`). Follow-ups deliberately NOT in v1:
   re-expressing DXA segment b/ξ in each grain's local frame; running
   GrainSegmentationModifier to find grains automatically; converters from
   segmentation / Voronoi-tool output (incl. quaternion input); per-grain
   atom coloring / GB extraction / example polycrystal datasets.

## Known cosmetic defect (found 2026-08-05, not fixed)

The discrete structure-type legend (`ColorLegendOverlay(property=...)`,
`scene.py` §(b)) lists **all six** PTM structure types even when only one is
present, and its labels collide and clip at the right edge
("BCCCubic diamondHexagonal diamond"). Visible in every `dxa-standard`
figure. The ovito 3.15.5 overlay API has no label filter, so the options are
(a) `orientation` = vertical + `legend_size`/`label_size` tuning, which stops
the collision, and/or (b) deleting unused ElementTypes from the Structure
Type property before rendering, which also drops the unused swatches.
Erik's call — it changes how all his figures look.

## Open questions for Erik at restart

- Which README figure (his data vs. generated example)?
- PyPI name: `ovito-auto-viz` (check it's free).
- Ontology scope: annotation-only (JSON-LD context) or full RDF export?
