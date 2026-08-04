# Viz-card schema reference

Generated from `schema/vizcard.schema.json` — do not edit by hand;
run `python tools/gen-schema-md.py` after changing the schema.

| key | type | description |
|-----|------|-------------|
| `name` | string | Short card name; used in auto-generated output file names. |
| `extends` | string | Preset to inherit from (name on the preset search path, or a path to a YAML file). Chains are allowed. |
| `warnings` | array of string | Emitted by `ovzm import`; informational only. |
| `input` | object |  |
| `input.file` | string | LAMMPS dump/data file, .gz supported. Globs allowed; multiple matches are treated as trajectory frames. |
| `input.frames` | `all` | `last` | `first` or integer or array of integer | Frame selection: 'all', 'last', an index, or [start, stop, step]. |
| `crystal` | object | Crystallographic orientation of the simulation frame. Give x plus y or z (cubic Miller triplets), or 'auto' to parse the x-101_y1-21_z111 filename convention. |
| `crystal.x` | `auto` or miller |  |
| `crystal.y` | miller |  |
| `crystal.z` | miller |  |
| `crystal.lattice` | `fcc` | `bcc` | `hcp` | `diamond` |  |
| `view` | object |  |
| `view.direction` | `top` | `bottom` | `front` | `back` | `left` | `right` or miller | Named view (sim frame) or Miller direction (crystal frame; camera looks at the structure from that side). |
| `view.up` | miller | Optional up direction (crystal frame for Miller views). |
| `view.projection` | `ortho` | `perspective` |  |
| `view.zoom` | `fit` or number | 'fit' (default) or a magnification factor relative to fit. |
| `view.direction_sim_frame` | array of number | Raw sim-frame camera direction (written by `ovzm import`). |
| `view.fit_margin` | number | Enlarge the field of view beyond tight fit so overlays (tripod, labels, colorbar) land outside the projected cell. Default 1.15. |
| `atoms` | object |  |
| `atoms.radius` | number or object | Uniform radius in Å, or a map of type id/name -> radius. |
| `atoms.colors` | object | Map of type id/name -> RGB in [0,1]. |
| `atoms.show` | string | 'all', 'non_fcc', 'non_bcc', 'defects_only', or a raw OVITO boolean expression selecting the atoms to KEEP. |
| `atoms.names` | object | Map of type id -> species name (e.g. {1: Ni, 2: Cu}); used in labels and legends. |
| `atoms.color_by` | `type` | `structure` | 'structure' = PTM/CNA structure colors (default); 'type' = per-type colors (default when atoms.colors is given). |
| `pipeline` | array of `wrap` | `delete_selected` or object | Ordered analysis steps. Each entry is a bare name or {name: {params}}. |
| `annotate` | object |  |
| `annotate.tripod` | `miller` | `xyz` | `off` | 'miller' labels axes with crystal directions (needs crystal orientation). |
| `annotate.tripod_corner` | corner |  |
| `annotate.tripod_size` | number |  |
| `annotate.colorbar` | boolean or object | true/false, or {title, units, corner, font_size, format}. |
| `annotate.labels` | `auto` | `off` | 'auto' composes step, composition, and DXA results (b, ξ, character, lengths) from the data itself — no metadata required. |
| `annotate.labels_corner` | corner |  |
| `annotate.labels_font_size` | number |  |
| `annotate.labels_color` | array of number |  |
| `annotate.extra` | string or array of string | Extra caption line(s) appended verbatim. |
| `annotate.dxa_line_width` | number | Dislocation line width in Å (default 2.0). |
| `tripods` | object | Per-grain tripods for polycrystals (roadmap: rendered via a custom viewport overlay). |
| `tripods.mode` | `global` | `per_grain` |  |
| `tripods.source` | string | 'auto' (grain segmentation) or a grains file: space-separated columns id cx cy cz + orientation (quaternion or two Miller axes). |
| `tripods.labels` | `miller` | `off` |  |
| `output` | object |  |
| `output.preset` | `draft` | `slide` | `paper` | draft=1280x720 fast; slide=1920x1080; paper=3200x2400 with ambient occlusion. |
| `output.width` | integer |  |
| `output.height` | integer |  |
| `output.renderer` | `opengl` | `tachyon-fast` | `tachyon` | `tachyon-ao` | `ospray` |  |
| `output.background` | string | 'white', 'black', or 'transparent'. |
| `output.file` | string | 'auto' derives <input>__<cardname>.png next to the cwd. |
| `output.movie` | boolean | Force movie output for multi-frame inputs. |
| `output.fps` | integer |  |
| `output.tag` | string | Optional variant tag appended to the figure ID: <input-stem>__<card-name>__<tag>. |
| `grid` | object | Comparison-grid mode (ovzm grid): render this card over several inputs with identical camera, scale, styling, and colorbar limits. |
| `grid.inputs` | array of string | Input files (globs allowed); each becomes one panel. |
| `grid.labels` | array of string | Panel titles; defaults to the input file stems. |
| `grid.cols` | integer | Grid columns (default: 2 for <=4 panels, else 3). |
| `grid.tripod` | `first` | `all` | Draw tripod+legend on the first panel only (default) or on every panel. |
| `meta` | object | Figure attribution, recorded in the provenance (sidecar + embedded PNG). Resolved per key: card > ovzm-project.yaml (found by walking up from the card / input data, git-config style) > ~/.config/ovzm/identity.yaml. creator is MANDATORY; everything else may stay empty. |
| `meta.creator` | string | Person creating this figure. Required (card, project file, identity file, or --ask). |
| `meta.project` | string | Related project (optional; usually from ovzm-project.yaml). |
| `meta.funding` | string | Funding acknowledgment (optional; usually from ovzm-project.yaml). |
| `meta.affiliation` | string | Creator's affiliation FOR THIS PROJECT (optional; project file or its people: map). |
| `meta.email` | string | Optional contact email. |
| `meta.orcid` | string | Optional ORCID iD. |

## Pipeline steps

Entries in `pipeline:` are either bare names (`wrap`, `delete_selected`)
or single-key mappings `{name: {params}}`:

| step | params |
|------|--------|
| `ptm` | `rmsd_cutoff`, `orientations` |
| `cna` | `cutoff` |
| `dxa` | `lattice`, `circuit_length`, `only_perfect`, `line_smoothing` |
| `grain_segmentation` | `merge_threshold` |
| `color_coding` | `property`, `range`, `map` |
| `slice` | `normal`, `distance`, `width`, `inverse` |
| `select_type` | `property`, `types` |
| `select_expression` | `expr` |

## Definitions

- `miller` — a 3-vector of numbers, interpreted as a cubic Miller
  direction (crystal frame) or a sim-frame vector depending on context.
- `corner` — `top_left`, `top_right`, `bottom_left`, `bottom_right`.
