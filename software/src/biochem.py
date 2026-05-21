"""Biochemistry constants used by Fv (TAP) and VHH (TNP) surface metrics.

Hydrophobicity scales and charge assignments are pinned per Raybould 2019
Methods (TAP source) and Gordon 2025 (TNP source) verbatim. Salt-bridge
detection rules (R15a) zero charge / coerce hydrophobicity for residues
already engaged in a salt bridge so they don't double-count in PSH/PPC/PNC.
"""

import math
from typing import Optional

from parser import Residue


# Kyte-Doolittle hydrophobicity, raw values from Kyte & Doolittle 1982.
# Min-max normalized to [1.0, 2.0] per Raybould 2019 PSH definition (R25).
# Glycine value is the post-normalization value at the residue's slot; used
# as the substitute hydrophobicity for residues engaged in salt bridges.
_KD_RAW = {
    "I": 4.5, "V": 4.2, "L": 3.8, "F": 2.8, "C": 2.5, "M": 1.9, "A": 1.8,
    "G": -0.4, "T": -0.7, "S": -0.8, "W": -0.9, "Y": -1.3, "P": -1.6,
    "H": -3.2, "E": -3.5, "Q": -3.5, "D": -3.5, "N": -3.5, "K": -3.9,
    "R": -4.5,
}


def _minmax_to_range(raw: dict[str, float], lo: float, hi: float) -> dict[str, float]:
    rmin = min(raw.values())
    rmax = max(raw.values())
    span = rmax - rmin
    return {aa: lo + (v - rmin) / span * (hi - lo) for aa, v in raw.items()}


# R25 normalization target: [1.0, 2.0].
KD_HYDROPHOBICITY: dict[str, float] = _minmax_to_range(_KD_RAW, 1.0, 2.0)
GLYCINE_HYDROPHOBICITY: float = KD_HYDROPHOBICITY["G"]


# R26 charge assignment per Raybould 2019. H carries 0.1 (rounded from the
# literal H-H Henderson-Hasselbalch contribution at physiological pH).
CHARGES: dict[str, float] = {
    "D": -1.0, "E": -1.0,
    "K": 1.0, "R": 1.0,
    "H": 0.1,
}

# Side-chain heavy atoms that participate in the salt-bridge test (R15a).
# K+/R+ contribute terminal nitrogens; D-/E- contribute carboxyl oxygens.
SALT_BRIDGE_DONOR_ATOMS: dict[str, tuple[str, ...]] = {
    "LYS": ("NZ",),
    "ARG": ("NH1", "NH2", "NE"),
}
SALT_BRIDGE_ACCEPTOR_ATOMS: dict[str, tuple[str, ...]] = {
    "ASP": ("OD1", "OD2"),
    "GLU": ("OE1", "OE2"),
}

# R15a cutoff. Donor N+ to acceptor O- within this distance counts.
SALT_BRIDGE_MAX_ANGSTROMS = 3.2


def _dist(a, b) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def detect_salt_bridges(parsed) -> set[tuple[str, int, str]]:
    """Walk every K/R + D/E pair, return the set of residue keys that are in
    a salt bridge. R15a uses N+ ↔ O- atom-pair distance ≤ 3.2 Å. Returned
    keys are (chain_id, res_seq, i_code). Both partners are marked.
    """
    donors: list[tuple[str, Residue, object]] = []  # (chain, res, atom)
    acceptors: list[tuple[str, Residue, object]] = []

    for chain_id in parsed.chain_order:
        for r in parsed.residues_by_chain[chain_id]:
            donor_atoms = SALT_BRIDGE_DONOR_ATOMS.get(r.res_name)
            if donor_atoms:
                for an in donor_atoms:
                    a = r.atom(an)
                    if a is not None:
                        donors.append((chain_id, r, a))
            accept_atoms = SALT_BRIDGE_ACCEPTOR_ATOMS.get(r.res_name)
            if accept_atoms:
                for an in accept_atoms:
                    a = r.atom(an)
                    if a is not None:
                        acceptors.append((chain_id, r, a))

    in_bridge: set[tuple[str, int, str]] = set()
    for dc, dr, da in donors:
        for ac, ar, aa_atom in acceptors:
            if _dist(da, aa_atom) <= SALT_BRIDGE_MAX_ANGSTROMS:
                in_bridge.add((dc, dr.res_seq, dr.i_code or ""))
                in_bridge.add((ac, ar.res_seq, ar.i_code or ""))
                # Continue scanning so a single residue with two carboxyl O can
                # still be marked once; the set dedupes.
    return in_bridge


def hydrophobicity_of(aa_letter: str, in_salt_bridge: bool) -> Optional[float]:
    """Lookup KD hydrophobicity for an amino acid (single-letter). R15a:
    residues in a salt bridge get the glycine substitute value so they
    don't contribute the hydrophobicity of their full charged side chain."""
    if in_salt_bridge:
        return GLYCINE_HYDROPHOBICITY
    return KD_HYDROPHOBICITY.get(aa_letter)


def charge_of(aa_letter: str, in_salt_bridge: bool) -> float:
    """Lookup signed charge per R26. R15a zeroes residues engaged in a
    salt bridge so they don't count toward PPC/PNC/SFvCSP."""
    if in_salt_bridge:
        return 0.0
    return CHARGES.get(aa_letter, 0.0)
