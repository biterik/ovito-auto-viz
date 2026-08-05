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
"""Viz-card loading: YAML parsing, preset inheritance (extends), validation."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import yaml

try:
    import jsonschema
except ImportError:  # validation becomes a no-op; runner still works
    jsonschema = None

PKG_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PKG_ROOT.parent.parent  # src/ovzm -> repo root (editable install / checkout)

# Presets and the card schema are PACKAGE DATA: they live inside src/ovzm/ so
# that they ship in the wheel. Before 0.3.2 they sat at the repo root, which
# meant a non-editable install silently had neither. Keep the legacy locations
# in the search order so old checkouts keep working.
PRESET_DIR = PKG_ROOT / "presets"
SCHEMA_PATH = PKG_ROOT / "schema" / "vizcard.schema.json"

_SCHEMA_CACHE = None


class SchemaUnavailableError(RuntimeError):
    """The bundled card schema could not be loaded — the install is broken.

    Raised rather than silently skipping validation: a no-op validator that
    reports success is worse than no validator at all.
    """


def _preset_search_paths():
    """Where `extends: <name>` is resolved. First hit wins."""
    paths = []
    if os.environ.get("OVZM_PRESET_PATH"):
        paths += [Path(p) for p in os.environ["OVZM_PRESET_PATH"].split(":") if p]
    paths.append(Path.cwd() / "presets")
    paths.append(REPO_ROOT / "presets")  # legacy repo-root layout (pre-0.3.2)
    paths.append(PRESET_DIR)             # shipped with the package
    return paths


def find_preset(name: str) -> Path:
    """Resolve a preset reference: explicit path, or <name>[.yaml] on the search path."""
    p = Path(name)
    if p.suffix in (".yaml", ".yml") and p.exists():
        return p
    for base in _preset_search_paths():
        for cand in (base / f"{name}.yaml", base / f"{name}.yml", base / name):
            if cand.is_file():
                return cand
    raise FileNotFoundError(
        f"preset '{name}' not found (searched: "
        + ", ".join(str(b) for b in _preset_search_paths()) + ")"
    )


def deep_merge(base: dict, override: dict) -> dict:
    """Recursive dict merge; override wins. Lists are replaced, not appended."""
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _schema_search_paths():
    return (
        SCHEMA_PATH,                                        # shipped with the package
        REPO_ROOT / "schema" / "vizcard.schema.json",        # legacy repo-root layout
        PKG_ROOT / "vizcard.schema.json",                    # legacy flat copy
    )


def load_schema() -> dict:
    """Load the bundled viz-card JSON schema.

    Raises SchemaUnavailableError if it cannot be found anywhere — that means
    the package data did not get installed, and every card would otherwise
    "validate" successfully against nothing.
    """
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        for cand in _schema_search_paths():
            if cand.is_file():
                _SCHEMA_CACHE = json.loads(cand.read_text())
                break
        else:
            raise SchemaUnavailableError(
                "the viz-card schema is missing from this ovito-auto-viz "
                "install (searched: "
                + ", ".join(str(p) for p in _schema_search_paths())
                + "). The package data was not installed correctly — reinstall "
                "with 'pip install ovito-auto-viz', or from a checkout with "
                "'pip install -e <repo>'."
            )
    return _SCHEMA_CACHE


def validate(card: dict) -> list[str]:
    """Return a list of human-readable validation problems (empty = ok)."""
    schema = load_schema()  # raises SchemaUnavailableError on a broken install
    if jsonschema is None:
        raise SchemaUnavailableError(
            "the 'jsonschema' package is required to validate viz cards but is "
            "not importable; it is a declared dependency, so this install is "
            "incomplete — reinstall ovito-auto-viz."
        )
    validator = jsonschema.Draft202012Validator(schema)
    problems = []
    for err in sorted(validator.iter_errors(card), key=lambda e: list(e.absolute_path)):
        loc = ".".join(str(x) for x in err.absolute_path) or "<root>"
        problems.append(f"{loc}: {err.message}")
    return problems


def load_card(path: str | Path, *, do_validate: bool = True) -> dict:
    """Load a viz card, resolving the `extends:` chain (deepest ancestor first)."""
    path = Path(path)
    card = yaml.safe_load(path.read_text()) or {}
    chain = [card]
    seen = {str(path.resolve())}
    cur = card
    while cur.get("extends"):
        ppath = find_preset(cur["extends"])
        key = str(ppath.resolve())
        if key in seen:
            raise ValueError(f"circular 'extends' chain at {ppath}")
        seen.add(key)
        cur = yaml.safe_load(ppath.read_text()) or {}
        chain.append(cur)
    merged: dict = {}
    for layer in reversed(chain):  # ancestors first, card last
        merged = deep_merge(merged, layer)
    merged.pop("extends", None)
    merged.setdefault("_card_dir", str(path.resolve().parent))
    if do_validate:
        problems = validate({k: v for k, v in merged.items() if not k.startswith("_")})
        if problems:
            msg = "\n  ".join(problems)
            raise ValueError(f"viz card failed validation:\n  {msg}")
    return merged
