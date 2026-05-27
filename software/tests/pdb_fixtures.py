"""Minimal PDB-record synthesis helpers for tests.

`atom_line` formats a single fixed-column ATOM record per the PDB v3.30
spec (cols 1-78). `make_pdb` wraps a sequence of (chain_id, res_seq,
res_name, b_factor) tuples into a parseable PDB string, emitting both
N and CA atoms per residue so `_mean_b_factor` has something to average.
For rejection-path tests where coordinates don't matter, all atoms land
at the origin; downstream geometry tests can override coords via the
optional `coords` keyword."""


def atom_line(
    serial: int,
    atom_name: str,
    res_name: str,
    chain_id: str,
    res_seq: int,
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    b_factor: float = 20.0,
    element: str = "N",
) -> str:
    return (
        f"ATOM  "
        f"{serial:>5} "
        f"{atom_name:<4}"
        f" "  # altLoc
        f"{res_name:>3}"
        f" "
        f"{chain_id:>1}"
        f"{res_seq:>4}"
        f" "  # iCode
        f"   "  # 3-char gap
        f"{x:>8.3f}"
        f"{y:>8.3f}"
        f"{z:>8.3f}"
        f"{1.00:>6.2f}"  # occupancy
        f"{b_factor:>6.2f}"
        f"          "  # 10-char gap
        f"{element:>2}"
    )


def make_pdb(residues: list[tuple[str, int, str, float]]) -> str:
    """Build a PDB string from a list of (chain_id, res_seq, res_name, b_factor)
    tuples. One CA atom per residue (sufficient for chain-count + B-factor
    tests; not enough for SASA but rejection paths don't reach FreeSASA)."""
    lines = []
    for i, (chain, seq, name, b) in enumerate(residues, start=1):
        lines.append(atom_line(i, "CA", name, chain, seq, b_factor=b, element="C"))
    return "\n".join(lines) + "\n"


def make_chain(chain_id: str, length: int, res_name: str = "ALA", b: float = 20.0):
    """Convenience: a single chain of `length` identical residues."""
    return [(chain_id, i + 1, res_name, b) for i in range(length)]
