#!/usr/bin/env python3
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
"""Generate docs/SCHEMA.md from schema/vizcard.schema.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
schema = json.loads((ROOT / "schema" / "vizcard.schema.json").read_text())


def typestr(node):
    if "$ref" in node:
        return node["$ref"].split("/")[-1]
    if "enum" in node:
        return " | ".join(f"`{v}`" for v in node["enum"])
    if "const" in node:
        return f"`{node['const']}`"
    if "anyOf" in node:
        return " or ".join(typestr(n) for n in node["anyOf"])
    t = node.get("type", "any")
    if t == "array":
        return f"array of {typestr(node.get('items', {}))}"
    return t


def walk(props, prefix, lines):
    for key, node in props.items():
        if key.startswith("_"):
            continue
        path = f"{prefix}{key}"
        desc = node.get("description", "")
        lines.append(f"| `{path}` | {typestr(node)} | {desc} |")
        if node.get("type") == "object" and "properties" in node:
            walk(node["properties"], path + ".", lines)


lines = [
    "# Viz-card schema reference",
    "",
    "Generated from `schema/vizcard.schema.json` — do not edit by hand;",
    "run `python tools/gen-schema-md.py` after changing the schema.",
    "",
    "| key | type | description |",
    "|-----|------|-------------|",
]
walk(schema["properties"], "", lines)

lines += [
    "",
    "## Pipeline steps",
    "",
    "Entries in `pipeline:` are either bare names (`wrap`, `delete_selected`)",
    "or single-key mappings `{name: {params}}`:",
    "",
    "| step | params |",
    "|------|--------|",
]
for item in schema["properties"]["pipeline"]["items"]["anyOf"]:
    if item.get("type") == "object":
        for name, sub in item["properties"].items():
            params = ", ".join(f"`{k}`" for k in sub.get("properties", {})) or "—"
            lines.append(f"| `{name}` | {params} |")

lines += [
    "",
    "## Definitions",
    "",
    "- `miller` — a 3-vector of numbers, interpreted as a cubic Miller",
    "  direction (crystal frame) or a sim-frame vector depending on context.",
    "- `corner` — `top_left`, `top_right`, `bottom_left`, `bottom_right`.",
    "",
]
out = ROOT / "docs" / "SCHEMA.md"
out.write_text("\n".join(lines))
print(f"wrote {out}")
