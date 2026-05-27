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
#                          is emitted at the expected position with cysClass
#                          set to disulfide_missing)
#   - cys_extra          : a Cys at any non-canonical position, regardless
#                          of bonding state

import math
from dataclasses import dataclass
from typing import Optional

from structure import CANONICAL_CYS_POSITIONS, role_of_chain


SG_SG_MAX_ANGSTROMS = 3.0
CA_CA_MAX_ANGSTROMS = 7.0


@dataclass
class CysteineHit:
    chainId: str
    resSeq: int
    iCode: str
    resName: str  # always "CYS" for real hits; "-" for phantom missing entries
    chainRole: str  # "H" / "L" / "-" when chain isn't mapped to either
    cysClass: str  # "disulfide" | "disulfide_broken" | "disulfide_missing" | "cys_extra" | "bonded" | "unbonded"
    bondingState: str  # "bonded" | "unbonded" | "missing"
    sasa: Optional[float]
    rsasa: Optional[float]
    sidechainSasa: Optional[float]
    sidechainRsasa: Optional[float]
    partnerChainId: str
    partnerResSeq: Optional[int]
    partnerIcode: str


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
    bonding_state: str,
    canonical_keys: set[tuple[str, int]],
    canonical_positions: dict,
) -> str:
    """R23 four-state classification. Falls back to raw bonding state
    when numbering isn't wired (no role / no canonical positions for the
    scheme), so the table is still useful in the auto-detect-only case."""
    if role is not None and (role, res_seq) in canonical_keys:
        return "disulfide" if bonding_state == "bonded" else "disulfide_broken"
    if role is not None and canonical_positions:
        return "cys_extra"
    return bonding_state


def _phantom_missing_cys(role: str, pos: int, chain_id_for_role: str) -> CysteineHit:
    """Emit a placeholder row for a canonical Cys position the structure
    doesn't actually contain (resName "-" sentinel). Spec R23: missing
    canonical Cys is a developability red flag and needs to appear in
    the cys table even without a real residue to attach to."""
    return CysteineHit(
        chainId=chain_id_for_role,
        resSeq=pos,
        iCode="-",
        resName="-",
        chainRole=role,
        cysClass="disulfide_missing",
        bondingState="missing",
        sasa=None,
        rsasa=None,
        sidechainSasa=None,
        sidechainRsasa=None,
        partnerChainId="-",
        partnerResSeq=None,
        partnerIcode="-",
    )


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

    # Per-scheme canonical positions + the set we test each real Cys against.
    canonical_positions: dict[str, tuple[int, int]] = (
        CANONICAL_CYS_POSITIONS.get(numbering_scheme, {}) if numbering_scheme else {}
    )
    canonical_keys: set[tuple[str, int]] = {
        (role, pos) for role, positions in canonical_positions.items() for pos in positions
    }
    # Used below to skip phantom rows for canonical positions that ARE
    # filled , keyed by (role, res_seq).
    cys_by_role_pos: dict[tuple[str, int], int] = {}
    for idx, (chain_id, r, _ca, _sg) in enumerate(cys_records):
        role = role_of_chain(chain_id, heavy_chain_id, light_chain_id)
        if role is not None:
            cys_by_role_pos[(role, r.res_seq)] = idx

    hits: list[CysteineHit] = []
    for idx, (chain_id, r, _ca, _sg) in enumerate(cys_records):
        key = (chain_id, f"{r.res_seq}{r.i_code}".strip())
        sasa_info = sasa_lookup.get(key, {})
        role = role_of_chain(chain_id, heavy_chain_id, light_chain_id)

        partner_idx = partner_of.get(idx)
        if partner_idx is not None:
            p_chain, p_res, _, _ = cys_records[partner_idx]
            bonding_state = "bonded"
            partner_chain = p_chain
            partner_res_seq: Optional[int] = p_res.res_seq
            partner_icode = p_res.i_code or "-"
        else:
            bonding_state = "unbonded"
            partner_chain = "-"
            partner_res_seq = None
            partner_icode = "-"

        hits.append(
            CysteineHit(
                chainId=chain_id,
                resSeq=r.res_seq,
                iCode=r.i_code or "-",
                resName="CYS",
                chainRole=role or "-",
                cysClass=_classify_cys(
                    r.res_seq, role, bonding_state, canonical_keys, canonical_positions
                ),
                bondingState=bonding_state,
                sasa=sasa_info.get("sasa"),
                rsasa=sasa_info.get("rsasa"),
                sidechainSasa=sasa_info.get("sideChainSasa"),
                sidechainRsasa=sasa_info.get("sideChainRsasa"),
                partnerChainId=partner_chain,
                partnerResSeq=partner_res_seq,
                partnerIcode=partner_icode,
            )
        )

    # Phantom rows for missing canonical Cys (R23).
    for role, (p1, p2) in canonical_positions.items():
        chain_id_for_role = heavy_chain_id if role == "H" else light_chain_id
        if not chain_id_for_role:
            continue
        for pos in (p1, p2):
            if (role, pos) in cys_by_role_pos:
                continue
            hits.append(_phantom_missing_cys(role, pos, chain_id_for_role))

    return hits
