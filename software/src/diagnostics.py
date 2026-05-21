"""Spec defensive checks emitted into the JSON report's `diagnostics` field.

SSBOND cross-check (spec R21): compare PDB SSBOND header records against the
geometry-detected disulfide bonds from `cysteines.py`. Log any mismatch — the
header may declare bonds that geometry rejects (failed distance test), or
geometry may find bonds the header missed (e.g. an ImmuneBuilder PDB with no
SSBOND section).

Hallmark tetrad re-check (spec R33): read the residues at the four hallmark
positions on the heavy chain and compare against the canonical IgG and VHH
residue sets (Vincke et al. 2009 / Gordon 2025). When the implied identity
(majority match) disagrees with the chain-count mode (R7), emit a warning so
the user can investigate engineered or chimeric constructs.
"""

import sys
from typing import Optional

from numbering import HALLMARK_TETRAD

# Canonical hallmark-tetrad residue sets at Kabat 37 / 44 / 45 / 47
# (≡ IMGT 42 / 49 / 50 / 52). Vincke et al. 2009 / Pardon et al. 2014:
# VHH-specific residues are F / E / R / G; canonical IgG is V / G / L / W.
# Each set is a tuple of accepted single-letter codes per position so
# common variants (e.g. Y instead of F at position 1 in some camelid
# lineages) don't trip a false-positive mismatch warning.
_HALLMARK_IGG = (("V",), ("G",), ("L",), ("W",))
_HALLMARK_VHH = (("F", "Y"), ("E", "Q"), ("R", "K"), ("G", "F"))

# Three-letter → one-letter map; mirrors the same lookup used in motifs.py
# and metrics.py. Kept local to avoid cross-module imports for what is
# essentially a constant.
_AA_THREE_TO_ONE = {
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


def _norm_icode(s: Optional[str]) -> str:
    """Normalize iCode for comparison. Both the empty-string convention (PDB
    SSBOND records) and the `"-"` sentinel (cysteines.py emits this so PColumn
    String axes accept the value) collapse to empty-string here so the two
    sides of the cross-check actually meet."""
    if not s:
        return ""
    t = s.strip()
    if t in ("", "-"):
        return ""
    return t


def _pair_key(chain_a, res_a, icode_a, chain_b, res_b, icode_b):
    """Order-independent key for a Cys pair (sorted by chain+resSeq)."""
    a = (chain_a, res_a, _norm_icode(icode_a))
    b = (chain_b, res_b, _norm_icode(icode_b))
    return tuple(sorted([a, b]))


def cross_check_ssbonds(ssbonds, cys_hits) -> dict:
    """Compare PDB SSBOND records with geometry-detected disulfide bonds.

    Returns a dict suitable for JSON emission:
      {
        "headerBondCount": int,
        "geometryBondCount": int,
        "matched": int,
        "headerOnly": [...],     # SSBOND declared, geometry rejected
        "geometryOnly": [...],   # geometry found, no SSBOND
      }
    """
    header_pairs: set = set()
    for s in ssbonds:
        header_pairs.add(
            _pair_key(s.chain1, s.res1, s.i_code1, s.chain2, s.res2, s.i_code2)
        )

    # Each disulfide is represented twice in cys_hits (once per partner). De-dup.
    geom_pairs: set = set()
    for h in cys_hits:
        if h.cysClass not in ("disulfide", "disulfide_broken"):
            continue
        if h.partnerChainId is None or h.partnerResSeq is None:
            continue
        if h.cysClass == "disulfide_broken":
            # geometry rejected this; it stays under headerOnly, not geometryOnly.
            continue
        geom_pairs.add(
            _pair_key(
                h.chainId, h.resSeq, h.iCode,
                h.partnerChainId, h.partnerResSeq, h.partnerIcode,
            )
        )

    matched = header_pairs & geom_pairs
    header_only = header_pairs - geom_pairs
    geometry_only = geom_pairs - header_pairs

    def _fmt(pair):
        a, b = pair
        return {
            "chain1": a[0], "resSeq1": a[1], "iCode1": a[2] or "",
            "chain2": b[0], "resSeq2": b[1], "iCode2": b[2] or "",
        }

    return {
        "headerBondCount": len(header_pairs),
        "geometryBondCount": len(geom_pairs),
        "matched": len(matched),
        "headerOnly": [_fmt(p) for p in sorted(header_only)],
        "geometryOnly": [_fmt(p) for p in sorted(geometry_only)],
    }


def check_hallmark_tetrad(
    parsed,
    numbering_scheme: Optional[str],
    heavy_chain_id: Optional[str],
    chain_count_mode: Optional[str] = None,
) -> Optional[dict]:
    """Read the four hallmark-tetrad residues on the heavy chain and compare
    against the canonical IgG and VHH residue sets (Vincke 2009 / Gordon
    2025). Spec R33.

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
        one = _AA_THREE_TO_ONE.get(name) if name else None
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
            f"{p}={o or '—'}" for p, o in zip(positions, one_letters)
        )
        print(
            f"WARN (spec R33): hallmark-tetrad residues at {observed} "
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
