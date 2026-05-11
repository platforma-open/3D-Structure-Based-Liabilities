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

from numbering import CANONICAL_CYS_POSITIONS, role_of_chain


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
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def _bonding_test(ca1, sg1, ca2, sg2) -> bool:
    return _dist(sg1, sg2) <= SG_SG_MAX_ANGSTROMS and _dist(ca1, ca2) <= CA_CA_MAX_ANGSTROMS


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
    that should hold a Cys but don't."""

    # Collect Cys with the two atoms we need.
    cys_records: list[tuple[str, object, object, object]] = []  # (chain, res, ca, sg)
    for chain_id in parsed.chain_order:
        for r in parsed.residues_by_chain[chain_id]:
            if r.res_name != "CYS":
                continue
            ca = r.atom("CA")
            sg = r.atom("SG")
            if ca is None or sg is None:
                continue
            cys_records.append((chain_id, r, ca, sg))

    # Pairwise bonding scan. First-match wins on ambiguous geometry.
    partner_of: dict[int, int] = {}
    for i in range(len(cys_records)):
        for j in range(i + 1, len(cys_records)):
            _, _, ca_i, sg_i = cys_records[i]
            _, _, ca_j, sg_j = cys_records[j]
            if _bonding_test(ca_i, sg_i, ca_j, sg_j):
                if i not in partner_of and j not in partner_of:
                    partner_of[i] = j
                    partner_of[j] = i

    # Build index for canonical lookup: (chain_role, res_seq) -> cys_record index.
    cys_by_role_pos: dict[tuple[str, int], int] = {}
    for idx, (chain_id, r, _ca, _sg) in enumerate(cys_records):
        role = role_of_chain(chain_id, heavy_chain_id, light_chain_id)
        if role is not None:
            cys_by_role_pos[(role, r.res_seq)] = idx

    # Per-scheme expected canonical positions.
    canonical_positions: dict[str, tuple[int, int]] = {}
    if numbering_scheme and numbering_scheme in CANONICAL_CYS_POSITIONS:
        canonical_positions = CANONICAL_CYS_POSITIONS[numbering_scheme]
    canonical_keys: set[tuple[str, int]] = set()
    for role, (p1, p2) in canonical_positions.items():
        canonical_keys.add((role, p1))
        canonical_keys.add((role, p2))

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
            partner_res_seq = p_res.res_seq
            partner_icode = p_res.i_code or "-"
        else:
            bonding_state = "unbonded"
            partner_chain = "-"
            partner_res_seq = None
            partner_icode = "-"

        # Four-state classification: only meaningful when role is known AND
        # we know the canonical positions for that role/scheme.
        cys_class: str
        if role is not None and (role, r.res_seq) in canonical_keys:
            if bonding_state == "bonded":
                cys_class = "disulfide"
            else:
                cys_class = "disulfide_broken"
        elif role is not None and canonical_positions:
            cys_class = "cys_extra"
        else:
            cys_class = bonding_state  # fall back to raw bonding state

        hits.append(
            CysteineHit(
                chainId=chain_id,
                resSeq=r.res_seq,
                iCode=r.i_code or "-",
                resName="CYS",
                chainRole=role or "-",
                cysClass=cys_class,
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

    # Phantom rows for missing canonical Cys — only when canonical positions
    # are known and the corresponding chain ID is mapped.
    for role, (p1, p2) in canonical_positions.items():
        chain_id_for_role = heavy_chain_id if role == "H" else light_chain_id
        if not chain_id_for_role:
            continue
        for pos in (p1, p2):
            if (role, pos) in cys_by_role_pos:
                continue
            hits.append(
                CysteineHit(
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
            )

    return hits
