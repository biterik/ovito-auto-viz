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
"""Unit tests for the per-grain tripods (grains: block) — v0.4.0.

Deliberately ovito-free: ovzm.grains must stay importable without the ovito
module so `ovzm validate` and these tests run in the packaging CI job.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from ovzm.grains import (GrainsError, axis_label, finalize_grains,
                         grains_prov, resolve_grains)

TESTS_DIR = Path(__file__).resolve().parent

G1 = {"origin": [1.0, 2.0, 3.0], "x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}
G2 = {"origin": [4.0, 5.0, 6.0], "x": [4, -3, 0], "y": [3, 4, 0], "z": [0, 0, 1]}


def card_inline(items, tripod=None, card_dir="."):
    block = {"items": items}
    if tripod is not None:
        block["tripod"] = tripod
    return {"grains": block, "_card_dir": card_dir}


# ---------------------------------------------------------------------------
# parsing: inline, file, XOR


def test_no_grains_block_resolves_to_none():
    assert resolve_grains({"name": "x"}) is None


def test_inline_two_grains_box_mode():
    r = resolve_grains(card_inline([dict(G1), dict(G2)]))
    assert [g["name"] for g in r["grains"]] == ["g1", "g2"]
    assert r["source"] == "inline"
    assert r["file_sha256"] is None
    for g in r["grains"]:
        assert g["arm_mode"] == "box"
        dirs = [a["direction_sim"] for a in g["arms"]]
        assert np.allclose(dirs, np.eye(3)), \
            "box mode arms must point along the sim-box axes"
    assert [a["label"] for a in r["grains"][1]["arms"]] == \
        ["[4-30]", "[340]", "[001]"]


def test_grains_file_is_parsed_and_hashed(tmp_path):
    gfile = tmp_path / "grains.yaml"
    gfile.write_text(
        "grains:\n"
        "  - name: upper\n    origin: [1, 2, 3]\n"
        "    x: [1, 0, 0]\n    y: [0, 1, 0]\n    z: [0, 0, 1]\n")
    card = {"grains": {"file": "grains.yaml"}, "_card_dir": str(tmp_path)}
    r = resolve_grains(card)
    assert r["source"] == str(gfile.resolve())
    assert r["file_sha256"] == hashlib.sha256(gfile.read_bytes()).hexdigest()
    assert r["grains"][0]["name"] == "upper"


def test_file_xor_items_both_is_a_hard_error(tmp_path):
    gfile = tmp_path / "g.yaml"
    gfile.write_text("grains: []\n")
    card = {"grains": {"file": "g.yaml", "items": [dict(G1)]},
            "_card_dir": str(tmp_path)}
    with pytest.raises(GrainsError, match="exactly ONE"):
        resolve_grains(card)


def test_file_xor_items_neither_is_a_hard_error():
    with pytest.raises(GrainsError, match="exactly ONE"):
        resolve_grains({"grains": {"tripod": {"size": 20}}})


def test_missing_grains_file_names_the_resolved_path(tmp_path):
    card = {"grains": {"file": "nope.yaml"}, "_card_dir": str(tmp_path)}
    with pytest.raises(GrainsError, match=str(tmp_path)):
        resolve_grains(card)


def test_unparseable_grains_file_is_a_hard_error(tmp_path):
    (tmp_path / "bad.yaml").write_text("grains: [unclosed\n  - {")
    card = {"grains": {"file": "bad.yaml"}, "_card_dir": str(tmp_path)}
    with pytest.raises(GrainsError, match="not valid YAML"):
        resolve_grains(card)


def test_grains_file_without_grains_list_is_a_hard_error(tmp_path):
    (tmp_path / "flat.yaml").write_text("- origin: [0, 0, 0]\n")
    card = {"grains": {"file": "flat.yaml"}, "_card_dir": str(tmp_path)}
    with pytest.raises(GrainsError, match="top-level"):
        resolve_grains(card)


# ---------------------------------------------------------------------------
# per-grain validation


@pytest.mark.parametrize("missing", ["origin", "x", "y", "z"])
def test_missing_required_key_names_the_grain(missing):
    g = dict(G1, name="upper")
    del g[missing]
    with pytest.raises(GrainsError, match=f"grain 'upper'.*'{missing}'"):
        resolve_grains(card_inline([g]))


def test_non_orthogonal_triad_reuses_crystal_error_naming_the_grain():
    g = dict(G1, name="upper", y=[1, 1, 0])
    with pytest.raises(GrainsError, match="grain 'upper'.*orthogonal"):
        resolve_grains(card_inline([g]))


def test_left_handed_triad_is_rejected():
    g = dict(G1, z=[0, 0, -1])
    with pytest.raises(GrainsError, match="left-handed"):
        resolve_grains(card_inline([g]))


def test_duplicate_names_are_a_hard_error():
    with pytest.raises(GrainsError, match="duplicate.*'upper'"):
        resolve_grains(card_inline([dict(G1, name="upper"),
                                    dict(G2, name="upper")]))


def test_auto_naming_fills_gaps_positionally():
    r = resolve_grains(card_inline([dict(G1, name="upper"), dict(G2)]))
    assert [g["name"] for g in r["grains"]] == ["upper", "g2"]


def test_float_orientations_are_accepted():
    g = {"origin": [0, 0, 0], "x": [0.8, -0.6, 0.0], "y": [0.6, 0.8, 0.0],
         "z": [0.0, 0.0, 1.0]}
    r = resolve_grains(card_inline([g]))
    assert [a["label"] for a in r["grains"][0]["arms"]] == \
        ["[0.8 -0.6 0]", "[0.6 0.8 0]", "[001]"]


# ---------------------------------------------------------------------------
# the analytic arm-direction test (locks in the crystal.py convention)


def test_arm_direction_for_grain_rotated_90deg_about_z():
    """Convention lock: `x:` is the crystal direction lying along sim x.
    For a grain whose box-x axis is crystal [0,-1,0] (crystal rotated +90
    deg about z), the crystal [100] arm must come out along sim +y."""
    g = {"origin": [0, 0, 0], "x": [0, -1, 0], "y": [1, 0, 0], "z": [0, 0, 1]}
    r = resolve_grains(card_inline(
        [g], tripod={"axes": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}))
    dirs = [a["direction_sim"] for a in r["grains"][0]["arms"]]
    assert np.allclose(dirs[0], [0, 1, 0]), "crystal [100] -> sim +y"
    assert np.allclose(dirs[1], [-1, 0, 0]), "crystal [010] -> sim -x"
    assert np.allclose(dirs[2], [0, 0, 1]), "crystal [001] -> sim +z"


def test_arm_direction_sigma5_grain():
    r = resolve_grains(card_inline(
        [dict(G2)], tripod={"axes": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}))
    dirs = [a["direction_sim"] for a in r["grains"][0]["arms"]]
    assert np.allclose(dirs[0], [0.8, 0.6, 0])   # cos 36.87, sin 36.87
    assert np.allclose(dirs[1], [-0.6, 0.8, 0])
    assert np.allclose(dirs[2], [0, 0, 1])


def test_per_grain_axes_overrides_the_global_default():
    r = resolve_grains(card_inline(
        [dict(G1, axes=[[1, 1, 0], [-1, 1, 0], [0, 0, 1]]), dict(G2)],
        tripod={"axes": "box"}))
    g1, g2 = r["grains"]
    assert g1["arm_mode"] == "axes"
    assert np.allclose(g1["arms"][0]["direction_sim"],
                       np.array([1, 1, 0]) / np.sqrt(2))
    assert g1["arms"][0]["label"] == "[110]"
    assert g2["arm_mode"] == "box"


# ---------------------------------------------------------------------------
# label formatting


def test_axis_label_integer_triplets_use_miller_formatting():
    assert axis_label([4, -3, 0]) == "[4-30]"
    assert axis_label([2, 0, 0]) == "[100]"   # smallest-int reduction
    assert axis_label([1, -2, 1]) == "[1-21]"


def test_axis_label_float_triplets_as_given_max_3_decimals():
    assert axis_label([0.577, 0.577, 0.577]) == "[0.577 0.577 0.577]"
    assert axis_label([0.5, 0.0, 0.25]) == "[0.5 0 0.25]"
    assert axis_label([0.8, -0.6, 0.0]) == "[0.8 -0.6 0]"


# ---------------------------------------------------------------------------
# finalize: default size + origin-in-box warning


CELL = [[100.0, 0, 0, 0], [0, 50.0, 0, 0], [0, 0, 50.0, 0]]


def test_default_size_is_5pct_of_largest_edge_min_10A():
    r = resolve_grains(card_inline([dict(G1)]))
    finalize_grains(r, CELL)
    assert r["tripod"]["size"] == pytest.approx(10.0)  # 5% of 100 -> min 10
    r = resolve_grains(card_inline([dict(G1)]))
    finalize_grains(r, [[400.0, 0, 0, 0], [0, 50.0, 0, 0], [0, 0, 50.0, 0]])
    assert r["tripod"]["size"] == pytest.approx(20.0)


def test_explicit_size_is_kept():
    r = resolve_grains(card_inline([dict(G1)], tripod={"size": 33.0}))
    finalize_grains(r, CELL)
    assert r["tripod"]["size"] == pytest.approx(33.0)


def test_origin_outside_box_warns_but_is_kept(capsys):
    g = dict(G1, name="runaway", origin=[150.0, 25.0, 25.0])
    r = resolve_grains(card_inline([g, dict(G2, origin=[50.0, 25.0, 25.0])]))
    finalize_grains(r, CELL)
    err = capsys.readouterr().err
    assert "runaway" in err and "outside" in err
    assert len(r["grains"]) == 2, "outside origin must still be drawn"
    r2 = resolve_grains(card_inline([dict(G1, origin=[50.0, 25.0, 25.0])]))
    finalize_grains(r2, CELL)
    assert "outside" not in capsys.readouterr().err


def test_invalid_size_is_rejected():
    with pytest.raises(GrainsError, match="size"):
        resolve_grains(card_inline([dict(G1)], tripod={"size": -5}))


# ---------------------------------------------------------------------------
# provenance block


def test_grains_prov_is_reconstructible_and_yaml_safe(tmp_path):
    import yaml
    gfile = tmp_path / "grains.yaml"
    gfile.write_text(
        "grains:\n"
        "  - name: upper\n    origin: [1, 2, 3]\n"
        "    x: [4, -3, 0]\n    y: [3, 4, 0]\n    z: [0, 0, 1]\n")
    card = {"grains": {"file": "grains.yaml",
                       "tripod": {"show_names": True}},
            "_card_dir": str(tmp_path)}
    r = finalize_grains(resolve_grains(card), CELL)
    prov = grains_prov(r)
    assert prov["source"] == str(gfile.resolve())
    assert prov["file_sha256"] == hashlib.sha256(
        gfile.read_bytes()).hexdigest()
    assert prov["tripod"] == {"size_A": 10.0, "show_names": True}
    (g,) = prov["grains"]
    assert g["name"] == "upper" and g["arm_mode"] == "box"
    assert [a["label"] for a in g["arms"]] == ["[4-30]", "[340]", "[001]"]
    # must round-trip through YAML without python-specific tags
    assert "!!" not in yaml.safe_dump(prov)


# ---------------------------------------------------------------------------
# schema round-trip (jsonschema is a declared dependency)


def test_schema_accepts_a_grains_card_and_rejects_a_grain_without_origin():
    from ovzm import card as card_mod
    ok = {"name": "t", "input": {"file": "x.dump"},
          "grains": {"items": [dict(G1)],
                     "tripod": {"size": 20, "axes": "box",
                                "show_names": True}}}
    assert card_mod.validate(ok) == []
    bad = {"name": "t", "input": {"file": "x.dump"},
           "grains": {"items": [{"x": [1, 0, 0], "y": [0, 1, 0],
                                 "z": [0, 0, 1]}]}}
    assert any("origin" in p for p in card_mod.validate(bad))


# ---------------------------------------------------------------------------
# the bicrystal fixture generator


def test_make_bicrystal_fixture_round_trips(tmp_path):
    data = tmp_path / "bicrystal.data"
    gyaml = tmp_path / "bicrystal-grains.yaml"
    subprocess.run(
        [sys.executable, str(TESTS_DIR / "make_bicrystal.py"),
         str(data), str(gyaml)],
        check=True, capture_output=True)
    n_atoms = int(data.read_text().split(" atoms")[0].rsplit("\n", 1)[-1])
    assert 10_000 <= n_atoms <= 40_000
    card = {"grains": {"file": "bicrystal-grains.yaml",
                       "tripod": {"show_names": True}},
            "_card_dir": str(tmp_path)}
    r = resolve_grains(card)
    assert [g["name"] for g in r["grains"]] == ["lower", "upper"]
    upper = r["grains"][1]
    assert [a["label"] for a in upper["arms"]] == ["[4-30]", "[340]", "[001]"]
    # exact Sigma-5: the orientation matrix rows are [4,-3,0]/5, [3,4,0]/5, z
    assert np.allclose(upper["orientation"].M,
                       [[0.8, -0.6, 0], [0.6, 0.8, 0], [0, 0, 1]])
