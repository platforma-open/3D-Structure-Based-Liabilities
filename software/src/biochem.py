"""Biochemistry constants used by Fv (TAP) and VHH (TNP) surface metrics.

Hydrophobicity scales and charge assignments are pinned per Raybould 2019
Methods (TAP source) and Gordon 2025 (TNP source) verbatim. Salt-bridge
detection rules (R15a) zero charge / coerce hydrophobicity for residues
already engaged in a salt bridge so they don't double-count in PSH/PPC/PNC.
"""

import math
from typing import Optional

from parser import Residue


# Hydrophobicity scales (R48). All scales stored as "higher = more
# hydrophobic" before normalization, then min-max-normalized to [1.0, 2.0]
# per Raybould 2019 PSH definition (R25). Within-scale relative ordering is
# preserved; the normalization just rescales so PSH magnitudes stay in the
# same ballpark across scales.
#
# Kyte-Doolittle (Kyte & Doolittle 1982) — the Raybould 2019 / TAP default.
_KD_RAW = {
    "I": 4.5, "V": 4.2, "L": 3.8, "F": 2.8, "C": 2.5, "M": 1.9, "A": 1.8,
    "G": -0.4, "T": -0.7, "S": -0.8, "W": -0.9, "Y": -1.3, "P": -1.6,
    "H": -3.2, "E": -3.5, "Q": -3.5, "D": -3.5, "N": -3.5, "K": -3.9,
    "R": -4.5,
}

# Wimley-White whole-residue interface scale (Wimley & White 1996, Nat
# Struct Biol). ΔG of water→POPC interface partitioning (kcal/mol).
# Published convention: positive ΔG = unfavorable transfer = hydrophilic.
# Stored here as −ΔG so higher = more hydrophobic, matching KD direction.
_WW_RAW = {
    "A": -0.17, "C":  0.24, "D": -1.23, "E": -2.02, "F":  1.13,
    "G": -0.01, "H": -0.17, "I":  0.31, "K": -0.99, "L":  0.56,
    "M":  0.23, "N": -0.42, "P": -0.45, "Q": -0.58, "R": -0.81,
    "S": -0.13, "T": -0.14, "V": -0.07, "W":  1.85, "Y":  0.94,
}

# Hessa biological hydrophobicity (Hessa et al. 2005, Nature 433) — ΔG_app
# for Sec61 translocon-mediated membrane insertion (kcal/mol). Published as
# positive ΔG = unfavorable insertion = hydrophilic; stored here as −ΔG.
_HESSA_RAW = {
    "A": -0.11, "C":  0.13, "D": -3.49, "E": -2.68, "F":  0.32,
    "G": -0.74, "H": -2.06, "I":  0.60, "K": -2.71, "L":  0.55,
    "M":  0.10, "N": -2.05, "P": -2.23, "Q": -2.36, "R": -2.58,
    "S": -0.84, "T": -0.52, "V":  0.31, "W":  0.27, "Y": -0.68,
}

# Eisenberg-McLachlan consensus normalized scale (Eisenberg et al. 1984).
# Published as "higher = more hydrophobic" — no sign flip.
_EM_RAW = {
    "A":  0.62, "C":  0.29, "D": -0.90, "E": -0.74, "F":  1.19,
    "G":  0.48, "H": -0.40, "I":  1.38, "K": -1.50, "L":  1.06,
    "M":  0.64, "N": -0.78, "P":  0.12, "Q": -0.85, "R": -2.53,
    "S": -0.18, "T": -0.05, "V":  1.08, "W":  0.81, "Y":  0.26,
}

# Black-Mould normalized hydrophobicity (Black & Mould 1991, Anal. Biochem.
# 193:72). Published on a [0, 1] range, higher = more hydrophobic.
_BM_RAW = {
    "A": 0.616, "C": 0.680, "D": 0.028, "E": 0.043, "F": 1.000,
    "G": 0.501, "H": 0.165, "I": 0.943, "K": 0.283, "L": 0.943,
    "M": 0.738, "N": 0.236, "P": 0.711, "Q": 0.251, "R": 0.000,
    "S": 0.359, "T": 0.450, "V": 0.825, "W": 0.878, "Y": 0.880,
}


def _minmax_to_range(raw: dict[str, float], lo: float, hi: float) -> dict[str, float]:
    rmin = min(raw.values())
    rmax = max(raw.values())
    span = rmax - rmin
    return {aa: lo + (v - rmin) / span * (hi - lo) for aa, v in raw.items()}


# R25 normalization target: [1.0, 2.0]. KD is the default and stays exported
# for backwards-compat callers; new code should resolve through
# `get_hydrophobicity_scale()`.
KD_HYDROPHOBICITY: dict[str, float] = _minmax_to_range(_KD_RAW, 1.0, 2.0)
GLYCINE_HYDROPHOBICITY: float = KD_HYDROPHOBICITY["G"]

# R48 — registry of selectable scales. Keys match the CLI flag /
# `BlockData.hydrophobicityScale` discriminator. Each scale's glycine slot is
# the post-normalization R15a salt-bridge substitute value.
HYDROPHOBICITY_SCALES: dict[str, dict[str, float]] = {
    "kd": KD_HYDROPHOBICITY,
    "ww": _minmax_to_range(_WW_RAW, 1.0, 2.0),
    "hessa": _minmax_to_range(_HESSA_RAW, 1.0, 2.0),
    "em": _minmax_to_range(_EM_RAW, 1.0, 2.0),
    "bm": _minmax_to_range(_BM_RAW, 1.0, 2.0),
}


def get_hydrophobicity_scale(name: str) -> tuple[dict[str, float], float]:
    """Resolve a scale name to (scale_dict, glycine_value)."""
    scale = HYDROPHOBICITY_SCALES.get(name)
    if scale is None:
        raise ValueError(
            f"Unknown hydrophobicity scale '{name}'. "
            f"Available: {sorted(HYDROPHOBICITY_SCALES.keys())}"
        )
    return scale, scale["G"]


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


def hydrophobicity_of(
    aa_letter: str,
    in_salt_bridge: bool,
    scale: dict[str, float] = KD_HYDROPHOBICITY,
    glycine_value: float = GLYCINE_HYDROPHOBICITY,
) -> Optional[float]:
    """Lookup hydrophobicity for a residue under the given scale (default
    KD). R15a: residues engaged in a salt bridge get the scale's glycine
    substitute value so they don't contribute the hydrophobicity of their
    full charged side chain."""
    if in_salt_bridge:
        return glycine_value
    return scale.get(aa_letter)


def charge_of(aa_letter: str, in_salt_bridge: bool) -> float:
    """Lookup signed charge per R26. R15a zeroes residues engaged in a
    salt bridge so they don't count toward PPC/PNC/SFvCSP."""
    if in_salt_bridge:
        return 0.0
    return CHARGES.get(aa_letter, 0.0)
