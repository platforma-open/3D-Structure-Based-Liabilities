"""Derive heavy-atom Ala-X-Ala SASA reference values for all 20 amino acids
per spec R11.

For each amino acid X, build an extended Ala-X-Ala tripeptide with
PeptideBuilder, run FreeSASA on the heavy-atom-only structure (matches
the ImmuneBuilder input shape per spec R15), and record the central
residue's total SASA and side-chain SASA.

Output is a TSV at `software/liabilities-script/data/heavy_atom_max_sasa.tsv`
(three columns: residue, total, sidechain). The runtime `main.py`
loads it and divides per-residue SASA by these references to compute
rSASA, replacing FreeSASA's Naccess-derived defaults.

Run inside the block's Docker image (FreeSASA already there):
  docker run --rm -v "$(pwd)/software:/work" <liabilities-image> sh -c '
    pip install --quiet PeptideBuilder
    python /work/scripts/derive_ala_x_ala_refs.py \
      /work/liabilities-script/data/heavy_atom_max_sasa.tsv
  '

PeptideBuilder + Biopython are NOT in the runtime requirements; they're
needed only for this one-shot derivation. Methodology mirrors Yang &
Blundell 1996 / Shrake-Rupley 1973 (probe radius 1.4 Å), per spec R11.
"""

import io
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
        print("usage: derive_ala_x_ala_refs.py <output.tsv>", file=sys.stderr)
        sys.exit(2)
    out_path = Path(sys.argv[1])

    tmpdir = Path("/tmp/axa-deriv")
    tmpdir.mkdir(exist_ok=True)

    rows: list[tuple[str, float | None, float | None]] = []
    for x in AMINO_ACIDS_3:
        try:
            r = derive_one(x, tmpdir)
            rows.append((x, r["total"], r["sidechain"]))
            print(f"  {x}: total={r['total']:7.2f}  side={r['sidechain']:7.2f}")
        except Exception as e:
            print(f"  {x}: FAILED , {e}", file=sys.stderr)
            rows.append((x, None, None))

    lines = [
        "# Heavy-atom-only Ala-X-Ala reference SASAs (R11), Yang & Blundell 1996",
        "# Re-derived via software/scripts/derive_ala_x_ala_refs.py.",
        "# residue, total (A^2), sidechain (A^2)",
        "residue\ttotal\tsidechain",
    ]
    for name, total, side in rows:
        lines.append(f"{name}\t{total if total is not None else ''}\t{side if side is not None else ''}")
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {out_path}")

    # When running inside the block's Docker (root) but mounting host paths,
    # the output ends up root-owned. Match the bind-mount's owner so the host
    # user can re-edit the TSV without a chown dance.
    import os
    try:
        mount_stat = os.stat(out_path.parent)
        os.chown(out_path, mount_stat.st_uid, mount_stat.st_gid)
    except (FileNotFoundError, PermissionError, OSError):
        pass


if __name__ == "__main__":
    main()
