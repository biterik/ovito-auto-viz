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
"""v0.4.3 card keys and semantic checks -- schema level, ovito-free.

ptm.structures, view.fov, annotate.tripod_font_size / tripod_outline, the
PTM-before-DXA conflict (DXA overwrites 'Structure Type') and the warning
for a dxa figure without a crystal frame. Deliberately ovito-free so it
runs in the packaging CI job.
"""
import pytest

from ovzm.card import card_warnings, load_card, semantic_problems


def write(tmp_path, text, name="c.yaml"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


BASE = "name: t\ninput: {file: x.dump}\n"
CRYSTAL = "crystal: {x: [1,0,0], y: [0,1,0], z: [0,0,1], lattice: fcc}\n"


# --- schema: the new keys are accepted, bad values rejected -----------------

def test_new_keys_validate(tmp_path):
    card = load_card(write(tmp_path, BASE + CRYSTAL +
                           "view: {fov: 40.5}\n"
                           "pipeline: [{ptm: {structures: [ico, sc]}}]\n"
                           "annotate: {tripod_font_size: 0.7, tripod_outline: false}\n"))
    assert card["view"]["fov"] == 40.5


@pytest.mark.parametrize("bad, where", [
    ("view: {fov: 0}\n", "fov"),
    ("view: {fov: -3}\n", "fov"),
    ("pipeline: [{ptm: {structures: [icosahedral]}}]\n", "structures"),
    ("annotate: {tripod_font_size: 0}\n", "tripod_font_size"),
    ("atoms: {structure_colors: {icosa: [1, 0, 0]}}\n", "structure_colors"),
])
def test_bad_values_are_rejected(tmp_path, bad, where):
    with pytest.raises(ValueError) as exc:
        load_card(write(tmp_path, BASE + bad))
    assert where in str(exc.value)


# --- PTM before DXA ---------------------------------------------------------

def test_ptm_only_type_with_dxa_last_is_refused(tmp_path):
    with pytest.raises(ValueError) as exc:
        load_card(write(tmp_path, BASE + CRYSTAL +
                        "pipeline: [{ptm: {structures: [ico]}}, {dxa: {lattice: fcc}}]\n"))
    msg = str(exc.value)
    assert "dxa" in msg and "ico" in msg and "FIRST" in msg


def test_structure_color_dxa_cannot_produce_is_refused_via_preset(tmp_path):
    """dxa-standard runs ptm then dxa; asking for an ico colour on top of it
    used to render silently without the colour (2026-11-21)."""
    with pytest.raises(ValueError) as exc:
        load_card(write(tmp_path, "name: t\nextends: dxa-standard\n"
                        "input: {file: x.dump}\n"
                        "atoms: {structure_colors: {ico: [1, 0, 0]}}\n"))
    assert "ico" in str(exc.value)


def test_dxa_first_is_accepted(tmp_path):
    card = load_card(write(tmp_path, BASE + CRYSTAL +
                           "pipeline: [{dxa: {lattice: fcc}}, {ptm: {structures: [ico]}}]\n"
                           "atoms: {structure_colors: {ico: [1, 0, 0]}}\n"))
    assert semantic_problems(card)[0] == []


def test_types_dxa_also_reports_are_fine_after_ptm(tmp_path):
    """fcc/hcp colours on dxa-standard keep working (DXA reports them too)."""
    card = load_card(write(tmp_path, "name: t\nextends: dxa-standard\n"
                           "input: {file: x.dump}\n"
                           "atoms: {structure_colors: {hcp: [1, 0, 0]}}\n"))
    assert semantic_problems(card)[0] == []


# --- view.fov needs an orthographic camera ----------------------------------

def test_fov_with_perspective_is_refused(tmp_path):
    with pytest.raises(ValueError) as exc:
        load_card(write(tmp_path, BASE + "view: {fov: 30, projection: perspective}\n"))
    assert "view.fov" in str(exc.value)


# --- dxa without a crystal frame: warning, not error ------------------------

def test_dxa_without_crystal_block_warns(tmp_path):
    card = load_card(write(tmp_path, BASE + "pipeline: [{dxa: {lattice: fcc}}]\n"))
    errors, warnings = semantic_problems(card)
    assert errors == []
    assert any("crystal" in w and "LH/SF" in w for w in warnings)


def test_dxa_with_unresolved_auto_orientation_warns_at_run_time(tmp_path):
    card = load_card(write(tmp_path, "name: t\nextends: dxa-standard\n"
                           "input: {file: x.dump}\n"))
    assert semantic_problems(card)[1] == []          # crystal block present
    warns = card_warnings(card, orientation=None)    # but auto found nothing
    assert any("could not be resolved" in w for w in warns)


def test_no_warning_without_dxa(tmp_path):
    card = load_card(write(tmp_path, BASE + "pipeline: [{ptm: {}}]\n"))
    assert card_warnings(card, orientation=None) == []
