# Spec R21-R23: cysteine bonding state from coordinates + canonical-position
# classification.
#
# Without numbering (scheme + chain role mapping unset) we fall back to the
# bonding-state-only path: every Cys reports "bonded" or "unbonded" by
# geometry, no four-state classification.
#
# With numbering wired we anchor on the spec's canonical-Cys positions
# (IMGT H23+H104 / L23+L104; Chothia H22+H92 / L23+L88) and emit four-state
# classifications per R23:
#   - disulfide          : both canonical Cys present + bonded
#   - disulfide_broken   : both canonical Cys present + unbonded
#   - disulfide_missing  : a canonical position has no Cys (a phantom hit
#                          is emitted at that role with cysClass set to
#                          disulfide_missing)
#   - cys_extra          : a Cys at any non-canonical position, regardless
#                          of bonding state
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
    Cys engaged in a disulfide. First-match wins on ambiguous geometry ,
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


def _classify_cys(
    res_seq: int,
    role: Optional[str],
    bonded: bool,
    canonical_keys: set[tuple[str, int]],
    canonical_positions: dict,
) -> str:
    """R23 four-state classification. Falls back to raw bonding state
    when numbering isn't wired (no role / no canonical positions for the
    scheme), so the hit is still classified usefully in the auto-detect-only
    case (though the resulting "bonded"/"unbonded" values are inert
    downstream)."""
    if role is not None and (role, res_seq) in canonical_keys:
        return "disulfide" if bonded else "disulfide_broken"
    if role is not None and canonical_positions:
        return "cys_extra"
    return "bonded" if bonded else "unbonded"


def detect_cysteines(
    parsed,
    sasa_lookup,
    numbering_scheme: Optional[str] = None,
    heavy_chain_id: Optional[str] = None,
    light_chain_id: Optional[str] = None,
) -> list[CysteineHit]:
    """Walk every Cys residue, compute pairwise bonding state, and (when
    numbering is wired) classify each Cys against the scheme's canonical
    disulfide positions. Phantom entries are added for canonical positions
    that should hold a Cys but don't (spec R23 `disulfide_missing`)."""
    cys_records = _collect_cys_records(parsed)
    partner_of = _scan_disulfides(cys_records)

    canonical_positions: dict[str, tuple[int, int]] = (
        CANONICAL_CYS_POSITIONS.get(numbering_scheme, {}) if numbering_scheme else {}
    )
    canonical_keys: set[tuple[str, int]] = {
        (role, pos) for role, positions in canonical_positions.items() for pos in positions
    }
    # Tracks which canonical (role, res_seq) slots are actually filled, so
    # missing-Cys phantom rows below don't duplicate a real hit.
    filled_canonical: set[tuple[str, int]] = set()
    for chain_id, r, _ca, _sg in cys_records:
        role = role_of_chain(chain_id, heavy_chain_id, light_chain_id)
        if role is not None:
            filled_canonical.add((role, r.res_seq))

    hits: list[CysteineHit] = []
    for idx, (chain_id, r, _ca, _sg) in enumerate(cys_records):
        key = (chain_id, f"{r.res_seq}{r.i_code}".strip())
        sasa_info = sasa_lookup.get(key, {})
        role = role_of_chain(chain_id, heavy_chain_id, light_chain_id)
        bonded = partner_of.get(idx) is not None
        hits.append(
            CysteineHit(
                cysClass=_classify_cys(
                    r.res_seq, role, bonded, canonical_keys, canonical_positions
                ),
                sidechainRsasa=sasa_info.get("sideChainRsasa"),
            )
        )

    # Phantom rows for missing canonical Cys (R23).
    for role, (p1, p2) in canonical_positions.items():
        if not (heavy_chain_id if role == "H" else light_chain_id):
            continue
        for pos in (p1, p2):
            if (role, pos) in filled_canonical:
                continue
            hits.append(CysteineHit(cysClass="disulfide_missing", sidechainRsasa=None))

    return hits
