"""Spec R39 threshold flags + R41/R41a composite scoring and risk classifiers.

Thresholds are pinned per spec line 142 (Raybould 2019 Table 2 for Fv) and
spec line 147 (Gordon 2025 / TNP source for VHH). Composite scoring follows
R41's mirror of `compute_developability_score` in the sequence-liabilities
block: fixability_weight × region_weight × exposure for motifs, plus
per-mode flag bumps (red=8, amber=3, green=0), plus the Cys contributions
(8 × exposed_extra + 20 × broken_canonical + 20 × missing_canonical).
"""

from typing import Optional


# R39 Fv thresholds (Raybould 2019 Table 2). Bidirectional metrics return
# "green" / "amber" / "red"; cohortSize is 242 for traceability.
#
# `direction`: "high_bad" — values above amber band are red (most metrics).
#              "low_bad"  — values below amber band are red (SFvCSP).
_FV_THRESHOLDS = {
    "totalCdrLength": {"direction": "high_bad", "amber": (54, 60)},
    # PSH bidirectional: red <83.84 OR >173.85; amber 83.84-100.71 OR 156.20-173.85; green 100.71-156.20
    "psh": {
        "bidirectional": True,
        "green": (100.71, 156.20),
        "amber_lo": (83.84, 100.71),
        "amber_hi": (156.20, 173.85),
    },
    "ppc": {"direction": "high_bad", "amber": (1.25, 3.16)},
    "pnc": {"direction": "high_bad", "amber": (1.84, 3.50)},
    # SFvCSP: more-positive product = better-matched chains. Red <-20.40,
    # amber -20.40..-6.30, green >-6.30.
    "sfvcsp": {"direction": "low_bad", "amber": (-20.40, -6.30)},
}

# R39 VHH thresholds. Spec gives only CDRH3 compactness in full ("green
# 0.82–1.57, amber 0.56–0.82 OR 1.57–1.61, red <0.56 OR >1.61"); the other
# four metrics are pinned at M1 from TNP source. Until M1, default to Fv
# thresholds for the other four — best available proxy.
_VHH_THRESHOLDS = {
    "cdrh3Compactness": {
        "bidirectional": True,
        "green": (0.82, 1.57),
        "amber_lo": (0.56, 0.82),
        "amber_hi": (1.57, 1.61),
    },
}


def _flag_one_sided(value: float, spec: dict) -> str:
    """Three-band: amber within (amber_lo, amber_hi); red on the bad side
    of the band, green on the good side. `direction` picks which side is
    bad — "high_bad" (most metrics) treats values above amber as red,
    "low_bad" (SFvCSP) treats values below amber as red."""
    amber_lo, amber_hi = spec["amber"]
    direction = spec.get("direction", "high_bad")
    if direction == "high_bad":
        if value > amber_hi:
            return "red"
        if value >= amber_lo:
            return "amber"
        return "green"
    # low_bad
    if value < amber_lo:
        return "red"
    if value <= amber_hi:
        return "amber"
    return "green"


def _flag_bidirectional(value: float, spec: dict) -> str:
    g_lo, g_hi = spec["green"]
    if g_lo <= value <= g_hi:
        return "green"
    al_lo, al_hi = spec["amber_lo"]
    if al_lo <= value < al_hi:
        return "amber"
    ah_lo, ah_hi = spec["amber_hi"]
    if ah_lo < value <= ah_hi:
        return "amber"
    return "red"


def _flag_metric(value: float, spec: dict) -> str:
    if spec.get("bidirectional"):
        return _flag_bidirectional(value, spec)
    return _flag_one_sided(value, spec)


def compute_flags(surface_metrics: dict) -> dict[str, str]:
    """Per-metric flag string per R39 thresholds. Returns empty dict when
    `surface_metrics` is empty or missing `mode`."""
    if not surface_metrics or "mode" not in surface_metrics:
        return {}
    mode = surface_metrics["mode"]
    if mode == "TAP":
        thresholds = _FV_THRESHOLDS
    elif mode == "TNP":
        # Fall back to Fv thresholds for the four shared metrics; add VHH-specific.
        thresholds = {**_FV_THRESHOLDS, **_VHH_THRESHOLDS}
    else:
        return {}

    flags: dict[str, str] = {}
    for metric, spec in thresholds.items():
        value = surface_metrics.get(metric)
        if value is None:
            continue
        flags[metric + "Flag"] = _flag_metric(float(value), spec)
    return flags


def _flag_bump(flag: Optional[str]) -> float:
    """R41 metric-flag contribution: red=8.0, amber=3.0, green=0.0."""
    if flag == "red":
        return 8.0
    if flag == "amber":
        return 3.0
    return 0.0


def _cys_class_bump(cys_class: str, sidechain_rsasa: Optional[float], buried_cutoff: float) -> float:
    """R41 Cys contribution.
       exposed_extra_cys: 8.0 each (cys_extra AND surface-exposed)
       broken_canonical:  20.0 each
       missing_canonical: 20.0 each
    """
    if cys_class == "disulfide_broken":
        return 20.0
    if cys_class == "disulfide_missing":
        return 20.0
    if cys_class == "cys_extra":
        if sidechain_rsasa is not None and sidechain_rsasa >= buried_cutoff:
            return 8.0
    return 0.0


def compute_developability(
    motif_hits,
    cys_hits,
    surface_metrics: dict,
    rsasa_buried_cutoff: float,
):
    """R41 + R41a: composite developability score + two categorical risk
    columns. Returns a dict for JSON emission."""

    flags = compute_flags(surface_metrics)

    # R41 motif contribution: sum of non-gated weighted scores (== motifStructuralRiskScore).
    motif_contrib = sum(h.weightedScore for h in motif_hits if h.confidenceGated != "yes")

    # R41 metric flag contribution.
    flag_contrib = sum(_flag_bump(v) for v in flags.values())

    # R41 cysteine contribution.
    cys_contrib = sum(
        _cys_class_bump(h.cysClass, h.sidechainRsasa, rsasa_buried_cutoff)
        for h in cys_hits
    )

    structural_developability_score = motif_contrib + flag_contrib + cys_contrib

    # R41a structuralDevelopabilityRisk over fixable items only.
    # "Fixable" motifs are those in {fixable, easily_fixable}; their highest
    # sequence risk class drives the base level, then promoted by any
    # amber/red metric flag.
    _engineering_fixabilities = ("fixable", "easily_fixable")
    risk_levels = ["None", "Low", "Medium", "High"]
    risk_order = {n: i for i, n in enumerate(risk_levels)}

    def _seq_risk_to_level(rc: str) -> str:
        # Mirror of classify_developability_risk in sequence-liabilities.
        return {"High": "High", "Medium": "Medium", "Low": "Low"}.get(rc, "None")

    base_level = "None"
    for h in motif_hits:
        if h.confidenceGated == "yes":
            continue
        if h.fixability not in _engineering_fixabilities:
            continue
        candidate = _seq_risk_to_level(h.sequenceRiskClass)
        if risk_order[candidate] > risk_order[base_level]:
            base_level = candidate

    has_amber = any(v == "amber" for v in flags.values())
    has_red = any(v == "red" for v in flags.values())
    if has_red and risk_order[base_level] < risk_order["High"]:
        base_level = "High"
    elif has_amber and risk_order[base_level] < risk_order["Medium"]:
        base_level = "Medium"

    # R41a structuralIntegrityRisk: Present if any hard_to_fix / structural
    # item, OR any canonical disulfide broken/missing OR exposed extra Cys.
    structural_present = False
    for h in cys_hits:
        if h.cysClass in ("disulfide_broken", "disulfide_missing"):
            structural_present = True
            break
        if h.cysClass == "cys_extra" and h.sidechainRsasa is not None and h.sidechainRsasa >= rsasa_buried_cutoff:
            structural_present = True
            break
    if not structural_present:
        for h in motif_hits:
            if h.confidenceGated == "yes":
                continue
            if h.fixability in ("hard_to_fix", "structural"):
                structural_present = True
                break
    structural_integrity_risk = "Present" if structural_present else "None"

    return {
        "flags": flags,
        "structuralDevelopabilityScore": structural_developability_score,
        "structuralDevelopabilityRisk": base_level,
        "structuralIntegrityRisk": structural_integrity_risk,
        "components": {
            "motifContribution": motif_contrib,
            "metricFlagContribution": flag_contrib,
            "cysteineContribution": cys_contrib,
        },
    }
