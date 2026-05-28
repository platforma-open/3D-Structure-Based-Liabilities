"""Spec R39 threshold flags + R41/R41a composite scoring and risk classifiers.

Thresholds live in `data/thresholds.json` per spec line 142 (`R39`) so the
calibration source + cohortSize travel with the values. Loaded once at
import time; runtime threshold checks read from the parsed dict.
Fv values come from Raybould 2019 Table 2 (cohortSize 242). VHH values
come from the TNP source paper's `assign_flag()` function in
oxpig/TNP `bin/TNP` (cohortSize 36). Composite scoring (R41) mirrors
`compute_developability_score` in the sequence-liabilities block:
fixability_weight × region_weight × exposure for motifs, plus per-mode
flag bumps (red=8, amber=3, green=0), plus the Cys contributions
(8 × exposed_extra + 20 × broken_canonical + 20 × missing_canonical).
"""

import json
from pathlib import Path
from typing import Optional

_THRESHOLDS_PATH = Path(__file__).parent / "data" / "thresholds.json"


def _load_thresholds() -> tuple[dict, dict]:
    """Load Fv + VHH threshold dicts from `data/thresholds.json`. Returns
    `(fv, vhh)` keyed by metric name with the same shape the runtime
    flaggers consume (`bidirectional` + `green`/`amber_lo`/`amber_hi` for
    bidirectional metrics; `direction` + `amber` for one-sided)."""
    raw = json.loads(_THRESHOLDS_PATH.read_text())
    return raw["fv"]["thresholds"], raw["vhh"]["thresholds"]


# Loaded at import. Tuples are produced from the JSON arrays so downstream
# code can treat them as fixed-arity bands (unchanged from the previous
# inline-constants version).
_FV_THRESHOLDS_RAW, _VHH_THRESHOLDS_RAW = _load_thresholds()


def _coerce_band_tuples(thresholds: dict) -> dict:
    """JSON gives us `[lo, hi]` arrays; the rest of the file works on
    `(lo, hi)` tuples for consistency with the previous inline definitions
    and easier unpacking."""
    out = {}
    for metric, spec in thresholds.items():
        coerced = dict(spec)
        for key in ("amber", "green", "amber_lo", "amber_hi"):
            if key in coerced and isinstance(coerced[key], list):
                coerced[key] = tuple(coerced[key])
        out[metric] = coerced
    return out


_FV_THRESHOLDS = _coerce_band_tuples(_FV_THRESHOLDS_RAW)
_VHH_THRESHOLDS = _coerce_band_tuples(_VHH_THRESHOLDS_RAW)


def _flag_one_sided(value: float, spec: dict) -> str:
    """Three-band: amber within (amber_lo, amber_hi); red on the bad side
    of the band, green on the good side. `direction` picks which side is
    bad , "high_bad" (most metrics) treats values above amber as red,
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
        # VHH is now fully populated from TNP source `assign_flag()`; use
        # its own thresholds end-to-end (no Fv fallback needed).
        thresholds = _VHH_THRESHOLDS
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


# R41a , engineering-grade fixability tiers + the four-step risk ladder.
# `_ENGINEERING_FIXABILITIES` is the same set the sequence-liabilities
# block uses for `classify_developability_risk` (motifs we can credibly
# fix without a sequence redesign).
_ENGINEERING_FIXABILITIES = ("fixable", "easily_fixable")
_RISK_LEVELS = ["None", "Low", "Medium", "High"]
_RISK_ORDER = {n: i for i, n in enumerate(_RISK_LEVELS)}


def _seq_risk_to_level(rc: str) -> str:
    """R41a sequence-side risk class → ladder level. Identity for the four
    known values; anything else (None, unexpected labels) falls through to
    "None" so an upstream regression can't silently inflate a candidate."""
    return rc if rc in _RISK_LEVELS else "None"


def _developability_risk(motif_hits, flags: dict[str, str]) -> str:
    """R41a , over engineering-fixable, non-gated motifs only:
       1. Take the highest sequenceRiskClass among them as the base level.
       2. Promote to Medium if ANY metric flag is amber.
       3. Promote to High if ANY metric flag is red.
    Mirror of `classify_developability_risk` in sequence-liabilities."""
    base_level = "None"
    for h in motif_hits:
        if h.confidenceGated == "yes":
            continue
        if h.fixability not in _ENGINEERING_FIXABILITIES:
            continue
        candidate = _seq_risk_to_level(h.sequenceRiskClass)
        if _RISK_ORDER[candidate] > _RISK_ORDER[base_level]:
            base_level = candidate

    if any(v == "red" for v in flags.values()) and _RISK_ORDER[base_level] < _RISK_ORDER["High"]:
        return "High"
    if (
        any(v == "amber" for v in flags.values())
        and _RISK_ORDER[base_level] < _RISK_ORDER["Medium"]
    ):
        return "Medium"
    return base_level


def _has_integrity_issue(motif_hits, cys_hits, rsasa_buried_cutoff: float) -> bool:
    """R41a structuralIntegrityRisk , Present iff at least one of:
       • a canonical disulfide is broken or missing entirely (cys side),
       • an extra Cys is surface-exposed (free thiol → covalent aggregation risk),
       • a non-gated motif lives in the {hard_to_fix, structural} tier.
    Any one is enough , short-circuits as soon as it finds a trigger."""
    for h in cys_hits:
        if h.cysClass in ("disulfide_broken", "disulfide_missing"):
            return True
        if (
            h.cysClass == "cys_extra"
            and h.sidechainRsasa is not None
            and h.sidechainRsasa >= rsasa_buried_cutoff
        ):
            return True
    for h in motif_hits:
        if h.confidenceGated == "yes":
            continue
        if h.fixability in ("hard_to_fix", "structural"):
            return True
    return False


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

    base_level = _developability_risk(motif_hits, flags)
    structural_integrity_risk = (
        "Present" if _has_integrity_issue(motif_hits, cys_hits, rsasa_buried_cutoff) else "None"
    )

    return {
        "flags": flags,
        "structuralDevelopabilityScore": structural_developability_score,
        "structuralDevelopabilityRisk": base_level,
        "structuralIntegrityRisk": structural_integrity_risk,
    }
