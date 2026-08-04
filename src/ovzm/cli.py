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
"""ovzm — declarative OVITO visualization of LAMMPS files.

Commands:
  ovzm render  card.yaml [-o out.png]   render image (or movie for trajectories)
  ovzm session card.yaml [-o out.ovito] write a ready-to-open OVITO session
  ovzm import  state.ovito [-o card.yaml] best-effort session -> card
  ovzm validate card.yaml               check a card against the schema
  ovzm schema                            print the JSON schema
"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ovzm", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("render", help="render a card to an image/movie")
    p.add_argument("card")
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--ask", action="store_true",
                   help="prompt interactively for missing required info (species names)")

    p = sub.add_parser("session", help="write a .ovito session from a card")
    p.add_argument("card")
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--ask", action="store_true")

    p = sub.add_parser("grid", help="render one card over N inputs (grid.inputs) into a comparison grid")
    p.add_argument("card")
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--ask", action="store_true")

    p = sub.add_parser("prov", help="print the provenance embedded in a rendered PNG")
    p.add_argument("image")

    p = sub.add_parser("info", help="inspect a LAMMPS file: types, box, frames, guessed orientation")
    p.add_argument("file")

    p = sub.add_parser("import", help="best-effort .ovito -> card YAML")
    p.add_argument("state")
    p.add_argument("-o", "--output", default=None)

    p = sub.add_parser("validate", help="validate a card against the schema")
    p.add_argument("card")

    sub.add_parser("schema", help="print the card JSON schema")

    args = ap.parse_args(argv)

    if args.cmd == "schema":
        from .card import load_schema
        print(json.dumps(load_schema(), indent=2))
        return 0

    if args.cmd == "validate":
        from .card import load_card
        try:
            load_card(args.card)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print("ok")
        return 0

    if args.cmd == "import":
        from .importer import import_session
        text = import_session(args.state)
        if args.output:
            with open(args.output, "w") as fh:
                fh.write(text)
            print(f"[ovzm] wrote {args.output}")
        else:
            print(text)
        return 0

    if args.cmd == "info":
        return info(args.file)

    if args.cmd == "prov":
        from .runner import read_embedded_prov
        text = read_embedded_prov(args.image)
        if text is None:
            print("no embedded provenance found (not rendered by ovzm ≥0.2?)",
                  file=sys.stderr)
            return 1
        print(text, end="")
        return 0

    if args.cmd == "grid":
        from .grid import run_grid
        run_grid(args.card, args.output, ask=args.ask)
        return 0

    from .runner import run_render, run_session
    if args.cmd == "render":
        run_render(args.card, args.output, ask=args.ask)
    elif args.cmd == "session":
        run_session(args.card, args.output, ask=args.ask)
    return 0


def info(path: str) -> int:
    """Print what a card needs to know about a file — the card-authoring helper."""
    from ovito.io import import_file
    from .crystal import orientation_from_filename
    pipe = import_file(path)
    data = pipe.compute()
    n_frames = pipe.source.num_frames
    print(f"file:      {path}")
    print(f"frames:    {n_frames}")
    print(f"atoms:     {data.particles.count}")
    ts = data.attributes.get("Timestep")
    if ts is not None:
        print(f"timestep:  {ts}")
    cell = data.cell
    if cell is not None:
        import numpy as np
        m = np.asarray(cell)
        print(f"box (Å):   {m[0,0]:.2f} x {m[1,1]:.2f} x {m[2,2]:.2f}"
              f"   pbc: {tuple(bool(b) for b in cell.pbc)}")
    tprop = data.particles.particle_types
    if tprop is not None:
        for t in tprop.types:
            import numpy as np
            n = int(np.sum(np.asarray(tprop) == t.id))
            name = t.name or "?? (no species name — card needs atoms.names)"
            print(f"type {t.id}:    {name}  ({n} atoms)")
    o = orientation_from_filename(path)
    if o is not None:
        lx, ly, lz = o.axis_labels()
        print(f"orientation (from filename): x={lx} y={ly} z={lz}")
    else:
        print("orientation: not encoded in filename — card needs crystal.x/y/z "
              "(or labels stay in DXA lattice frame)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
