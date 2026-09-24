Compatibility release: ovzm now works with the current `ovito` module
(3.16.x, new rendering engine) and again with every version since 3.12.

## Fixes

- **`color_coding` crashed on every OVITO version** (3.12 … 3.16) with
  `AttributeError: 'ColorCodingModifier' object has no attribute
  '_ovzm_auto_range'`. ovzm attached private bookkeeping (auto-range flag,
  color-map name) to the OVITO modifier object; OVITO's pybind11 objects have
  no `__dict__` and refuse custom attributes. The facts now live in an
  ovzm-side table (`pipelinebuild.set_meta/get_meta`). A source lint in the
  test suite (`tests/test_ovito_compat.py`) rejects any future
  `<ovito object>._private = …`, and CI renders a `color_coding` card — the
  path had never been exercised by CI, which is how the bug shipped.
- **ovito ≥ 3.16 clipped every overlay text** (label block, legend title,
  tripod axis labels cut after a few characters). Cause: an overlay created
  before a `QGuiApplication` exists gets a font with an empty family and is
  measured with one font but drawn with another. `scene.ensure_gui_app()`
  now runs before every overlay constructor (render, grid, grain tripods).
  Verified by rendering on 3.15.5 and 3.16.1; a regression test compares
  the ink width of a long label against its short prefix.
- **Unknown `color_coding.map` names fail loudly** instead of silently
  rendering the default gradient while the provenance claimed the requested
  map. `plasma` was listed but has never existed in OVITO — removed;
  `cyclic-rainbow` added. Raw OVITO class names (`Viridis`, …) still work.
- `ovzm import` wrote `input.file: file:///abs/path` (a URL, unusable as a
  card input); now a plain path.
- **ovito 3.12.x resets the C locale to "C" on import** (verified 3.12.4 on
  macOS), so every later `read_text()`/`open()` without an explicit encoding
  decoded as US-ASCII and any card containing an "Å" aborted with
  `UnicodeDecodeError`. All text I/O in ovzm now names `utf-8`; a source lint
  in `tests/test_ovito_compat.py` keeps it that way.
- The physics test looked for `ovzm` on `PATH`; it now uses the console
  script next to the running interpreter (unactivated venvs work).

## New

- **`ovzm session` embeds the overlays on ovito ≥ 3.16.1** (tripod, label
  block, colorbar/legend, grain tripods). Older modules corrupt the `.ovito`
  file when overlays are in the scene, so there the previous behaviour
  (skip + stderr note) is kept. The provenance records which case applied
  (`resolved_scene.session_overlays`).

## OVITO 3.16 notes (verified 2026-09-24 on 3.16.1)

- The Linux module renders through Vulkan. Headless machines additionally
  need a Vulkan driver: `mesa-vulkan-drivers` (lavapipe) on Debian/Ubuntu.
  README, CI and the agent skill are updated; without it `ovzm render`
  aborts with "Could not initialize the Vulkan graphics backend".
- Same `font_size` renders ~30 % smaller than on 3.15 — OVITO's own change
  in font metrics; card values were not adjusted.
- `ovito.scene.save()` with overlays in the scene, which produced corrupt
  session files up to 3.15.5, round-trips correctly on 3.16.1 — hence the
  version-gated session overlays above.
- `OpenGLRenderer` is now an alias of `StandardRenderer`; the renderer
  `outlines_*` parameters were removed (ovzm never used them).
- **macOS arm64 wheel bug in ovito 3.16.1** (verified 2026-09-24, Python
  3.12): `import ovito` fails with `Library not loaded:
  @loader_path/libospray.3.2.0.dylib`. The wheel ships the library only as
  `libospray.3.dylib` (the name 3.15.5 linked against). Workaround until an
  upstream fix:
  `ln -s libospray.3.dylib <site-packages>/ovito/plugins/libospray.3.2.0.dylib`.
  Nothing ovzm can do about it; the validation matrix below used that link.

## Validated

`python -m pytest tests` (45 tests), `ovzm render` (try-it example and a
`color_coding` card), `ovzm session` and `ovzm import` on macOS arm64
(Python 3.12) with ovito 3.12.4, 3.15.5 and 3.16.1 (the latter with the
symlink above), and on Linux x86_64 with 3.15.5 and 3.16.1.

## Citation

Concept DOI: 10.5281/zenodo.21796154 (Zenodo archives this release
automatically). Please cite via the repository's "Cite this repository"
button (CITATION.cff).
