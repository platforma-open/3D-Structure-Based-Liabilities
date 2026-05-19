"""Spec R24-R33 surface developability metrics.

Fv (TAP) — Raybould 2019:
  R24  totalCdrLength  : sum of CDR loop lengths from numbering
  R25  PSH             : Σ H(R₁)·H(R₂)/r² over surface CDR-vicinity pairs
                         within 7.5 Å heavy-atom distance, no type restriction
  R26  PPC             : same pair formula with |Q(R₁)·Q(R₂)|, K/R/H signs only
  R26  PNC             : same with D/E signs only
  R28  SFvCSP          : [Σ_RH Q(RH)] × [Σ_RL Q(RL)] over surface-exposed
                         whole-V-domain residues (NOT CDR-restricted)

VHH (TNP) — Gordon 2025:
  R29  totalCdrLength  : sum of three CDR lengths (single chain)
  R31  PSH/PPC/PNC     : same algorithms applied to one chain, but with
                         same-type-pair restriction (PSH: H-H pairs only;
                         PPC: K/R/H-K/R/H pairs only; PNC: D/E-D/E pairs only)
  R30  CDRH3 compact.  : cdrh3Length / ‖centroid(CDR3 Cα) − centroid(anchor Cα)‖
                         IMGT anchors 102, 103, 118, 119

Per R34/R36 the residue's local positional uncertainty is the parser's
mean heavy-atom B-factor, gated region-aware against `frConfidenceGatingThreshold`
(framework) or `cdrConfidenceGatingThreshold` (CDR). For each metric we
emit a parallel `<metric>LowConfidenceResidueFraction` Double — fraction
of *contributing* residues that exceed their region threshold (R36).
"""

import math
from dataclasses import dataclass
from typing import Optional

from biochem import (
    charge_of,
    detect_salt_bridges,
    get_hydrophobicity_scale,
    hydrophobicity_of,
)
from numbering import (
    CDRH3_COMPACTNESS_ANCHORS_IMGT,
    SCHEME_CDR_RANGES,
    SCHEME_VDOMAIN_END,
    region_for,
)


# Spec R25 pair filter: heavy-atom distance < 7.5 Å AND both residues are
# surface-exposed (rSASA ≥ buried cutoff).
_PAIR_MAX_ANGSTROMS = 7.5

# Spec R25 CDR-vicinity: surface-exposed CDR/anchor residues + other surface
# residues within this heavy-atom distance to any CDR residue.
_CDR_VICINITY_ANGSTROMS = 4.0


@dataclass
class FvMetrics:
    """R24-R28 (Fv mode) — emitted only when 2 mapped chains and Fv-shape input."""
    totalCdrLength: int
    psh: float
    pshPatchCount: int
    ppc: float
    pnc: float
    sfvcsp: Optional[float]  # None when VHH mode


@dataclass
class VhhMetrics:
    """R29-R33 (VHH mode) — single chain, type-restricted patches, CDRH3 compactness."""
    totalCdrLength: int
    psh: float
    pshPatchCount: int
    ppc: float
    pnc: float
    cdrh3Compactness: Optional[float]


def _heavy_atom_min_distance(r_a, r_b) -> float:
    best = float("inf")
    for a in r_a.atoms:
        for b in r_b.atoms:
            d = math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)
            if d < best:
                best = d
    return best


def _cdr_vicinity_residues(residues, regions, rsasa_lookup, buried_cutoff):
    """R25 CDR vicinity: surface-exposed CDR residues + surface residues
    with a heavy atom within _CDR_VICINITY_ANGSTROMS of any CDR residue.
    """
    cdr_residues = [r for r, region in zip(residues, regions) if region in ("CDR1", "CDR2", "CDR3")]
    if not cdr_residues:
        return []

    in_vicinity_idx: set[int] = set()
    for i, r in enumerate(residues):
        if regions[i] in ("CDR1", "CDR2", "CDR3"):
            in_vicinity_idx.add(i)
            continue
        # Surface-exposed?
        rsasa = rsasa_lookup.get(i)
        if rsasa is None or rsasa < buried_cutoff:
            continue
        for cr in cdr_residues:
            if _heavy_atom_min_distance(r, cr) <= _CDR_VICINITY_ANGSTROMS:
                in_vicinity_idx.add(i)
                break

    # Filter to surface-exposed.
    out = []
    for i in sorted(in_vicinity_idx):
        rsasa = rsasa_lookup.get(i)
        if rsasa is not None and rsasa >= buried_cutoff:
            out.append(i)
    return out


def _residue_pair_sum(
    pair_indices: list[int],
    residues,
    aa_letters: list[str],
    weight_fn,
    same_type_pred=None,
):
    """Generic pair-sum: Σ w(R₁) · w(R₂) / r² over surface CDR-vicinity
    residue pairs within 7.5 Å. `same_type_pred(aa1, aa2)` lets VHH mode
    restrict to same-type pairs. Also returns the set of unified-index
    residues that contributed at least one non-zero pair (R36 confidence
    fraction denominator)."""
    total = 0.0
    patch_count = 0
    contributors: set[int] = set()
    for ai_idx in range(len(pair_indices)):
        for bj_idx in range(ai_idx + 1, len(pair_indices)):
            i = pair_indices[ai_idx]
            j = pair_indices[bj_idx]
            a_letter = aa_letters[i]
            b_letter = aa_letters[j]
            wa = weight_fn(i, a_letter)
            wb = weight_fn(j, b_letter)
            if wa == 0.0 or wb == 0.0:
                continue
            if same_type_pred is not None and not same_type_pred(a_letter, b_letter):
                continue
            d = _heavy_atom_min_distance(residues[i], residues[j])
            if d <= 0 or d > _PAIR_MAX_ANGSTROMS:
                continue
            contribution = wa * wb / (d * d)
            total += contribution
            patch_count += 1
            contributors.add(i)
            contributors.add(j)
    return total, patch_count, contributors


def _mean_b_factor(residue) -> Optional[float]:
    """Residue mean heavy-atom B-factor (per R34). None when no atoms carry it."""
    if not residue.atoms:
        return None
    vals = [a.b_factor for a in residue.atoms if a.b_factor > 0]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _low_conf_fraction(
    contributor_indices,
    residues,
    regions,
    fr_thresh: float,
    cdr_thresh: float,
) -> Optional[float]:
    """R36: fraction of *contributing* residues whose mean B-factor exceeds
    the region-aware threshold. None when no residue carries a B-factor
    (the JSON-side reader can drop the field on the UI). Empty contributor
    set returns None as well."""
    indices = list(contributor_indices)
    if not indices:
        return None
    total = 0
    low_conf = 0
    for i in indices:
        b = _mean_b_factor(residues[i])
        if b is None:
            continue
        region = regions[i]
        thresh = cdr_thresh if region in ("CDR1", "CDR2", "CDR3") else fr_thresh
        total += 1
        if b > thresh:
            low_conf += 1
    if total == 0:
        return None
    return low_conf / total


def _vdomain_surface_residues(
    chain_id,
    residues,
    aa_letters,
    rsasa_lookup,
    role,
    scheme,
    buried_cutoff,
):
    """Whole-V-domain surface-exposed residues for SFvCSP (R28). Range
    bounded by SCHEME_VDOMAIN_END."""
    v_end = SCHEME_VDOMAIN_END.get(scheme, {}).get(role) if scheme else None
    out = []
    for i, r in enumerate(residues):
        if v_end is not None and r.res_seq > v_end:
            continue
        rsasa = rsasa_lookup.get(i)
        if rsasa is None or rsasa < buried_cutoff:
            continue
        out.append(i)
    return out


def _three_one(res_name: str) -> str:
    # local copy of the 3→1 letter mapping (avoid circular import with motifs.py)
    return _AA_THREE_TO_ONE.get(res_name, "X")


_AA_THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def _hydrophobic(aa: str) -> bool:
    return aa in ("A", "I", "L", "M", "F", "V", "P", "W")


def _positive(aa: str) -> bool:
    return aa in ("K", "R", "H")


def _negative(aa: str) -> bool:
    return aa in ("D", "E")


def _total_cdr_length_for_chain(residues, regions) -> int:
    return sum(1 for region in regions if region in ("CDR1", "CDR2", "CDR3"))


def _cdrh3_compactness_imgt(residues, chain_id_to_residues, h_chain_id, scheme) -> Optional[float]:
    """R30 compactness: cdrh3Length / ρ where ρ = ‖centroid(CDR3 Cα, IMGT
    105-117) − centroid(anchor Cα, IMGT 102+103+118+119)‖. IMGT-anchored;
    returns None for non-IMGT schemes (Chothia/Kabat lack a defined anchor
    set in the spec)."""
    if scheme != "imgt" or not h_chain_id:
        return None
    residues = chain_id_to_residues.get(h_chain_id)
    if not residues:
        return None
    cdr3_range = SCHEME_CDR_RANGES["imgt"]["H"]["CDR3"]
    cdr3_ca = []
    anchor_ca = []
    for r in residues:
        ca = r.atom("CA")
        if ca is None:
            continue
        if cdr3_range[0] <= r.res_seq <= cdr3_range[1]:
            cdr3_ca.append(ca)
        elif r.res_seq in CDRH3_COMPACTNESS_ANCHORS_IMGT:
            anchor_ca.append(ca)
    if not cdr3_ca or not anchor_ca:
        return None
    cx = sum(a.x for a in cdr3_ca) / len(cdr3_ca)
    cy = sum(a.y for a in cdr3_ca) / len(cdr3_ca)
    cz = sum(a.z for a in cdr3_ca) / len(cdr3_ca)
    ax = sum(a.x for a in anchor_ca) / len(anchor_ca)
    ay = sum(a.y for a in anchor_ca) / len(anchor_ca)
    az = sum(a.z for a in anchor_ca) / len(anchor_ca)
    rho = math.sqrt((cx - ax) ** 2 + (cy - ay) ** 2 + (cz - az) ** 2)
    if rho == 0:
        return None
    return len(cdr3_ca) / rho


def _build_chain_context(
    parsed,
    chain_id,
    sasa_lookup,
    salt_bridge_keys: set,
):
    """Pre-compute per-residue helpers used by every metric on a chain."""
    residues = parsed.residues_by_chain.get(chain_id, [])
    aa_letters = [_three_one(r.res_name) for r in residues]
    rsasa_lookup: dict[int, float] = {}
    in_bridge: dict[int, bool] = {}
    for i, r in enumerate(residues):
        key = (chain_id, f"{r.res_seq}{r.i_code}".strip())
        info = sasa_lookup.get(key, {})
        rs = info.get("rsasa")
        if rs is not None:
            rsasa_lookup[i] = rs
        in_bridge[i] = (chain_id, r.res_seq, r.i_code or "") in salt_bridge_keys
    return residues, aa_letters, rsasa_lookup, in_bridge


def compute_metrics(
    parsed,
    sasa_lookup,
    numbering_scheme: Optional[str],
    heavy_chain_id: Optional[str],
    light_chain_id: Optional[str],
    rsasa_buried_cutoff: float,
    fr_conf_thresh: float = 4.0,
    cdr_conf_thresh: float = 6.0,
    hydrophobicity_scale: str = "kd",
):
    """Returns a dict suitable for JSON emission. Includes Fv metrics when
    both heavy + light are mapped; VHH metrics when only heavy is mapped
    (and chain length sanity-checks). Returns empty dict when neither.

    Type-restricted patches: R31 (VHH mode) only counts same-type pairs.
    Fv mode (R25/R26) counts all pairs with non-zero weights.

    `hydrophobicity_scale` (R48): selects the per-residue lookup used by PSH.
    Defaults to "kd" (Kyte-Doolittle, the Raybould 2019 setting).
    """
    if not numbering_scheme:
        return {}

    salt_bridges = detect_salt_bridges(parsed)
    chain_id_to_residues = dict(parsed.residues_by_chain)
    h_scale, h_glycine = get_hydrophobicity_scale(hydrophobicity_scale)

    h_present = heavy_chain_id and heavy_chain_id in chain_id_to_residues
    l_present = light_chain_id and light_chain_id in chain_id_to_residues
    if not h_present and not l_present:
        return {}

    if h_present and l_present:
        mode = "TAP"
    elif h_present and not l_present:
        mode = "TNP"
    else:
        return {}

    def _chain_metrics(chain_id, role, type_restricted_psh):
        residues, aa_letters, rsasa_lookup, in_bridge = _build_chain_context(
            parsed, chain_id, sasa_lookup, salt_bridges
        )
        regions = [region_for(role, r.res_seq, numbering_scheme, parsed.platforma_cdrs) for r in residues]
        cdr_vic = _cdr_vicinity_residues(residues, regions, rsasa_lookup, rsasa_buried_cutoff)

        def h_weight(i, aa):
            v = hydrophobicity_of(aa, in_bridge.get(i, False), h_scale, h_glycine)
            return v if v is not None else 0.0

        def pos_charge_abs(i, aa):
            c = charge_of(aa, in_bridge.get(i, False))
            return c if c > 0 else 0.0

        def neg_charge_abs(i, aa):
            c = charge_of(aa, in_bridge.get(i, False))
            return -c if c < 0 else 0.0

        psh, psh_patches, psh_contrib = _residue_pair_sum(
            cdr_vic, residues, aa_letters, h_weight,
            same_type_pred=(lambda a, b: _hydrophobic(a) and _hydrophobic(b)) if type_restricted_psh else None,
        )
        ppc, _, ppc_contrib = _residue_pair_sum(
            cdr_vic, residues, aa_letters, pos_charge_abs,
            same_type_pred=(lambda a, b: _positive(a) and _positive(b)) if type_restricted_psh else None,
        )
        pnc, _, pnc_contrib = _residue_pair_sum(
            cdr_vic, residues, aa_letters, neg_charge_abs,
            same_type_pred=(lambda a, b: _negative(a) and _negative(b)) if type_restricted_psh else None,
        )
        total_cdr = _total_cdr_length_for_chain(residues, regions)
        return (total_cdr, psh, psh_patches, ppc, pnc,
                psh_contrib, ppc_contrib, pnc_contrib,
                residues, aa_letters, rsasa_lookup, in_bridge, regions)

    out: dict = {"mode": mode}

    if mode == "TAP":
        # Combine H and L into a single CDR-vicinity / pair pool — but the
        # spec defines PSH/PPC/PNC over the *Fv* (both chains together).
        # We compute per-chain CDR vicinities, then merge for inter-chain
        # pair contributions.
        (h_total_cdr, _, _, _, _,
         _, _, _, h_res, h_aa, h_rsasa, h_bridge, h_regions) = _chain_metrics(heavy_chain_id, "H", False)
        (l_total_cdr, _, _, _, _,
         _, _, _, l_res, l_aa, l_rsasa, l_bridge, l_regions) = _chain_metrics(light_chain_id, "L", False)

        # Build a unified residue list for the Fv (H then L) and re-derive
        # CDR-vicinity over the joined list so cross-chain pairs are counted.
        residues = h_res + l_res
        aa_letters = h_aa + l_aa
        rsasa_lookup: dict[int, float] = {}
        in_bridge: dict[int, bool] = {}
        regions: list[Optional[str]] = h_regions + l_regions
        for i in range(len(h_res)):
            if i in h_rsasa:
                rsasa_lookup[i] = h_rsasa[i]
            in_bridge[i] = h_bridge.get(i, False)
        offset = len(h_res)
        for i in range(len(l_res)):
            if i in l_rsasa:
                rsasa_lookup[offset + i] = l_rsasa[i]
            in_bridge[offset + i] = l_bridge.get(i, False)

        cdr_vic = _cdr_vicinity_residues(residues, regions, rsasa_lookup, rsasa_buried_cutoff)

        def h_weight(i, aa):
            v = hydrophobicity_of(aa, in_bridge.get(i, False), h_scale, h_glycine)
            return v if v is not None else 0.0

        def pos_charge_abs(i, aa):
            c = charge_of(aa, in_bridge.get(i, False))
            return c if c > 0 else 0.0

        def neg_charge_abs(i, aa):
            c = charge_of(aa, in_bridge.get(i, False))
            return -c if c < 0 else 0.0

        psh, psh_patches, psh_contrib = _residue_pair_sum(cdr_vic, residues, aa_letters, h_weight)
        ppc, _, ppc_contrib = _residue_pair_sum(cdr_vic, residues, aa_letters, pos_charge_abs)
        pnc, _, pnc_contrib = _residue_pair_sum(cdr_vic, residues, aa_letters, neg_charge_abs)

        # SFvCSP: whole V-domain product of H and L surface-exposed charges
        h_v_surf = _vdomain_surface_residues(
            heavy_chain_id, h_res, h_aa, h_rsasa, "H", numbering_scheme, rsasa_buried_cutoff
        )
        l_v_surf = _vdomain_surface_residues(
            light_chain_id, l_res, l_aa, l_rsasa, "L", numbering_scheme, rsasa_buried_cutoff
        )
        h_q = sum(charge_of(h_aa[i], h_bridge.get(i, False)) for i in h_v_surf)
        l_q = sum(charge_of(l_aa[i], l_bridge.get(i, False)) for i in l_v_surf)
        sfvcsp = h_q * l_q

        # R36 contributing-residue sets. totalCdrLength: every CDR residue.
        # SFvCSP: V-domain surface residues with non-zero charge (the only
        # residues that affect the H_q × L_q product).
        cdr_indices = [i for i, region in enumerate(regions) if region in ("CDR1", "CDR2", "CDR3")]
        sfvcsp_contrib = set()
        for i in h_v_surf:
            if charge_of(h_aa[i], h_bridge.get(i, False)) != 0.0:
                sfvcsp_contrib.add(i)
        for i in l_v_surf:
            if charge_of(l_aa[i], l_bridge.get(i, False)) != 0.0:
                sfvcsp_contrib.add(offset + i)

        out.update({
            "totalCdrLength": h_total_cdr + l_total_cdr,
            "psh": psh,
            "pshPatchCount": psh_patches,
            "ppc": ppc,
            "pnc": pnc,
            "sfvcsp": sfvcsp,
            "totalCdrLengthLowConfidenceResidueFraction":
                _low_conf_fraction(cdr_indices, residues, regions, fr_conf_thresh, cdr_conf_thresh),
            "pshLowConfidenceResidueFraction":
                _low_conf_fraction(psh_contrib, residues, regions, fr_conf_thresh, cdr_conf_thresh),
            "ppcLowConfidenceResidueFraction":
                _low_conf_fraction(ppc_contrib, residues, regions, fr_conf_thresh, cdr_conf_thresh),
            "pncLowConfidenceResidueFraction":
                _low_conf_fraction(pnc_contrib, residues, regions, fr_conf_thresh, cdr_conf_thresh),
            "sfvcspLowConfidenceResidueFraction":
                _low_conf_fraction(sfvcsp_contrib, residues, regions, fr_conf_thresh, cdr_conf_thresh),
        })

    elif mode == "TNP":
        (h_total_cdr, psh, psh_patches, ppc, pnc,
         psh_contrib, ppc_contrib, pnc_contrib,
         h_res, h_aa, h_rsasa, h_bridge, h_regions) = _chain_metrics(heavy_chain_id, "H", True)
        compactness = _cdrh3_compactness_imgt(
            None, chain_id_to_residues, heavy_chain_id, numbering_scheme
        )
        cdr_indices = [i for i, region in enumerate(h_regions) if region in ("CDR1", "CDR2", "CDR3")]
        # CDRH3 compactness contributors: every CDR3 residue + the IMGT
        # anchor residues (all are framework-adjacent or in CDR3).
        compactness_contrib: set[int] = set()
        if numbering_scheme == "imgt":
            cdr3_range = SCHEME_CDR_RANGES["imgt"]["H"]["CDR3"]
            for i, r in enumerate(h_res):
                if cdr3_range[0] <= r.res_seq <= cdr3_range[1]:
                    compactness_contrib.add(i)
                elif r.res_seq in CDRH3_COMPACTNESS_ANCHORS_IMGT:
                    compactness_contrib.add(i)
        out.update({
            "totalCdrLength": h_total_cdr,
            "psh": psh,
            "pshPatchCount": psh_patches,
            "ppc": ppc,
            "pnc": pnc,
            "cdrh3Compactness": compactness,
            "totalCdrLengthLowConfidenceResidueFraction":
                _low_conf_fraction(cdr_indices, h_res, h_regions, fr_conf_thresh, cdr_conf_thresh),
            "pshLowConfidenceResidueFraction":
                _low_conf_fraction(psh_contrib, h_res, h_regions, fr_conf_thresh, cdr_conf_thresh),
            "ppcLowConfidenceResidueFraction":
                _low_conf_fraction(ppc_contrib, h_res, h_regions, fr_conf_thresh, cdr_conf_thresh),
            "pncLowConfidenceResidueFraction":
                _low_conf_fraction(pnc_contrib, h_res, h_regions, fr_conf_thresh, cdr_conf_thresh),
            "cdrh3CompactnessLowConfidenceResidueFraction":
                _low_conf_fraction(compactness_contrib, h_res, h_regions, fr_conf_thresh, cdr_conf_thresh),
        })

    return out
