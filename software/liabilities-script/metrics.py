"""Spec R24-R33 surface developability metrics + R15a salt-bridge prep.

Section 1 carries the Raybould 2019 / Gordon 2025 hydrophobicity and
charge constants plus the R15a salt-bridge detector that runs before
charge assignment. Section 2 is the patch detector + per-mode metric
implementations.

Fv (TAP) , Raybould 2019:
  R24  totalCdrLength  : sum of CDR loop lengths from numbering
  R25  PSH             : Σ H(R₁)·H(R₂)/r² over surface CDR-vicinity pairs
                         within 7.5 Å heavy-atom distance, no type restriction
  R26  PPC             : same pair formula with |Q(R₁)·Q(R₂)|, K/R/H signs only
  R26  PNC             : same with D/E signs only
  R28  SFvCSP          : [Σ_RH Q(RH)] × [Σ_RL Q(RL)] over surface-exposed
                         whole-V-domain residues (NOT CDR-restricted)

VHH (TNP) , Gordon 2025:
  R29  totalCdrLength  : sum of three CDR lengths (single chain)
  R31  PSH/PPC/PNC     : same algorithms applied to one chain, but with
                         same-type-pair restriction (PSH: H-H pairs only;
                         PPC: K/R/H-K/R/H pairs only; PNC: D/E-D/E pairs only)
  R30  CDRH3 compact.  : cdrh3Length / ‖centroid(CDR3 Cα) − centroid(anchor Cα)‖
                         IMGT anchors 102, 103, 118, 119

Per R34/R36 the residue's local positional uncertainty is the parser's
mean heavy-atom B-factor, gated region-aware against `frConfidenceGatingThreshold`
(framework) or `cdrConfidenceGatingThreshold` (CDR). For each metric we
emit a parallel `<metric>LowConfidenceResidueFraction` Double , fraction
of *contributing* residues that exceed their region threshold (R36).
"""

import math
from pathlib import Path
from typing import Optional

from structure import (
    AA_THREE_TO_ONE,
    CDRH3_COMPACTNESS_ANCHORS_IMGT,
    Residue,
    SCHEME_CDR_RANGES,
    SCHEME_VDOMAIN_END,
    region_for,
)


# ---------------------------------------------------------------------------
# Section 1: biochemistry constants + R15a salt-bridge detection
# ---------------------------------------------------------------------------

# Kyte-Doolittle hydrophobicity values loaded from `data/Hydrophobics.txt`
# (KD 1982 raw values, one residue per line as `<letter><whitespace><value>`).
# Raybould 2019 PSH (R25) is defined on KD min-max-normalized to [1.0, 2.0];
# the spec locks this in at the Concept level so there is no scale selector.
_HYDRO_PATH = Path(__file__).parent / "data" / "Hydrophobics.txt"


def _load_kd_raw(path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        out[parts[0]] = float(parts[1])
    return out


def _minmax_to_range(raw: dict[str, float], lo: float, hi: float) -> dict[str, float]:
    rmin = min(raw.values())
    rmax = max(raw.values())
    span = rmax - rmin
    return {aa: lo + (v - rmin) / span * (hi - lo) for aa, v in raw.items()}


_KD_RAW = _load_kd_raw(_HYDRO_PATH)
KD_HYDROPHOBICITY: dict[str, float] = _minmax_to_range(_KD_RAW, 1.0, 2.0)
GLYCINE_HYDROPHOBICITY: float = KD_HYDROPHOBICITY["G"]


# R26 charge assignment per Raybould 2019. H carries 0.1 (rounded from the
# literal H-H Henderson-Hasselbalch contribution at physiological pH).
CHARGES: dict[str, float] = {
    "D": -1.0, "E": -1.0,
    "K": 1.0, "R": 1.0,
    "H": 0.1,
}

# Side-chain heavy atoms that participate in the salt-bridge test (R15a).
SALT_BRIDGE_DONOR_ATOMS: dict[str, tuple[str, ...]] = {
    "LYS": ("NZ",),
    "ARG": ("NH1", "NH2", "NE"),
}
SALT_BRIDGE_ACCEPTOR_ATOMS: dict[str, tuple[str, ...]] = {
    "ASP": ("OD1", "OD2"),
    "GLU": ("OE1", "OE2"),
}
SALT_BRIDGE_MAX_ANGSTROMS = 3.2


def _atom_dist(a, b) -> float:
    return math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))


def _centroid(atoms) -> tuple[float, float, float]:
    n = len(atoms)
    return (
        sum(a.x for a in atoms) / n,
        sum(a.y for a in atoms) / n,
        sum(a.z for a in atoms) / n,
    )


def _weight_fns(in_bridge: dict):
    """Build the three PSH / PPC / PNC weight closures over a shared
    `in_bridge` map (R15a: salt-bridged residues take the glycine
    hydrophobicity and zero charge). The same three are needed by both
    `_chain_metrics` (per-chain, VHH mode) and the TAP-mode Fv pool
    built from H+L; centralising avoids triple-duplicating them."""
    def hydrophobicity(i, aa):
        v = hydrophobicity_of(aa, in_bridge.get(i, False), KD_HYDROPHOBICITY, GLYCINE_HYDROPHOBICITY)
        return v if v is not None else 0.0

    def pos_charge_abs(i, aa):
        c = charge_of(aa, in_bridge.get(i, False))
        return c if c > 0 else 0.0

    def neg_charge_abs(i, aa):
        c = charge_of(aa, in_bridge.get(i, False))
        return -c if c < 0 else 0.0

    return hydrophobicity, pos_charge_abs, neg_charge_abs


def detect_salt_bridges(parsed) -> set[tuple[str, int, str]]:
    """Walk every K/R + D/E pair, return the set of residue keys that are in
    a salt bridge. R15a uses N+ ↔ O- atom-pair distance ≤ 3.2 Å. Returned
    keys are (chain_id, res_seq, i_code). Both partners are marked.
    """
    donors: list[tuple[str, Residue, object]] = []
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
    for _dc, dr, da in donors:
        for _ac, ar, aa_atom in acceptors:
            if _atom_dist(da, aa_atom) <= SALT_BRIDGE_MAX_ANGSTROMS:
                in_bridge.add((_dc, dr.res_seq, dr.i_code or ""))
                in_bridge.add((_ac, ar.res_seq, ar.i_code or ""))
    return in_bridge


def hydrophobicity_of(
    aa_letter: str,
    in_salt_bridge: bool,
    scale: dict[str, float] = KD_HYDROPHOBICITY,
    glycine_value: float = GLYCINE_HYDROPHOBICITY,
) -> Optional[float]:
    """R15a: residues engaged in a salt bridge get the scale's glycine
    value so they don't contribute the hydrophobicity of their full
    charged side chain."""
    if in_salt_bridge:
        return glycine_value
    return scale.get(aa_letter)


def charge_of(aa_letter: str, in_salt_bridge: bool) -> float:
    """R26 charge lookup. R15a zeroes residues already engaged in a salt
    bridge so they don't count toward PPC/PNC/SFvCSP."""
    if in_salt_bridge:
        return 0.0
    return CHARGES.get(aa_letter, 0.0)


# ---------------------------------------------------------------------------
# Section 2: patch detector + per-mode metric implementations
# ---------------------------------------------------------------------------


# Spec R25 pair filter: heavy-atom distance < 7.5 Å AND both residues are
# surface-exposed (rSASA ≥ buried cutoff).
_PAIR_MAX_ANGSTROMS = 7.5

# Spec R25 CDR-vicinity: surface-exposed CDR/anchor residues + other surface
# residues within this heavy-atom distance to any CDR residue.
_CDR_VICINITY_ANGSTROMS = 4.0


def _heavy_atom_min_distance(r_a, r_b) -> float:
    return min(
        math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))
        for a in r_a.atoms
        for b in r_b.atoms
    )


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


def _hydrophobic(aa: str) -> bool:
    return aa in ("A", "I", "L", "M", "F", "V", "P", "W")


def _positive(aa: str) -> bool:
    return aa in ("K", "R", "H")


def _negative(aa: str) -> bool:
    return aa in ("D", "E")


def _total_cdr_length_for_chain(residues, regions) -> int:
    return sum(1 for region in regions if region in ("CDR1", "CDR2", "CDR3"))


def _cdrh3_compactness_imgt(
    residues,
    chain_id_to_residues,
    h_chain_id,
    scheme,
    upstream_cdrh3_length: Optional[int] = None,
) -> Optional[float]:
    """R30 compactness: cdrh3Length / ρ where ρ = ‖centroid(CDR3 Cα, IMGT
    105-117) − centroid(anchor Cα, IMGT 102+103+118+119)‖. IMGT-anchored;
    returns None for non-IMGT schemes (Chothia/Kabat lack a defined anchor
    set in the spec). When `upstream_cdrh3_length` is provided (R5/R29) it
    is used as the numerator; otherwise the in-block CDR3 Cα count is."""
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
    rho = math.dist(_centroid(cdr3_ca), _centroid(anchor_ca))
    if rho == 0:
        return None
    numerator = upstream_cdrh3_length if upstream_cdrh3_length is not None else len(cdr3_ca)
    return numerator / rho


def _build_chain_context(
    parsed,
    chain_id,
    sasa_lookup,
    salt_bridge_keys: set,
):
    """Pre-compute per-residue helpers used by every metric on a chain."""
    residues = parsed.residues_by_chain.get(chain_id, [])
    aa_letters = [AA_THREE_TO_ONE.get(r.res_name, "X") for r in residues]
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
    upstream_cdrh3_length: Optional[int] = None,
):
    """Returns a dict suitable for JSON emission. Includes Fv metrics when
    both heavy + light are mapped; VHH metrics when only heavy is mapped
    (and chain length sanity-checks). Returns empty dict when neither.

    Type-restricted patches: R31 (VHH mode) only counts same-type pairs.
    Fv mode (R25/R26) counts all pairs with non-zero weights.
    """
    if not numbering_scheme:
        return {}

    salt_bridges = detect_salt_bridges(parsed)
    chain_id_to_residues = dict(parsed.residues_by_chain)

    # R7 mode dispatch: heavy must be mapped (TNP = VHH heavy-only;
    # TAP = paired Fv with light also mapped). Light-only is an
    # antigen-chain / mislabelled-input case; no metrics emitted.
    h_present = heavy_chain_id and heavy_chain_id in chain_id_to_residues
    l_present = light_chain_id and light_chain_id in chain_id_to_residues
    if not h_present:
        return {}
    mode = "TAP" if l_present else "TNP"

    def _chain_ctx(chain_id, role):
        """Per-chain residue list + rSASA / salt-bridge / region tagging.
        Cheap; called once per mapped chain."""
        residues, aa_letters, rsasa_lookup, in_bridge = _build_chain_context(
            parsed, chain_id, sasa_lookup, salt_bridges
        )
        regions = [
            region_for(role, r.res_seq, numbering_scheme, parsed.platforma_cdrs)
            for r in residues
        ]
        total_cdr = _total_cdr_length_for_chain(residues, regions)
        return residues, aa_letters, rsasa_lookup, in_bridge, regions, total_cdr

    if mode == "TNP":
        return _compute_tnp(
            heavy_chain_id, numbering_scheme, rsasa_buried_cutoff,
            fr_conf_thresh, cdr_conf_thresh, upstream_cdrh3_length,
            chain_id_to_residues, _chain_ctx,
        )
    return _compute_tap(
        heavy_chain_id, light_chain_id, numbering_scheme,
        rsasa_buried_cutoff, fr_conf_thresh, cdr_conf_thresh, _chain_ctx,
    )


def _bundle_low_conf_fractions(
    contributors: dict,
    residues,
    regions,
    fr_conf_thresh: float,
    cdr_conf_thresh: float,
) -> dict:
    """R36 fractions per metric. `contributors` maps `<metric>` to its
    contributing-residue index set; output keys are
    `<metric>LowConfidenceResidueFraction`. Pulled out so each mode-
    specific helper finishes with one loop instead of five identical
    `_low_conf_fraction(...)` calls."""
    return {
        f"{name}LowConfidenceResidueFraction": _low_conf_fraction(
            indices, residues, regions, fr_conf_thresh, cdr_conf_thresh,
        )
        for name, indices in contributors.items()
    }


def _compute_tnp(
    heavy_chain_id,
    numbering_scheme,
    rsasa_buried_cutoff,
    fr_conf_thresh,
    cdr_conf_thresh,
    upstream_cdrh3_length,
    chain_id_to_residues,
    chain_ctx,
):
    """VHH branch: type-restricted PSH/PPC/PNC on one chain + CDRH3 compactness."""
    h_res, h_aa, h_rsasa, h_bridge, h_regions, h_total_cdr = chain_ctx(heavy_chain_id, "H")
    cdr_vic = _cdr_vicinity_residues(h_res, h_regions, h_rsasa, rsasa_buried_cutoff)
    h_weight, pos_charge_abs, neg_charge_abs = _weight_fns(h_bridge)

    psh, psh_patches, psh_contrib = _residue_pair_sum(
        cdr_vic, h_res, h_aa, h_weight,
        same_type_pred=lambda a, b: _hydrophobic(a) and _hydrophobic(b),
    )
    ppc, _, ppc_contrib = _residue_pair_sum(
        cdr_vic, h_res, h_aa, pos_charge_abs,
        same_type_pred=lambda a, b: _positive(a) and _positive(b),
    )
    pnc, _, pnc_contrib = _residue_pair_sum(
        cdr_vic, h_res, h_aa, neg_charge_abs,
        same_type_pred=lambda a, b: _negative(a) and _negative(b),
    )
    compactness = _cdrh3_compactness_imgt(
        None, chain_id_to_residues, heavy_chain_id, numbering_scheme,
        upstream_cdrh3_length=upstream_cdrh3_length,
    )
    cdr_indices = [i for i, r in enumerate(h_regions) if r in ("CDR1", "CDR2", "CDR3")]
    # CDRH3 compactness contributors: every CDR3 residue + IMGT anchors.
    compactness_contrib: set[int] = set()
    if numbering_scheme == "imgt":
        cdr3_lo, cdr3_hi = SCHEME_CDR_RANGES["imgt"]["H"]["CDR3"]
        for i, r in enumerate(h_res):
            if cdr3_lo <= r.res_seq <= cdr3_hi or r.res_seq in CDRH3_COMPACTNESS_ANCHORS_IMGT:
                compactness_contrib.add(i)

    out = {
        "mode": "TNP",
        "totalCdrLength": h_total_cdr,
        "psh": psh, "pshPatchCount": psh_patches,
        "ppc": ppc, "pnc": pnc,
        "cdrh3Compactness": compactness,
    }
    out.update(_bundle_low_conf_fractions(
        {
            "totalCdrLength": cdr_indices,
            "psh": psh_contrib,
            "ppc": ppc_contrib,
            "pnc": pnc_contrib,
            "cdrh3Compactness": compactness_contrib,
        },
        h_res, h_regions, fr_conf_thresh, cdr_conf_thresh,
    ))
    return out


def _compute_tap(
    heavy_chain_id,
    light_chain_id,
    numbering_scheme,
    rsasa_buried_cutoff,
    fr_conf_thresh,
    cdr_conf_thresh,
    chain_ctx,
):
    """Fv branch: PSH/PPC/PNC over a unified H+L residue pool (cross-chain
    pairs counted) plus SFvCSP product over the whole V-domain.

    Unified-index convention (H residues first, then L):
        unified[0 : len(h_res)]                     → heavy residue i
        unified[offset : offset + len(l_res)]       → light residue (i - offset)
      where `offset = len(h_res)`.
    """
    h_res, h_aa, h_rsasa, h_bridge, h_regions, h_total_cdr = chain_ctx(heavy_chain_id, "H")
    l_res, l_aa, l_rsasa, l_bridge, l_regions, l_total_cdr = chain_ctx(light_chain_id, "L")

    # Merge per-chain contexts under unified indices.
    residues = h_res + l_res
    aa_letters = h_aa + l_aa
    regions: list[Optional[str]] = h_regions + l_regions
    rsasa_lookup: dict[int, float] = {**h_rsasa}
    in_bridge: dict[int, bool] = {i: h_bridge.get(i, False) for i in range(len(h_res))}
    offset = len(h_res)
    for i in range(len(l_res)):
        if i in l_rsasa:
            rsasa_lookup[offset + i] = l_rsasa[i]
        in_bridge[offset + i] = l_bridge.get(i, False)

    cdr_vic = _cdr_vicinity_residues(residues, regions, rsasa_lookup, rsasa_buried_cutoff)
    h_weight, pos_charge_abs, neg_charge_abs = _weight_fns(in_bridge)
    psh, psh_patches, psh_contrib = _residue_pair_sum(cdr_vic, residues, aa_letters, h_weight)
    ppc, _, ppc_contrib = _residue_pair_sum(cdr_vic, residues, aa_letters, pos_charge_abs)
    pnc, _, pnc_contrib = _residue_pair_sum(cdr_vic, residues, aa_letters, neg_charge_abs)

    # SFvCSP: whole-V-domain product of H and L surface-exposed charges.
    h_v_surf = _vdomain_surface_residues(
        heavy_chain_id, h_res, h_aa, h_rsasa, "H", numbering_scheme, rsasa_buried_cutoff
    )
    l_v_surf = _vdomain_surface_residues(
        light_chain_id, l_res, l_aa, l_rsasa, "L", numbering_scheme, rsasa_buried_cutoff
    )
    h_q = sum(charge_of(h_aa[i], h_bridge.get(i, False)) for i in h_v_surf)
    l_q = sum(charge_of(l_aa[i], l_bridge.get(i, False)) for i in l_v_surf)
    sfvcsp = h_q * l_q

    # R36 contributors: SFvCSP is non-zero-charge V-domain residues.
    cdr_indices = [i for i, r in enumerate(regions) if r in ("CDR1", "CDR2", "CDR3")]
    sfvcsp_contrib: set[int] = set()
    for i in h_v_surf:
        if charge_of(h_aa[i], h_bridge.get(i, False)) != 0.0:
            sfvcsp_contrib.add(i)
    for i in l_v_surf:
        if charge_of(l_aa[i], l_bridge.get(i, False)) != 0.0:
            sfvcsp_contrib.add(offset + i)

    out = {
        "mode": "TAP",
        "totalCdrLength": h_total_cdr + l_total_cdr,
        "psh": psh, "pshPatchCount": psh_patches,
        "ppc": ppc, "pnc": pnc,
        "sfvcsp": sfvcsp,
    }
    out.update(_bundle_low_conf_fractions(
        {
            "totalCdrLength": cdr_indices,
            "psh": psh_contrib,
            "ppc": ppc_contrib,
            "pnc": pnc_contrib,
            "sfvcsp": sfvcsp_contrib,
        },
        residues, regions, fr_conf_thresh, cdr_conf_thresh,
    ))
    return out
