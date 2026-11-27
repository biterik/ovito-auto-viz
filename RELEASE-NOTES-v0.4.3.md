# ovito-auto-viz 0.4.3

Three card keys that were missing when matching published figures, a guard
against a silent PTM/DXA colouring failure, and two styling fixes. Every
0.4.2 card renders as before (one exception, see "Behaviour change").

## New card keys

- **`pipeline: [{ptm: {structures: [...]}}]`** — enable PTM's extra
  templates: `ico` (icosahedral), `sc`, `cubic_diamond`, `hexagonal_diamond`,
  `graphene`. They are off in OVITO by default and there was no way to switch
  them on from a card. Additive: fcc/hcp/bcc stay on. `atoms.structure_colors`
  accepts the new names too (`sc`, `graphene`), and unknown names are now
  rejected by the schema.
- **`view.fov`** — absolute field of view: the half-height of an
  orthographic view in Å (OVITO's own `Viewport.fov` convention). Overrides
  `fit`, `fit_margin` and `zoom`. Reason: those follow `zoom_all()`, which was
  not reproducible between renders of the same card (43 vs 95 Å seen on
  2026-11-21) — useless when a figure must match a published scale or a
  series must share one. In `ovzm grid` it gives every panel the same
  absolute field. The provenance records `camera.fov_source`. Refused with a
  perspective camera.
- **`annotate.tripod_font_size`** (OVITO's unit: relative to the tripod size,
  default 0.4) and **`annotate.tripod_outline`** (white outline; on by
  default once a font size is set). At slide size the default labels printed
  at ~10 pt.

## Guards

- **PTM before DXA is refused when it would hide colours.** DXA writes its own
  "Structure Type" (and numbers it differently from id 4 on), so with `dxa`
  after `ptm` — the `dxa-standard` order — a PTM-only type such as `ico`
  never reached the image and its `structure_colors` entry silently did
  nothing. `ovzm validate` / `render` now stop with the fix: put `dxa` first
  (the dislocation lines do not depend on the order). Cards whose colours
  name only types DXA also reports (other, fcc, hcp, bcc, the diamonds) are
  unaffected.
- **A `dxa` figure without a crystal frame warns** (validate and render, also
  recorded under `warnings:` in the provenance): without `crystal:` — or with
  `crystal: {x: auto}` and a file name that does not carry the
  `x-101_y1-21_z111` convention — the tripod, ξ and b cannot carry Miller
  indices. The warning also states DXA's LH/SF (left-hand start-finish)
  Burgers-circuit convention.

## Fixes

- **`atoms.radius: <number>` was ignored for named types.** Naming a type
  (`names: {1: Ni}`) gives it the element radius, and a per-type radius beats
  the global default ovzm set — so `radius: 0.4` rendered Ni at 1.24 Å. The
  uniform radius now goes on every type. *Behaviour change:* cards that set a
  uniform radius together with `names:` now render at the radius they ask for.
- Vertical discrete structure-type legend (no more label collision), already
  on `main` since 0.4.2 (6ebd2bb).

## Tests

20 new tests (67 in total, all green with ovito 3.17.2 on Linux):
`tests/test_v043_card_semantics.py` (schema + semantic checks, ovito-free, so
they also run in the packaging CI job) and `tests/test_v043_render.py`
(real pipeline and renders: a 13-atom icosahedron classified ICO only with
the template on and rendered in its `structure_colors` colour with `dxa`
first; `view.fov` identical for two box sizes and showing the requested
height; tripod font size / outline; uniform radius on named types).

Origin: the three local patches made for the TURLO-REDO status deck
(2026-11-21), see `docs/TASK-v0.4.3-ptm-structures-view-fov-tripod-font.md`.
