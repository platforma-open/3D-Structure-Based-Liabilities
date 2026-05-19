"""R14 numbering-scheme constants + R10 region tagging.

Per spec R14, the block needs ~30 numbering-scheme constants (canonical Cys
positions, CDR ranges, VHH hallmark tetrad, CDRH3 compactness anchors)
committed as Python literals. ANARCI is cited as the source of the schemes
themselves but is not a runtime dependency.

R10 PLATFORMA CDR records (the spec's preferred path) are now consumed —
parser.py extracts them from `REMARK 99 PLATFORMA CDR*` lines and stuffs
them into `Parsed.platforma_cdrs`; `region_for` below uses those over the
fixed scheme ranges when present. The scheme ranges below remain as fallback
when records are missing (legacy crystal PDBs, hand-uploaded structures).
"""

from typing import Optional


# R10: scheme-aware fixed CDR ranges per chain role. Ranges are inclusive on
# both ends, given in the scheme's own numbering (so e.g. "Chothia H26-H32"
# means res_seq 26..32 on the chain labelled as the heavy chain).
#
# Heavy chain entries cover Fv and VHH (VHH borrows the heavy ranges since
# its single chain follows the heavy-chain numbering convention).
#
# IMGT ranges from spec line 64; Chothia ranges from spec line 65. Kabat is
# included as a third common option pinned at the standard Kabat boundaries
# (Wu & Kabat 1991). FR ranges are derived as the residues between CDRs and
# capped at the typical V-domain extent (1..128 for IMGT, 1..113 for Chothia
# heavy / 1..108 light, 1..113 Kabat heavy / 1..107 light).
SCHEME_CDR_RANGES = {
    "imgt": {
        "H": {"CDR1": (27, 38), "CDR2": (56, 65), "CDR3": (105, 117)},
        "L": {"CDR1": (27, 38), "CDR2": (56, 65), "CDR3": (105, 117)},
    },
    "chothia": {
        "H": {"CDR1": (26, 32), "CDR2": (52, 56), "CDR3": (95, 102)},
        "L": {"CDR1": (24, 34), "CDR2": (50, 56), "CDR3": (89, 97)},
    },
    "kabat": {
        "H": {"CDR1": (31, 35), "CDR2": (50, 65), "CDR3": (95, 102)},
        "L": {"CDR1": (24, 34), "CDR2": (50, 56), "CDR3": (89, 97)},
    },
}

# Approximate V-domain end positions for FR4 cap, per scheme/chain.
SCHEME_VDOMAIN_END = {
    "imgt": {"H": 128, "L": 128},
    "chothia": {"H": 113, "L": 108},
    "kabat": {"H": 113, "L": 107},
}

# R21 canonical disulfide positions per scheme. (cys1, cys2) on each chain.
CANONICAL_CYS_POSITIONS = {
    "imgt": {"H": (23, 104), "L": (23, 104)},
    "chothia": {"H": (22, 92), "L": (23, 88)},
    "kabat": {"H": (22, 92), "L": (23, 88)},
}

# R33 VHH hallmark tetrad. Position pairs per scheme; spec line 114 calls out
# the Kabat 37/44/45/47 ↔ IMGT 42/49/50/52 mapping.
HALLMARK_TETRAD = {
    "imgt": (42, 49, 50, 52),
    "chothia": (37, 44, 45, 47),  # Chothia closely matches Kabat here
    "kabat": (37, 44, 45, 47),
}

# R30 CDRH3 compactness anchors (IMGT 102, 103, 118, 119). Other schemes have
# no canonical equivalent; compactness is an IMGT-anchored metric in the spec.
CDRH3_COMPACTNESS_ANCHORS_IMGT = (102, 103, 118, 119)


def _normalize_scheme(scheme: Optional[str]) -> Optional[str]:
    if scheme is None:
        return None
    s = scheme.strip().lower()
    if s in SCHEME_CDR_RANGES:
        return s
    return None


def region_for(
    chain_role: Optional[str],
    res_seq: int,
    scheme: Optional[str],
    platforma_cdrs: Optional[dict] = None,
) -> Optional[str]:
    """Return "FR1" / "CDR1" / "FR2" / "CDR2" / "FR3" / "CDR3" / "FR4" /
    None. Returns None when chain_role is unknown (e.g. antigen chains in a
    complex), scheme is invalid, or residue falls outside the V-domain (e.g.
    constant region in a Fab — we don't tag CH1/CL).

    chain_role: "H" or "L". Pass "H" for VHH (single-chain camelid) too;
    its numbering follows heavy-chain convention.

    platforma_cdrs (spec R10 preferred path): when provided and contains
    `chain_role`, the dict {"CDR1": (start, end), "CDR2": ..., "CDR3": ...}
    overrides the scheme-fixed CDR ranges. The Structure Prediction block
    writes these as `REMARK 99 PLATFORMA CDR*` records; downstream we treat
    them as authoritative (per R9 / spec line 60).
    """
    s = _normalize_scheme(scheme)
    if s is None or chain_role not in ("H", "L"):
        return None

    cdrs = None
    if platforma_cdrs and chain_role in platforma_cdrs:
        from_remark = platforma_cdrs[chain_role]
        if all(k in from_remark for k in ("CDR1", "CDR2", "CDR3")):
            cdrs = from_remark
    if cdrs is None:
        cdrs = SCHEME_CDR_RANGES[s].get(chain_role)
    if cdrs is None:
        return None

    cdr1_start, cdr1_end = cdrs["CDR1"]
    cdr2_start, cdr2_end = cdrs["CDR2"]
    cdr3_start, cdr3_end = cdrs["CDR3"]
    v_end = SCHEME_VDOMAIN_END[s][chain_role]

    if res_seq > v_end:
        return None  # constant region — not tagged
    if res_seq < cdr1_start:
        return "FR1"
    if cdr1_start <= res_seq <= cdr1_end:
        return "CDR1"
    if cdr1_end < res_seq < cdr2_start:
        return "FR2"
    if cdr2_start <= res_seq <= cdr2_end:
        return "CDR2"
    if cdr2_end < res_seq < cdr3_start:
        return "FR3"
    if cdr3_start <= res_seq <= cdr3_end:
        return "CDR3"
    if cdr3_end < res_seq <= v_end:
        return "FR4"
    return None


def role_of_chain(
    chain_id: str,
    heavy_chain_id: Optional[str],
    light_chain_id: Optional[str],
) -> Optional[str]:
    """Map a PDB chain ID to the antibody chain role for region tagging.
    Returns "H", "L", or None (e.g. antigen chains in a complex)."""
    if heavy_chain_id and chain_id == heavy_chain_id:
        return "H"
    if light_chain_id and chain_id == light_chain_id:
        return "L"
    return None
