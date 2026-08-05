# TASK: Per-grain tripods (v0.4.0)

Implementation brief for a Claude Code session in this repo
(`~/DEVEL/ovito-auto-viz` on the Mac). Written 2026-08-05 in a Cowork
planning session with Erik; this file is the agreed spec.

**Read `CLAUDE.md` first** — design decisions 1–7 there are binding
(frame discipline, labels-are-computed, total provenance, attribution
headers). Note: its "Three separate Pythons" section describes Cowork
sessions; in Claude Code on the Mac you work directly in Erik's conda
env (editable install: `pip install -e /Users/e.bitzek/DEVEL/ovito-auto-viz`)
and can run `pytest` and real renders locally. Use absolute paths in every
command you show Erik. Do not commit or push without his explicit go-ahead.

## Motivation

Backlog item "per-grain tripods for polycrystals" (CLAUDE.md roadmap 6).
Immediate driver: the planned README hero figure — a published W GB crack
(bicrystal, P segregation at the GB) — needs one labeled tripod per grain.
Design for N grains; the bicrystal is just N=2. The feature is
lattice-agnostic (works for bcc W exactly like fcc).

## Scope of v1

Draw one coordinate tripod per grain, anchored at a user-provided grain
ORIGIN, oriented per a user-provided grain ORIENTATION, each arm labeled
with its Miller indices, optionally with the grain name.

Explicit NON-goals (next versions, do not implement now):
- Re-expressing DXA segment b/ξ in each grain's local frame.
- Running OVITO GrainSegmentationModifier to find grains automatically.
- Quaternion/rotation-matrix input; converters from segmentation or
  Voronoi-construction tool outputs.
- Per-grain atom coloring, GB extraction, example polycrystal datasets.

ovzm never guesses (design rule 3 analog): origins and orientations are
always provided by the user — inline in the card or via a grains file
produced manually, from a Voronoi construction list, or from a
segmentation tool. If a `grains:` block is present but incomplete, that
is a hard, readable error — never a silent fallback.

## Card syntax

```yaml
grains:                        # optional top-level block
  file: grains-d005.yaml       # EITHER external file (path relative to the
                               # card, same convention as input.file)
  items:                       # OR inline list — file XOR items, hard error
    - name: upper              # optional; defaults g1, g2, ...
      origin: [12.0, 40.0, 88.5]   # REQUIRED, Å, cartesian, simulation frame
      x: [-1, 0, 1]            # REQUIRED: Miller indices, in THIS grain's
      y: [1, -2, 1]            # crystal frame, of the three SIM-BOX axes —
      z: [1, 1, 1]             # identical semantics to the crystal: block
      axes: [[1,0,0],[0,1,0],[0,0,1]]  # optional per-grain override, see below
  tripod:                      # styling, all optional
    size: 20                   # arm length in Å (world-anchored; default:
                               # 5% of the largest box edge, min 10 Å)
    axes: box                  # global default arm mode: 'box' | list of 3
                               # Miller triplets (per-grain axes overrides)
    show_names: true           # grain name drawn near the origin
```

The external grains file is the same shape:

```yaml
# created with ovito-auto-viz ... (YAML_CREDIT_HEADER if ovzm ever writes one)
grains:
  - name: upper
    origin: [12.0, 40.0, 88.5]
    x: [-1, 0, 1]
    y: [1, -2, 1]
    z: [1, 1, 1]
  - name: lower
    ...
```

## Orientation semantics and math

Per grain, `x/y/z` are the crystal directions lying along the simulation
box axes — exactly the existing `crystal:` semantics. REUSE the matrix
construction and validation from `src/ovzm/crystal.py` (orthogonality,
right-handedness, normalization); do not duplicate it. Integer triplets
are the normal case; floats are accepted (segmentation-derived
orientations) — validate orthogonality the same way and render labels
from the values as given (existing Miller formatting in `labels.py`;
floats with ≤3 decimals).

Arm modes:
- `axes: box` (default): the three arms point along the sim-box axes
  ex/ey/ez and are labeled with the grain's x/y/z triplets. This mirrors
  the existing corner tripod, per grain — the right default for
  CSL/bicrystal constructions.
- `axes: [[h,k,l], ...]` (exactly 3 triplets): each arm points along that
  crystal direction of the grain expressed in the sim frame (transform
  via the grain's orientation matrix from crystal.py), labeled `[hkl]`.
  This covers Voronoi polycrystals with arbitrary rotations, where box
  axes are not low-index: give `[[100],[010],[001]]` and each grain shows
  its own cube axes.

Add an analytic unit test for the transform: a grain rotated 90° about z
must map crystal [100] to sim −y (or the convention crystal.py implies —
lock it in with the test, don't hand-wave it).

## Rendering

Implement as a `PythonViewportOverlay` (this is the approach the roadmap
already names). Per grain: project origin and the three arm tips
(origin + size × dir_sim) into viewport coordinates with the overlay
API's projection; draw arms as 2D lines with small arrowheads, always on
top of the atoms — that is deliberate; a tripod inside a dense grain must
stay visible. Arm length is specified in Å (world), so apparent size
scales with zoom and stays identical across grid panels.

Details:
- Axis colors: same x/y/z color convention as the existing corner tripod
  (check `scene.py`); labels in the same font/color logic as existing
  overlays, with a thin contrasting halo/outline so they survive busy
  backgrounds.
- Grain name (if `show_names`) drawn offset from the origin, avoiding the
  three arm labels (simple fixed offsets are fine for v1).
- If a projection fails (point behind a perspective camera), skip that
  tripod with a stderr warning, never crash.
- `view.fit_margin` logic is untouched: grain tripods live INSIDE the
  cell by design and are overlay-space, so zoom-to-fit must not react to
  them.
- Interaction with existing options: `annotate.tripod` (corner tripod)
  stays fully independent — both may be on simultaneously.

Grids (`ovzm grid`): grain tripods are data annotation, not legend —
draw them on EVERY panel. `grid.tripod: first|all` continues to govern
only the corner tripod. Cameras are shared across panels, so the
projected tripods must come out geometrically identical; assert that in
a test if cheap, otherwise verify manually once.

Sessions (`ovzm session`): overlays corrupt .ovito files on module
3.15.5 (CLAUDE.md gotcha 1) — grain tripods are skipped like all other
overlays; extend the existing warning message to mention them.

## Validation and errors (all via `ovzm validate` too)

- `grains.file` XOR `grains.items` — both or neither (with a `grains:`
  block present) is a hard error.
- Missing origin or x/y/z on any grain: hard error naming the grain.
- Non-orthogonal / left-handed triads: reuse crystal.py's error text.
- Duplicate grain names: hard error. Missing names: auto-assign g1..gN.
- Origin outside the box (plus 10% margin): WARNING, still drawn.
- grains file missing/unparseable: hard error with the resolved path.

## Provenance (design rule 5 — total and inseparable)

The resolved `.prov.yaml` (and thus the PNG `ovzm_prov` chunk) gains a
`grains:` block: source (`inline` or the grains-file path AND its
sha256), the fully resolved per-grain list (name, origin, x/y/z, arm
mode/axes), and the resolved tripod styling (size, show_names). The
figure must be reconstructible from provenance alone, as everywhere else.

## Schema and docs

- Extend `src/ovzm/schema/vizcard.schema.json`; regenerate
  `docs/SCHEMA.md` via `python tools/gen-schema-md.py`.
- README: short section "Per-grain tripods (bicrystals, polycrystals)"
  with the card snippet above and one sentence on the grains file;
  update the roadmap line.
- `skills/ovito-auto-viz/SKILL.md`: add grains to the never-guess table —
  the agent must ASK for origins/orientations or a grains file. Remind
  Erik at the end that the account-installed skill copy does not track
  the repo and needs re-delivery.
- CLAUDE.md: move the backlog item to done (with date); record follow-ups
  (per-grain segment frames; auto-segmentation; input converters).

## Tests and CI

- `tests/make_bicrystal.py`: generate a SMALL unrelaxed fcc bicrystal
  (two slabs, exact CSL rotation about [001] so all triplets are
  integers, ~10–40k atoms) plus the matching `grains.yaml`. Unrelaxed is
  fine — this is a render/geometry fixture, not physics.
- Unit tests: inline vs file parsing, XOR error, orthogonality error,
  duplicate names, auto-naming, the analytic arm-direction test, label
  formatting for int and float triplets.
- Render smoke test (extends the CI `render` job): render the bicrystal
  with a grains block; assert PNG non-blank AND the prov contains a
  `grains:` block with 2 entries and the file sha256. Upload the PNG as
  a CI artifact for eyeballing.
- Keep py3.9 compatible — the packaging matrix runs 3.9; no 3.10-only
  syntax anywhere in `src/`.

## Housekeeping

- Version bump to 0.4.0 (`pyproject.toml`, `src/ovzm/__init__.py`).
- Every new source file carries the standard author/funding header;
  any YAML the tool writes gets `YAML_CREDIT_HEADER` (design rule 7).

## Acceptance criteria

1. Bicrystal fixture renders two tripods at the given origins with
   correct, test-asserted arm directions and Miller labels + names.
2. `ovzm validate` rejects every malformed grains block with a readable,
   grain-naming error.
3. `.prov.yaml` and `ovzm prov <png>` show the resolved grains block
   including the grains-file sha256.
4. `ovzm grid` draws the tripods identically on all panels;
   `ovzm session` skips them with an explicit warning and writes a valid
   file.
5. Full test suite green locally and in CI (packaging 3.9+3.12 legs and
   render job); SCHEMA.md regenerated; README + SKILL.md + CLAUDE.md
   updated; version 0.4.0.
