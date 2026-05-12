"""Derive heavy-atom Ala-X-Ala SASA reference values for all 20 amino acids
per spec R11.

For each amino acid X, build an extended Ala-X-Ala tripeptide with
PeptideBuilder (φ=ψ=180°), run FreeSASA on the heavy-atom-only structure
(matches the ImmuneBuilder input shape per spec R15), and record the
central residue's total SASA and side-chain SASA.

The output JSON is committed to `software/src/ala_x_ala_refs.json`. The
runtime `main.py` loads it and divides per-residue SASA by these references
to compute rSASA — replacing FreeSASA's Naccess-derived default references.

Run inside the block's Docker image (FreeSASA already there):
  docker run --rm -v "$(pwd)/scripts:/work" <liabilities-image> sh -c '
    pip install --quiet PeptideBuilder
    python /work/derive_ala_x_ala_refs.py /work/../src/ala_x_ala_refs.json
  '

PeptideBuilder + Biopython are NOT in the runtime requirements — they're
needed only for this one-shot derivation.

Methodology mirrors Yang & Blundell 1996 / Shrake-Rupley 1973 as cited by
spec R11. Hydrogens absent by construction (PeptideBuilder writes heavy
atoms only). Probe radius = FreeSASA default (1.4 Å).
"""

import io
import json
import sys
from pathlib import Path

import Bio.PDB
import freesasa
import PeptideBuilder
from PeptideBuilder import Geometry


AMINO_ACIDS_3 = [
    "ALA", "ARG", "ASN", "ASP", "CYS",
    "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO",
    "SER", "THR", "TRP", "TYR", "VAL",
]
_THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def build_axa(x_three: str) -> str:
    """Build an extended Ala-X-Ala tripeptide and return its PDB string.

    PeptideBuilder uses one-letter codes. Central residue gets the
    `geometry()` default rotamer; flanking Ala provide neighboring backbone
    contributions so the central residue's SASA reflects an in-chain context
    rather than a free amino acid (per Yang & Blundell convention).
    """
    geo = [Geometry.geometry(_THREE_TO_ONE[x]) for x in ["ALA", x_three, "ALA"]]
    structure = PeptideBuilder.initialize_res(geo[0])
    for g in geo[1:]:
        PeptideBuilder.add_residue(structure, g)

    out = io.StringIO()
    pdb_io = Bio.PDB.PDBIO()
    pdb_io.set_structure(structure)
    pdb_io.save(out)
    return out.getvalue()


def derive_one(x_three: str, tmpdir: Path) -> dict:
    """Return {"total": float, "sidechain": float} for residue X."""
    pdb_text = build_axa(x_three)
    pdb_path = tmpdir / f"{x_three}.pdb"
    pdb_path.write_text(pdb_text)

    s = freesasa.Structure(str(pdb_path))
    res = freesasa.calc(s)
    areas = res.residueAreas()
    # Central residue: chain "A", res 2.
    central = areas["A"]["2"]
    if central.residueType != x_three:
        raise RuntimeError(
            f"central residue mismatch for {x_three}: got {central.residueType}"
        )
    return {
        "total": round(float(central.total), 4),
        "sidechain": round(float(central.sideChain), 4),
    }


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: derive_ala_x_ala_refs.py <output.json>", file=sys.stderr)
        sys.exit(2)
    out_path = Path(sys.argv[1])

    tmpdir = Path("/tmp/axa-deriv")
    tmpdir.mkdir(exist_ok=True)

    results: dict[str, dict[str, float]] = {}
    for x in AMINO_ACIDS_3:
        try:
            results[x] = derive_one(x, tmpdir)
            print(f"  {x}: total={results[x]['total']:7.2f}  side={results[x]['sidechain']:7.2f}")
        except Exception as e:
            print(f"  {x}: FAILED — {e}", file=sys.stderr)
            results[x] = {"total": None, "sidechain": None}

    payload = {
        "_provenance": {
            "method": "Ala-X-Ala extended tripeptide, heavy atoms only, "
                      "FreeSASA default classifier + probe radius 1.4 Å "
                      "(Shrake-Rupley). Per spec R11 / Yang & Blundell 1996.",
            "generator": "software/scripts/derive_ala_x_ala_refs.py",
        },
        "references": results,
    }
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"\nwrote {out_path}")

    # When running inside the block's Docker (root) but mounting host paths,
    # the output ends up root-owned. Match the bind-mount's owner so the host
    # user can re-edit the JSON without a chown dance.
    import os
    try:
        mount_stat = os.stat(out_path.parent)
        os.chown(out_path, mount_stat.st_uid, mount_stat.st_gid)
    except (FileNotFoundError, PermissionError, OSError):
        pass


if __name__ == "__main__":
    main()
