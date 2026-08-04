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
"""ovito-auto-viz: declarative, reproducible OVITO visualization via YAML viz-cards."""
__version__ = "0.3.1"

REPO_URL = "https://github.com/biterik/ovito-auto-viz"
TOOL_CREDIT = (
    "created with ovito-auto-viz (" + REPO_URL + ") by Erik Bitzek, "
    "funded by NFDI-MatWerk (DFG project 460247524)"
)
YAML_CREDIT_HEADER = (
    "# " + "-" * 74 + "\n"
    "# " + TOOL_CREDIT + "\n"
    "# " + "-" * 74 + "\n"
)
