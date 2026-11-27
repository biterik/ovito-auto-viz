# TASK: upstream three local patches + one ordering fix (target v0.4.3)

Written 2026-11-27 by the LLM-LAMMPS designer session 2026-11-27-1600-designer-inbox-and-tool-cards, from the
LLM-LAMMPS inbox entry of 2026-11-21 (pilot 2026-11-21-1625-turlo-status-readout). Not yet started.

## Where it came from

Matching published figures (Turlo & Rupert 2020) for the TURLO-REDO status deck, the pilot had to patch ovzm 0.4.2 in
its render sandbox. The diff (against the 0.4.2 repo, 85 lines, 4 files) is at

    /Users/e.bitzek/Desktop/SIMULATIONS/TURLO-REDO/50_TURLO-METHOD-VS-OURS-CU-ZR/ANALYSIS-FINAL-2NS/OVITO-TR-COLOURS/ovzm-0.4.2_local-patches_2026-11-21.diff

The cards that use the patched keys are in the same folder (`t50-TRcolors-base.yaml`, `t50_R1_TRcolors-*.yaml`).

## The three gaps (each a schema key + code + test)

1. **`ptm: {structures: [ico, ...]}`** -- enable extra PTM templates. Icosahedral (and sc, diamond, graphene) are off
   by default in OVITO's PTM modifier, and a card had no way to switch them on. Patch: `pipelinebuild.py` maps the
   names to `PolyhedralTemplateMatchingModifier.Type` and sets `m.structures[...].enabled = True`. Validate unknown
   names with a readable error (the patch raises KeyError).
2. **`view.fov`** -- absolute half-height of the orthographic field of view, in Å, overriding `fit`/`zoom`.
   Reason: `view.zoom` is relative to `zoom_all()`, and that was NOT reproducible between renders of the same card
   (field 43 vs 95 Å). Needed whenever a figure must match a scale (published figure, comparison grid). Patch in
   `runner.py` after the zoom step. Record the applied value in the provenance. Consider making `ovzm grid` use one
   absolute fov for all panels by default.
3. **`annotate.tripod_font_size`** -- tripod label size (OVITO's relative unit, default 0.4) plus a white outline.
   Reason: at a 1500 px render shown at a third of a slide width the Miller labels print at ~10 pt. Patch in
   `scene.py`. Erik's figure rule (LLM-LAMMPS preferences "Plot defaults"): >= 14 pt on slides, >= 7 pt printed in
   documents -- so the default should also be revisited, not only made settable.

## The ordering gotcha (no patch yet -- decide: document or fix)

With `ptm` before `dxa` (the order of the `dxa-standard` preset), DXA overwrites the "Structure Type" property, so
`structure_colors` for types DXA does not know (e.g. ico) never show. Work-around used: put `dxa` first when PTM
colours matter. Better: have the preset (or the builder) order them so PTM's types survive, or warn when
`structure_colors` names a type that the last structure-identification modifier cannot produce.

## Also requested (LLM-LAMMPS 2026-11-02 follow-up)

Every card that shows a dislocation should carry a `crystal:` block (Erik's figure rule: Miller directions of the axes,
xi and b with signs in the figure). Consider a `ovzm validate` warning when a pipeline contains `dxa` and the card has no
`crystal:` block, and note in the docs that DXA follows the LH/SF (left-hand start-finish) convention and that b flips
sign with xi.

## Done means

Schema keys documented in `docs/SCHEMA.md`, tests (schema + a small render for 2 and 3), CHANGELOG/RELEASE-NOTES,
release 0.4.3 on PyPI, the skill repackaged, and the LLM-LAMMPS tool card `canon/tools/ovito-auto-viz.card.yaml`
updated (version, and the "local patches" gotcha removed).
