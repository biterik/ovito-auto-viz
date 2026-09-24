# TASK — finish and ship the ovito 3.16 compatibility release (v0.4.2)

Brief for an autonomous Claude Code session. Written 2026-09-24 by a Cowork
session that did the analysis and the code changes in a Linux sandbox
against ovito 3.16.1 and 3.15.5 (see `RELEASE-NOTES-v0.4.2.md` and the
handoff at the top of `CLAUDE.md`). What is left is everything that needs
Erik's Mac, his conda environments, GitHub, and a human eye on a picture.

Work through the phases in order. Stop and report (do not guess) only at
the points marked **STOP**. Everything else: decide, do, record.

## Ground rules

- Repo: `/Users/e.bitzek/DEVEL/ovito-auto-viz`. Read `CLAUDE.md` first
  (repo-level) — it has the design decisions and the gotchas. The
  workspace-level `/Users/e.bitzek/DEVEL/CLAUDE.md` also applies.
- Never touch `~/.pip`, the system Python or an existing conda env's
  package set except the one named below. New test environments go under
  `/Users/e.bitzek/DEVEL/ovito-auto-viz/.venvs/` (gitignored — add the
  line if it is missing).
- Never set custom attributes on OVITO objects; call
  `scene.ensure_gui_app()` before constructing any overlay. Both are
  enforced by `tests/test_ovito_compat.py` — keep it green.
- Do not `git push` or create a tag before Phase 4 says so. Do not run
  `git add -A`: the working tree contains large untracked files that must
  NOT be committed (see Phase 3).
- Use absolute paths in every command. When you report, list what you ran.

## Phase 0 — orient (5 min)

1. `git -C /Users/e.bitzek/DEVEL/ovito-auto-viz status --short` and
   `git -C /Users/e.bitzek/DEVEL/ovito-auto-viz diff --stat`. Expected
   modified: `CITATION.cff README.md pyproject.toml src/ovzm/__init__.py
   src/ovzm/pipelinebuild.py src/ovzm/scene.py src/ovzm/grid.py
   src/ovzm/importer.py .github/workflows/ci.yml skills/ovito-auto-viz/SKILL.md
   CLAUDE.md`; expected new: `RELEASE-NOTES-v0.4.2.md
   tests/test_ovito_compat.py docs/TASK-ovito-3.16-compat.md`. If
   `.git/index.lock` exists and is 0 bytes, delete it (Cowork bridge
   artefact, see CLAUDE.md).
2. Read `RELEASE-NOTES-v0.4.2.md` and the diff of the four `src/ovzm/`
   files so you know what you are validating.
3. Find Erik's working env: `/Users/e.bitzek/miniforge3/envs/jupyter/bin/python -c
   "import ovito, ovzm; print(ovito.version_string, ovzm.__version__, ovzm.__file__)"`.
   Record the ovito version. If `ovzm` there is not the editable install
   of this repo (`__file__` not under the repo), reinstall it editable:
   `/Users/e.bitzek/miniforge3/envs/jupyter/bin/python -m pip install -e /Users/e.bitzek/DEVEL/ovito-auto-viz`.

## Phase 1 — validate on the Mac, three ovito versions

Erik saw the `color_coding` crash on 3.12, 3.15 and 3.16. Test all three.
Create one venv per version under the repo's `.venvs/` (Python from the
jupyter env is fine: `/Users/e.bitzek/miniforge3/envs/jupyter/bin/python -m venv …`),
install `ovito==3.12.4`, `ovito==3.15.5`, `ovito==3.16.1` respectively plus
`-e /Users/e.bitzek/DEVEL/ovito-auto-viz pytest pillow`. If a wheel is not
available for this macOS/Python combination, note it and move on with the
versions that install — do not fight pip for long.

For EACH venv, from a scratch dir (`mkdir -p /Users/e.bitzek/DEVEL/ovito-auto-viz/scratch && cd` there;
`scratch/` is gitignored — add the line if not):

1. `<venv>/bin/python -m pytest /Users/e.bitzek/DEVEL/ovito-auto-viz/tests -q`
   — expect 44 passed (`test_ovito_compat.py` contributes 4).
2. Render the try-it example and a `color_coding` card:
   ```
   <venv>/bin/python /Users/e.bitzek/DEVEL/ovito-auto-viz/examples/try-it/make_edge_dipoles.py
   cp /Users/e.bitzek/DEVEL/ovito-auto-viz/examples/try-it/edge-dipoles.yaml .
   printf 'creator: Erik Bitzek\n' > identity.yaml
   OVZM_IDENTITY=$PWD/identity.yaml <venv>/bin/ovzm render edge-dipoles.yaml -o ed-<ver>.png
   printf 'name: cc\ninput: {file: edge-dipoles.dump}\ncrystal: {x: [1,-1,0], y: [1,1,1], z: [-1,-1,2], lattice: fcc}\nview: {direction: [1,-3,9], up: [1,1,1], projection: perspective}\npipeline: [{color_coding: {property: Position.Y, map: viridis}}]\natoms: {show: all, names: {1: Ni}}\nannotate: {colorbar: {title: y, units: "Å"}}\noutput: {preset: draft}\n' > cc.yaml
   OVZM_IDENTITY=$PWD/identity.yaml <venv>/bin/ovzm render cc.yaml -o cc-<ver>.png
   ```
   Both must exit 0. `ovzm prov cc-<ver>.png` must show a `colorbars`
   entry with `map: viridis` and `start < end`.
3. Look at the PNGs (Read tool on the image). Every text overlay — the
   label block top-left, the legend title top-right, the three tripod axis
   labels — must be complete, not cut after a few characters. Compare the
   3.16 render with the 3.15 render: identical content, text ~30 % smaller
   on 3.16 is expected and acceptable.
4. `ovzm session edge-dipoles.yaml -o s-<ver>.ovito` must exit 0, and
   `<venv>/bin/ovzm import s-<ver>.ovito` must print a card whose
   `input.file` is a plain absolute path (no `file://`).

Record a table (version × {tests, render, color_coding, text OK, session,
import}) in your final report. **STOP** if any cell fails on a version that
installed: describe the failure with the traceback and the PNG, and do not
proceed to Phase 3 until Erik has answered — EXCEPT for a failure you can
fix in ≤ 30 lines without changing behaviour on the other versions; then
fix it, add a regression test, re-run the whole matrix, and say so.

## Phase 2 — optional improvements, only if Phase 1 is fully green

Do these in separate commits (Phase 3 explains commits). Skip any that
turns out to need more than ~1 h or a design decision.

1. **Sessions with overlays on ovito ≥ 3.16.1.** `runner.run_session` drops
   overlays because `ovito.scene.save()` produced corrupt files up to
   3.15.5 (verified again 2026-09-24: 3.15.5 corrupt, 3.16.1 round-trips
   cleanly — `ovito.scene.load()` afterwards lists the overlays).
   Version-gate it: `if ovito.version >= (3, 16, 1)` copy the overlays of
   the render viewport into `ovito.scene.viewports.active_vp.overlays`
   before saving and drop the stderr note; keep the old behaviour below
   that version. Test: save with the 3.16 venv, load in a fresh process,
   assert the overlay types are present; save with the 3.15 venv and
   assert the file still loads (i.e. the gate held). Update CLAUDE.md
   gotcha and README.
2. **`annotate.font_family`** (string, optional). ovito 3.16 added
   `font_family`/`font_style` to all text overlays and deprecated the
   `font` string. When the card gives a family and the overlay object
   has the attribute (`hasattr`), set it on tripod, legend, labels and the
   grid panel title; record the value in `resolved_scene`. Add to
   `src/ovzm/schema/vizcard.schema.json`, regenerate `docs/SCHEMA.md` with
   `tools/gen-schema-md.py`, add a `validate` test. Do NOT try to
   compensate the 3.15→3.16 font-size change.
3. **Discrete legend defect** (known since 0.4.0, see CLAUDE.md "Known
   cosmetic defect"): labels of the six structure types collide. This one
   changes how all figures look → **STOP** and ask Erik before touching it;
   just render one example with `orientation` vertical and attach the PNG
   to your report as a proposal.

## Phase 3 — commit

Commit in this order, each with a message body that says what and why
(imperative subject ≤ 72 chars). Add files explicitly:

1. `fix: color_coding crash (private attrs on OVITO objects) + ovito 3.16 text clipping`
   — `src/ovzm/pipelinebuild.py src/ovzm/scene.py src/ovzm/grid.py
   tests/test_ovito_compat.py`
2. `fix: ovzm import writes a plain path, not file://` — `src/ovzm/importer.py`
3. `ci/docs: Vulkan driver for ovito >= 3.16; color_coding smoke render`
   — `.github/workflows/ci.yml README.md skills/ovito-auto-viz/SKILL.md`
4. `0.4.2: release notes, version bump, handoff notes` — `pyproject.toml
   src/ovzm/__init__.py CITATION.cff RELEASE-NOTES-v0.4.2.md CLAUDE.md
   docs/TASK-ovito-3.16-compat.md .gitignore` (plus Erik's pending README
   edits from 0.4.1 if they are still in the diff — they are fine to
   include in commit 3 or 4).
5. Phase-2 items, one commit each.

NEVER add: `*.pptx`, `*.pdf`, `dump.10.40000`, `*.png` outside `docs/` and
`examples/try-it/`, the loose `*.yaml` cards in the repo root
(`overview.yaml wgb-grains.yaml wp-gb-crack-*.yaml ovzm-project.yaml` are
Erik's research cards — leave them untracked and untouched), `.claude/`,
`build/`, `scratch/`, `.venvs/`. If `git status` still shows them
untracked afterwards, that is correct.

End every commit message with the attribution lines the session gives you
(Co-Authored-By / Claude-Session), if any.

## Phase 4 — push, CI, release

1. `git -C /Users/e.bitzek/DEVEL/ovito-auto-viz push origin main`.
2. Watch CI: `gh run watch --repo biterik/ovito-auto-viz` (or
   `gh run list --repo biterik/ovito-auto-viz --limit 3` then
   `gh run view <id> --log-failed`). Both jobs (`packaging` ×2 Pythons,
   `render`) must be green. The `render` job now installs
   `mesa-vulkan-drivers` — if it fails on the apt step, check the package
   name on the runner's Ubuntu release and fix. Fix, commit, push, repeat
   until green; **STOP** after three red runs on the same failure.
3. When green: `git -C /Users/e.bitzek/DEVEL/ovito-auto-viz tag -a v0.4.2 -F /Users/e.bitzek/DEVEL/ovito-auto-viz/RELEASE-NOTES-v0.4.2.md`
   and `git push origin v0.4.2`, then
   `gh release create v0.4.2 --repo biterik/ovito-auto-viz --title "ovito-auto-viz 0.4.2" --notes-file /Users/e.bitzek/DEVEL/ovito-auto-viz/RELEASE-NOTES-v0.4.2.md`.
   Zenodo archives the release automatically (concept DOI in CITATION.cff).
4. PyPI: check whether `ovito-auto-viz` is already published
   (`python -m pip index versions ovito-auto-viz`). If it is, and a
   trusted-publishing workflow exists in `.github/workflows/`, the tag
   triggers it — verify the 0.4.2 wheel appears. If it is NOT published,
   **STOP**: report that the README's `pip install ovito-auto-viz` line
   (Erik's 0.4.1 edit) points at nothing yet and ask whether to set up
   trusted publishing (that needs his PyPI account interactively).

## Phase 5 — skill re-delivery and report

1. `skills/ovito-auto-viz/SKILL.md` changed (install line). Erik's Cowork
   account holds a separate copy that does not track the repo. Package it:
   `cd /Users/e.bitzek/DEVEL/ovito-auto-viz/skills && zip -r /Users/e.bitzek/DEVEL/ovito-auto-viz/scratch/ovito-auto-viz.skill ovito-auto-viz`
   and tell Erik to re-upload that file to his skills.
2. Final report, in this order: the Phase-1 matrix; what was committed
   (hashes); CI status and release URL; anything you STOPped on with the
   exact question; the two PNGs from 3.16 (edge-dipoles and color_coding)
   for Erik to eyeball; the skill file path. Keep it under a screen.
