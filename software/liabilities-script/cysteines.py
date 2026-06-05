# Spec R21-R23: cysteine bonding state from coordinates + canonical-position
# classification.
#
# Without numbering (scheme + chain role mapping unset) we fall back to the
# bonding-state-only path: every Cys reports "bonded" or "unbonded" by
# geometry, no four-state classification.
#
# With numbering wired we enumerate the spec's canonical-Cys PAIRS (IMGT
# H23+H104 / L23+L104; Chothia H22+H92 / L23+L88) and emit one row per
# pair (per R23):
#   - disulfide          : both canonical Cys present + bonded to each other
#   - disulfide_broken   : both canonical Cys present, not bonded as a pair
#   - disulfide_missing  : at least one of the two canonical positions has
#                          no Cys (covers partial deletions; this hit
#                          replaces what would otherwise be a `_broken`
#                          row plus a missing phantom for the same pair)
# Plus per-residue rows for any extra Cys:
#   - cys_extra          : a Cys at a non-canonical position, regardless of
#                          bonding state
#
# Per-cys drill-down is out of scope per the refreshed spec, so each hit
# only carries the two fields actually consumed downstream: the class label
# (for counts + the developability bump) and the side-chain rSASA (for the
# "exposed extra" count + the buried-vs-exposed gate in the scoring bump).

import math
from dataclasses import dataclass
from typing import Optional

from structure import CANONICAL_CYS_POSITIONS, role_of_chain


SG_SG_MAX_ANGSTROMS = 3.0
CA_CA_MAX_ANGSTROMS = 7.0


@dataclass
class CysteineHit:
    cysClass: str  # "disulfide" | "disulfide_broken" | "disulfide_missing" | "cys_extra" | "bonded" | "unbonded"
    sidechainRsasa: Optional[float]


def _dist(a, b) -> float:
    return math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))


def _bonding_test(ca1, sg1, ca2, sg2) -> bool:
    return _dist(sg1, sg2) <= SG_SG_MAX_ANGSTROMS and _dist(ca1, ca2) <= CA_CA_MAX_ANGSTROMS


def _collect_cys_records(parsed):
    """Build (chain_id, residue, ca_atom, sg_atom) tuples for every Cys
    that carries both atoms we need for geometry tests. Cys residues
    missing CA or SG (mutations, partial occupancy) are skipped silently."""
    out: list[tuple[str, object, object, object]] = []
    for chain_id in parsed.chain_order:
        for r in parsed.residues_by_chain[chain_id]:
            if r.res_name != "CYS":
                continue
            ca = r.atom("CA")
            sg = r.atom("SG")
            if ca is None or sg is None:
                continue
            out.append((chain_id, r, ca, sg))
    return out


def _scan_disulfides(cys_records) -> dict[int, int]:
    """Pairwise scan over cys_records; returns idx → partner_idx for every
    Cys engaged in a disulfide. First-match wins on ambiguous geometry:
    if one Cys could bond to two partners, we lock the first one we hit
    and treat the other as `unbonded` (consistent with REMARK SSBOND-style
    1:1 bond accounting; ambiguous cases are rare and biologically odd)."""
    partner_of: dict[int, int] = {}
    for i in range(len(cys_records)):
        for j in range(i + 1, len(cys_records)):
            _, _, ca_i, sg_i = cys_records[i]
            _, _, ca_j, sg_j = cys_records[j]
            if not _bonding_test(ca_i, sg_i, ca_j, sg_j):
                continue
            if i in partner_of or j in partner_of:
                continue
            partner_of[i] = j
            partner_of[j] = i
    return partner_of


def detect_cysteines(
    parsed,
    sasa_lookup,
    numbering_scheme: Optional[str] = None,
    heavy_chain_id: Optional[str] = None,
    light_chain_id: Optional[str] = None,
) -> list[CysteineHit]:
    """Walk every Cys residue, compute pairwise bonding state, and (when
    numbering is wired) classify each canonical disulfide PAIR against the
    scheme's expected positions. Non-canonical Cys get `cys_extra`; the
    fallback bonded/unbonded path is used when numbering is unavailable."""
    cys_records = _collect_cys_records(parsed)
    partner_of = _scan_disulfides(cys_records)

    canonical_positions: dict[str, tuple[int, int]] = (
        CANONICAL_CYS_POSITIONS.get(numbering_scheme, {}) if numbering_scheme else {}
    )

    # Numbering unwired path: emit raw bonded/unbonded per residue, no
    # canonical classification possible.
    if not canonical_positions or not (heavy_chain_id or light_chain_id):
        hits: list[CysteineHit] = []
        for idx, (chain_id, r, _ca, _sg) in enumerate(cys_records):
            key = (chain_id, f"{r.res_seq}{r.i_code}".strip())
            sasa_info = sasa_lookup.get(key, {})
            bonded = partner_of.get(idx) is not None
            hits.append(
                CysteineHit(
                    cysClass="bonded" if bonded else "unbonded",
                    sidechainRsasa=sasa_info.get("sideChainRsasa"),
                )
            )
        return hits

    # Numbered path: index Cys by (role, res_seq) so we can look up the two
    # halves of each canonical pair without re-walking the record list.
    by_role_pos: dict[tuple[str, int], int] = {}
    for idx, (chain_id, r, _ca, _sg) in enumerate(cys_records):
        role = role_of_chain(chain_id, heavy_chain_id, light_chain_id)
        if role is not None:
            by_role_pos.setdefault((role, r.res_seq), idx)

    canonical_indices: set[int] = set()
    hits: list[CysteineHit] = []

    for role, (p1, p2) in canonical_positions.items():
        if role == "H" and not heavy_chain_id:
            continue
        if role == "L" and not light_chain_id:
            continue
        i1 = by_role_pos.get((role, p1))
        i2 = by_role_pos.get((role, p2))
        if i1 is None or i2 is None:
            hits.append(CysteineHit(cysClass="disulfide_missing", sidechainRsasa=None))
            if i1 is not None:
                canonical_indices.add(i1)
            if i2 is not None:
                canonical_indices.add(i2)
            continue
        canonical_indices.add(i1)
        canonical_indices.add(i2)
        bonded_as_pair = partner_of.get(i1) == i2
        hits.append(
            CysteineHit(
                cysClass="disulfide" if bonded_as_pair else "disulfide_broken",
                sidechainRsasa=None,
            )
        )

    # Anything not consumed by a canonical pair is a non-canonical Cys.
    for idx, (chain_id, r, _ca, _sg) in enumerate(cys_records):
        if idx in canonical_indices:
            continue
        key = (chain_id, f"{r.res_seq}{r.i_code}".strip())
        sasa_info = sasa_lookup.get(key, {})
        hits.append(
            CysteineHit(
                cysClass="cys_extra",
                sidechainRsasa=sasa_info.get("sideChainRsasa"),
            )
        )

    return hits
