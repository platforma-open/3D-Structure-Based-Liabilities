"""Structure-side data, parsing, and defensive checks.

PDB parsing, REMARK 99 PLATFORMA CDR record extraction, FreeSASA wrapper
output normalization at the caller, B-factor read-through, the
numbering-scheme constants (canonical Cys positions, CDR ranges,
hallmark tetrad, CDRH3 compactness anchors), `region_for` resolution,
plus the hallmark-tetrad defensive check.
"""

import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Section 1: PDB parsing
# ---------------------------------------------------------------------------


@dataclass
class Atom:
    name: str
    x: float
    y: float
    z: float
    # PDB B-factor (temperature factor). ImmuneBuilder repurposes this column
    # to carry per-atom predicted positional error in Angstroms (upstream
    # guarantee). For experimental crystal structures it stays the literal
    # B-factor; both are treated interchangeably for confidence gating.
    b_factor: float = 0.0


@dataclass
class Residue:
    res_seq: int
    i_code: str
    res_name: str
    atoms: List[Atom] = field(default_factory=list)

    def atom(self, name: str) -> Optional[Atom]:
        for a in self.atoms:
            if a.name == name:
                return a
        return None


@dataclass
class Parsed:
    chain_order: List[str] = field(default_factory=list)
    residues_by_chain: Dict[str, List[Residue]] = field(default_factory=dict)
    # CDR ranges from `REMARK 99 PLATFORMA CDR*` records emitted
    # by the Structure Prediction block. Shape: {"H": {"CDR1": (start, end),
    # "CDR2": (...), "CDR3": (...)}, "L": {...}}. Empty when not present;
    # downstream code falls back to scheme-aware fixed ranges.
    platforma_cdrs: Dict[str, Dict[str, Tuple[int, int]]] = field(default_factory=dict)
    # REMARK 99 chain identity is authoritative. Maps role ("H"/"L")
    # to the physical PDB chain letter the records reference. e.g. given
    # `REMARK 99 PLATFORMA CDRH1 B27-B38`, this becomes {"H": "B"}. Caller
    # uses this to override the user's heavy/light chain dropdowns when
    # records are present.
    chain_role_to_pdb_chain: Dict[str, str] = field(default_factory=dict)


# `REMARK 99 PLATFORMA CDRH1 H27-H38`. Capture
# both the role letter (group 1) and the chain letter at each end of the
# range (groups 3, 5) so we can also extract the chain identity.
_PLATFORMA_CDR_RE = re.compile(
    r"^REMARK\s+99\s+PLATFORMA\s+CDR([HL])([123])\s+([A-Za-z])(\d+)-([A-Za-z])(\d+)\s*$"
)


def parse_pdb(text: str) -> Parsed:
    out = Parsed()
    # Residues are keyed by (chain, res_seq, i_code); atoms accumulate per residue.
    residues: Dict[str, Residue] = {}
    in_first_model = True
    model_count = 0

    for raw in text.splitlines():
        # PDB lines are nominally 80 columns; many producers strip trailing
        # whitespace. Pad to a full 80 so fixed-offset slicing further down
        # never reads past the end of `raw`.
        line = raw.ljust(80)
        tag = line[0:6].rstrip()

        if tag == "MODEL":
            model_count += 1
            if model_count > 1:
                in_first_model = False
        elif tag == "REMARK":
            m = _PLATFORMA_CDR_RE.match(raw.rstrip())
            if m:
                role = m.group(1)
                cdr_idx = m.group(2)
                chain_start, start_s = m.group(3), m.group(4)
                chain_end, end_s = m.group(5), m.group(6)
                # Both ends of the range must reference the same chain.
                if chain_start.upper() != chain_end.upper():
                    continue
                try:
                    start, end = int(start_s), int(end_s)
                except ValueError:
                    continue
                if end < start:
                    continue
                out.platforma_cdrs.setdefault(role, {})[f"CDR{cdr_idx}"] = (start, end)
                # Record the physical PDB chain letter for this role.
                # Later records for the same role must agree; conflicts are
                # silently dropped (downstream falls back to the user's mapping).
                existing = out.chain_role_to_pdb_chain.get(role)
                if existing is None:
                    out.chain_role_to_pdb_chain[role] = chain_start
                elif existing.upper() != chain_start.upper():
                    out.chain_role_to_pdb_chain.pop(role, None)
        elif tag in ("ATOM", "HETATM"):
            if not in_first_model:
                continue
            # ATOM / HETATM record fixed offsets (PDB v3.30). We pull:
            #   12-15 atom name        16    altLoc
            #   17-19 residue 3-letter 21    chainID
            #   22-25 residue seq num  26    iCode (insertion code)
            #   30-37 x   38-45 y      46-53 z  (Å, free-form floats)
            #   60-65 B-factor (Å² for crystals, Å for ImmuneBuilder-predicted)
            #
            # altLoc filter , multi-conformer side chains list each alternate
            # location with a letter ('A', 'B', ...). Keeping only ' ' and 'A'
            # ensures geometry tests (distance pairs, salt bridges) don't
            # double-count atoms.
            alt_loc = line[16:17]
            if alt_loc not in (" ", "A"):
                continue
            atom_name = line[12:16].strip()
            res_name = line[17:20].strip()
            chain_id = line[21:22] if line[21:22] != "" else " "
            try:
                res_seq = int(line[22:26].strip())
            except ValueError:
                continue
            i_code = line[26:27].strip()
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                continue
            try:
                b_factor = float(line[60:66])
            except ValueError:
                b_factor = 0.0

            key = f"{chain_id}|{res_seq}|{i_code}"
            res = residues.get(key)
            if res is None:
                res = Residue(res_seq=res_seq, i_code=i_code, res_name=res_name)
                residues[key] = res
                if chain_id not in out.residues_by_chain:
                    out.residues_by_chain[chain_id] = []
                    out.chain_order.append(chain_id)
                out.residues_by_chain[chain_id].append(res)
            res.atoms.append(Atom(name=atom_name, x=x, y=y, z=z, b_factor=b_factor))
    return out


# ---------------------------------------------------------------------------
# Section 2: numbering-scheme constants + region tagging
# ---------------------------------------------------------------------------


# Scheme-aware fixed CDR ranges per chain role. Ranges are inclusive on
# both ends, given in the scheme's own numbering (so e.g. "Chothia H26-H32"
# means res_seq 26..32 on the chain labelled as the heavy chain).
#
# Heavy chain entries cover Fv and VHH (VHH borrows the heavy ranges since
# its single chain follows the heavy-chain numbering convention).
#
# IMGT ranges and Chothia ranges from the standard references. Kabat is
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

# Canonical disulfide positions per scheme. (cys1, cys2) on each chain.
CANONICAL_CYS_POSITIONS = {
    "imgt": {"H": (23, 104), "L": (23, 104)},
    "chothia": {"H": (22, 92), "L": (23, 88)},
    "kabat": {"H": (22, 92), "L": (23, 88)},
}

# VHH hallmark tetrad. Position pairs per scheme; the source paper calls out
# the Kabat 37/44/45/47 ↔ IMGT 42/49/50/52 mapping.
HALLMARK_TETRAD = {
    "imgt": (42, 49, 50, 52),
    "chothia": (37, 44, 45, 47),  # Chothia closely matches Kabat here
    "kabat": (37, 44, 45, 47),
}

# CDRH3 compactness anchors (IMGT 102, 103, 118, 119). Other schemes have
# no canonical equivalent; compactness is defined as an IMGT-anchored metric.
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
    constant region in a Fab , we don't tag CH1/CL).

    chain_role: "H" or "L". Pass "H" for VHH (single-chain camelid) too;
    its numbering follows heavy-chain convention.

    platforma_cdrs (preferred path): when provided and contains
    `chain_role`, the dict {"CDR1": (start, end), "CDR2": ..., "CDR3": ...}
    overrides the scheme-fixed CDR ranges. The Structure Prediction block
    writes these as `REMARK 99 PLATFORMA CDR*` records; downstream we treat
    them as authoritative.
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
        return None  # constant region , not tagged
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


# ---------------------------------------------------------------------------
# Section 3: hallmark-tetrad defensive check
# ---------------------------------------------------------------------------


# Canonical hallmark-tetrad residue sets at Kabat 37 / 44 / 45 / 47
# (≡ IMGT 42 / 49 / 50 / 52). Vincke et al. 2009 / Pardon et al. 2014:
# VHH-specific residues are F / E / R / G; canonical IgG is V / G / L / W.
# Each set is a tuple of accepted single-letter codes per position so
# common variants (e.g. Y instead of F at position 1 in some camelid
# lineages) don't trip a false-positive mismatch warning.
_HALLMARK_IGG = (("V",), ("G",), ("L",), ("W",))
_HALLMARK_VHH = (("F", "Y"), ("E", "Q"), ("R", "K"), ("G", "F"))

# Three-letter → one-letter amino acid map. Single source of truth for
# the whole package; `motifs.py` + `metrics.py` import from here too.
# Non-standard / HETATM residues (MSE, modified residues, etc.) collapse
# to "X" at call sites via `AA_THREE_TO_ONE.get(name, "X")`.
AA_THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def _match_score(observed_one_letter: list[Optional[str]], canonical: tuple) -> int:
    """Count how many of the four hallmark positions match the canonical
    set (any of the accepted variants per position). None observations
    don't contribute either way."""
    score = 0
    for i, obs in enumerate(observed_one_letter):
        if obs is None:
            continue
        if obs in canonical[i]:
            score += 1
    return score


def check_hallmark_tetrad(
    parsed,
    numbering_scheme: Optional[str],
    heavy_chain_id: Optional[str],
    chain_count_mode: Optional[str] = None,
) -> Optional[dict]:
    """Read the four hallmark-tetrad residues on the heavy chain and compare
    against the canonical IgG and VHH residue sets (Vincke 2009 / Gordon
    2025).

    Returns None when scheme or heavy chain isn't set. Otherwise:
      {
        "scheme": "imgt" | "chothia" | "kabat",
        "chain": "<heavy chain id>",
        "positions": [{"position": int, "resName": str|None, "oneLetter": str|None}, ...],
        "missing": [int, ...],
        "impliedMode": "TAP" | "TNP" | "ambiguous",
        "impliedScore": {"igg": int, "vhh": int},
        "mismatch": bool          # impliedMode != chain_count_mode (when supplied)
      }

    When `chain_count_mode` is provided and the hallmark-implied mode
    disagrees, emit a warning to stderr so the user notices engineered or
    chimeric constructs that don't look like clean IgG or VHH.
    """
    if not numbering_scheme or not heavy_chain_id:
        return None
    scheme = numbering_scheme.strip().lower()
    if scheme not in HALLMARK_TETRAD:
        return None
    positions = HALLMARK_TETRAD[scheme]
    residues = parsed.residues_by_chain.get(heavy_chain_id, [])
    by_pos = {r.res_seq: r.res_name for r in residues if not r.i_code}

    rows = []
    missing = []
    one_letters: list[Optional[str]] = []
    for p in positions:
        name = by_pos.get(p)
        one = AA_THREE_TO_ONE.get(name) if name else None
        rows.append({"position": p, "resName": name, "oneLetter": one})
        one_letters.append(one)
        if name is None:
            missing.append(p)

    igg_score = _match_score(one_letters, _HALLMARK_IGG)
    vhh_score = _match_score(one_letters, _HALLMARK_VHH)
    # Need at least 3/4 hits to claim a clean identity; ties / sub-3 scores
    # stay "ambiguous" so we don't warn on partial data.
    if igg_score >= 3 and igg_score > vhh_score:
        implied = "TAP"
    elif vhh_score >= 3 and vhh_score > igg_score:
        implied = "TNP"
    else:
        implied = "ambiguous"

    mismatch = (
        chain_count_mode is not None
        and implied != "ambiguous"
        and implied != chain_count_mode
    )
    if mismatch:
        observed = ", ".join(
            f"{p}={o or '?'}" for p, o in zip(positions, one_letters)
        )
        print(
            f"WARN: hallmark-tetrad residues at {observed} "
            f"imply {implied} but chain count says {chain_count_mode}. "
            f"Likely an engineered or chimeric construct; surface metrics "
            f"may be miscalibrated.",
            file=sys.stderr,
        )

    return {
        "scheme": scheme,
        "chain": heavy_chain_id,
        "positions": rows,
        "missing": missing,
        "impliedMode": implied,
        "impliedScore": {"igg": igg_score, "vhh": vhh_score},
        "mismatch": mismatch,
    }
