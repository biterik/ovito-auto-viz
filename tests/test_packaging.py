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
"""Regression tests for the 0.3.1 packaging bug.

In 0.3.1 `presets/` and `schema/` lived at the repo root and were NOT declared
as package data, so `pip install ovito-auto-viz` produced a CLI where
`extends:` could not be resolved and `ovzm schema` printed `null` — silently,
because validate() treated a missing schema as "nothing to complain about".

These tests must pass against an INSTALLED wheel with the source tree absent;
running them from the repo root would mask the bug via the cwd/REPO_ROOT
fallbacks, so the CI job runs pytest from a scratch directory.
"""
from pathlib import Path

import pytest

import ovzm
from ovzm import card as card_mod

PKG_DIR = Path(ovzm.__file__).resolve().parent
PRESETS = ("dxa-standard", "segregation-map")


def test_schema_ships_inside_the_package():
    assert (PKG_DIR / "schema" / "vizcard.schema.json").is_file(), (
        "the card schema is not installed as package data — a wheel built from "
        "this tree would ship a CLI that cannot validate anything"
    )


@pytest.mark.parametrize("name", PRESETS)
def test_preset_ships_inside_the_package(name):
    assert (PKG_DIR / "presets" / f"{name}.yaml").is_file(), (
        f"preset {name!r} is not installed as package data"
    )


def test_load_schema_returns_a_real_schema():
    schema = card_mod.load_schema()
    assert isinstance(schema, dict) and schema, "load_schema() must not return None/{}"
    assert "properties" in schema
    assert "name" in schema["properties"]


@pytest.mark.parametrize("name", PRESETS)
def test_preset_resolves_by_name(name):
    assert card_mod.find_preset(name).is_file()


def test_card_with_extends_loads_and_validates(tmp_path):
    cardfile = tmp_path / "t.yaml"
    cardfile.write_text(
        "name: packaging-smoke\n"
        "extends: dxa-standard\n"
        "input:\n"
        "  file: nonexistent.dump\n"
        "meta:\n"
        "  creator: CI\n"
    )
    merged = card_mod.load_card(cardfile)
    assert merged["name"] == "packaging-smoke"
    assert "extends" not in merged, "the extends chain must be resolved away"


def test_missing_schema_raises_instead_of_validating_nothing(monkeypatch):
    """The heart of the bug: no schema must be an error, never a silent pass."""
    monkeypatch.setattr(card_mod, "_SCHEMA_CACHE", None)
    monkeypatch.setattr(card_mod, "_schema_search_paths",
                        lambda: (Path("/nonexistent/vizcard.schema.json"),))
    with pytest.raises(card_mod.SchemaUnavailableError):
        card_mod.load_schema()
    monkeypatch.setattr(card_mod, "_SCHEMA_CACHE", None)
    with pytest.raises(card_mod.SchemaUnavailableError):
        card_mod.validate({"name": "x"})


def test_invalid_card_is_actually_rejected(tmp_path):
    """Guards against a validator that passes everything."""
    cardfile = tmp_path / "bad.yaml"
    cardfile.write_text(
        "name: bad\n"
        "input:\n"
        "  file: nonexistent.dump\n"
        "view:\n"
        "  direction: not-a-real-direction-value-!!\n"
    )
    with pytest.raises(ValueError):
        card_mod.load_card(cardfile)


def test_version_is_exposed():
    assert ovzm.__version__
