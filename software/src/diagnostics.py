"""Spec defensive checks emitted into the JSON report's `diagnostics` field.

SSBOND cross-check (spec R21): compare PDB SSBOND header records against the
geometry-detected disulfide bonds from `cysteines.py`. Log any mismatch — the
header may declare bonds that geometry rejects (failed distance test), or
geometry may find bonds the header missed (e.g. an ImmuneBuilder PDB with no
SSBOND section).

Hallmark tetrad re-check (spec R33): read the residues at the four hallmark
positions on the heavy chain and report them. The spec just wants the values
logged so a downstream consumer can compare against the upstream block's
classification; we don't enforce a canonical residue set because the
IgG-vs-VHH distinction at those positions is informational, not deterministic.
"""

from typing import Optional

from numbering import HALLMARK_TETRAD


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


def check_hallmark_tetrad(parsed, numbering_scheme: Optional[str], heavy_chain_id: Optional[str]) -> Optional[dict]:
    """Read the four hallmark-tetrad residues on the heavy chain and report.

    Returns None when scheme or heavy chain isn't set. Otherwise:
      {
        "scheme": "imgt" | "chothia" | "kabat",
        "chain": "<heavy chain id>",
        "positions": [{"position": int, "resName": str|None}, ...],
        "missing": [int, ...]   # positions absent from the chain
      }
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
    for p in positions:
        name = by_pos.get(p)
        rows.append({"position": p, "resName": name})
        if name is None:
            missing.append(p)
    return {
        "scheme": scheme,
        "chain": heavy_chain_id,
        "positions": rows,
        "missing": missing,
    }
