---
name: ovito-auto-viz
description: >
  Render LAMMPS dumps/data files into publication-quality images, movies, or
  ready-to-open OVITO sessions via declarative YAML viz-cards and the ovzm
  CLI. Use whenever the user wants to visualize a LAMMPS file, render a
  dislocation/DXA picture, make an OVITO figure or movie, prepare an OVITO
  session, or asks for "the standard view" of a simulation snapshot.
---

# ovito-auto-viz — driving OVITO through viz cards

The tool lives in the `ovito-auto-viz` repo (CLI: `ovzm`, installed via
`pip install -e <repo>`). You write a small YAML **viz card** describing the
figure and run `ovzm render card.yaml`. Do not write ad-hoc ovito Python
scripts for tasks a card can express — the card IS the deliverable the user
can rerun, tweak, and version.

## Required information — ask, never guess

Before composing a card, run `ovzm info <file>` and check what is missing.
These must come from the user if not auto-detectable; ask for them explicitly
(one short question listing exactly what is needed):

- **Species names** for multi-type files (dumps carry none; `ovzm render`
  hard-errors without them). Never invent a mapping — type order in LAMMPS
  is arbitrary.
- **Crystal orientation** (x/y/z Miller triplets) unless encoded in the
  filename. Without it, b/ξ labels are only available in DXA's lattice frame.
- **View and what to show**, if the user's request doesn't imply them
  ("glide-plane view", "along the line", "everything").
- **Figure creator** (meta.creator) if neither an ovzm-project.yaml (project root) nor a personal identity file supplies it — mandatory, never invent it. Suggest creating an ovzm-project.yaml in the project root so it is answered once per project.
- **Units** for any color-coded property (the limits are auto-resolved, the
  units are physics the data doesn't carry).

## Workflow

1. Locate the repo (`ovzm --help` works if installed; else find
   `ovito-auto-viz/` and `pip install -e` it). Read `presets/` for available
   bases and `docs/SCHEMA.md` for every key.
2. Compose a card that `extends:` the closest preset (`dxa-standard` for
   defect/dislocation views, `segregation-map` for solute distribution) and
   overrides only what the task needs.
3. `ovzm validate card.yaml`, then `ovzm render card.yaml`.
4. Look at the produced PNG yourself and iterate (view, zoom, radii, label
   placement) before showing the user.
5. If the user wants to inspect interactively, also run
   `ovzm session card.yaml` and hand them the `.ovito` file (pipeline +
   camera preset; overlays only exist in rendered images).

## Conventions that matter

- **Crystal orientation**: set `crystal: {x: [...], y: [...], z: [...]}` when
  known; `x: auto` parses `x-101_y1-21_z111`-style filenames. The orientation
  drives Miller-labeled tripods, Miller view directions, and ξ/character
  labels. Without it you still get b in lattice coordinates.
- **Labels are computed, never invented**: `annotate.labels: auto` derives
  b, ξ, character angle, family totals, and composition from the data. If
  metadata (e.g. a dcreator `.disparam`) exists, compare DXA's answer against
  it and report discrepancies to the user.
- **Big files**: keep `atoms.show: non_fcc` (or a slab via `slice:`) so only
  defect atoms render. Renders are cheap; PTM/DXA is the expensive step —
  don't rerun a card needlessly. On clusters, run inside a batch job, never
  on a login node.
- Every render writes a `.prov.yaml` sidecar — leave it next to the image;
  it is the figure's reproducibility record.
- Keep cards in the project tree next to the data they render, with
  descriptive names (`d90-glideplane.yaml`, not `viz2.yaml`).
