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
"""Physics ground-truth test on the try-it example.

The generator inserts a known dislocation content (an edge quadrupole);
this test renders the example card and asserts that DXA -- via the full
ovzm chain, straight from the provenance record -- recovers it exactly:
4 perfect a/2<110> segments, all 90 deg edge, net b = 0, a ~ 3.52 A.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")
pytest.importorskip("ovito", reason="physics test needs the ovito module")

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "try-it"


def test_edge_quadrupole_ground_truth(tmp_path):
    for f in ("make_edge_dipoles.py", "edge-dipoles.yaml"):
        shutil.copy(EXAMPLE / f, tmp_path / f)
    subprocess.run([sys.executable, "make_edge_dipoles.py"],
                   cwd=tmp_path, check=True)
    ident = tmp_path / "identity.yaml"
    ident.write_text("creator: CI Physics Test\n")
    env = dict(os.environ, OVZM_IDENTITY=str(ident))
    subprocess.run(["ovzm", "render", "edge-dipoles.yaml"],
                   cwd=tmp_path, check=True, env=env)

    prov = yaml.safe_load(
        (tmp_path / "edge-dipoles__edge-dipoles.png.prov.yaml").read_text())
    dxa = prov["resolved_scene"]["dxa"]

    assert dxa["n_segments"] == 4
    assert set(dxa["families"]) == {"1/2<110>"}
    assert dxa["families"]["1/2<110>"]["count"] == 4
    # closed box: zero net Burgers vector
    assert dxa["net"]["b"] == "0" and dxa["net"].get("zero") is True
    # the a-estimate is MEASURED from |b_spatial|/|b_true|
    assert abs(dxa["lattice_constant_estimate_A"] - 3.52) < 0.05
    segs = dxa["segments"]
    assert len(segs) == 4
    bs = sorted(s["b"] for s in segs)
    assert bs == ["1/2[-110]", "1/2[-110]", "1/2[1-10]", "1/2[1-10]"]
    for s in segs:
        assert s["family_name"] == "perfect"
        assert abs(s["char_angle"] - 90.0) < 3.0     # pure edge
        assert s["xi"] == "[-1-12]"
        assert s["is_infinite"]
        assert abs(s["length"] - 17.24) < 0.5        # one box period
    # provenance basics: creator resolved, input hashed
    assert prov["creator"] == "CI Physics Test"
    assert len(prov["inputs"]) == 1 and len(prov["inputs"][0]["sha256"]) == 64
