"""Tests for `scoring.py`: threshold flagging (Fv + VHH), the
composite developability score, and categorical risk classification.

All inputs are synthesized dicts and dataclasses , no PDB, no FreeSASA."""

from cysteines import CysteineHit
from motifs import MotifHit

from scoring import compute_developability, compute_flags


def _motif(
    fixability="fixable",
    risk="Medium",
    gated="no",
    weighted_score=2.0,
    region="CDR3",
) -> MotifHit:
    return MotifHit(
        type="N-linked Glycosylation",
        chainId="H",
        resSeq=100,
        iCode="",
        resName="ASN",
        region=region,
        sasa=80.0,
        rsasa=0.5,
        exposed=True,
        exposureFactor=0.9,
        confidence=2.0,
        confidenceGated=gated,
        weightedScore=weighted_score,
        sequenceRiskClass=risk,
        fixability=fixability,
    )


def _cys(cys_class="cys_extra", sidechain_rsasa=0.5) -> CysteineHit:
    return CysteineHit(cysClass=cys_class, sidechainRsasa=sidechain_rsasa)


class TestComputeFlagsFv:
    """Fv thresholds verbatim from Raybould 2019 Table 2."""

    def _fv_metrics(self, **overrides):
        base = {
            "mode": "TAP",
            "totalCdrLength": 50,
            "psh": 130.0,
            "ppc": 1.0,
            "pnc": 1.0,
            "sfvcsp": -5.0,
        }
        base.update(overrides)
        return base

    def test_green_band(self):
        flags = compute_flags(self._fv_metrics())
        assert flags["totalCdrLengthFlag"] == "None"
        assert flags["pshFlag"] == "None"
        assert flags["ppcFlag"] == "None"
        assert flags["pncFlag"] == "None"
        assert flags["sfvcspFlag"] == "None"

    def test_totalCdrLength_one_sided_high_bad(self):
        # amber: 54-60, red: >60
        assert compute_flags(self._fv_metrics(totalCdrLength=55))["totalCdrLengthFlag"] == "Medium"
        assert compute_flags(self._fv_metrics(totalCdrLength=61))["totalCdrLengthFlag"] == "High"

    def test_psh_bidirectional(self):
        # green: 100.71-156.20, amber bands: 83.84-100.71 OR 156.20-173.85,
        # red: <83.84 OR >173.85
        assert compute_flags(self._fv_metrics(psh=90.0))["pshFlag"] == "Medium"
        assert compute_flags(self._fv_metrics(psh=160.0))["pshFlag"] == "Medium"
        assert compute_flags(self._fv_metrics(psh=80.0))["pshFlag"] == "High"
        assert compute_flags(self._fv_metrics(psh=200.0))["pshFlag"] == "High"

    def test_sfvcsp_low_bad(self):
        # amber: -20.40 ≤ SFvCSP ≤ -6.30, red: <-20.40
        assert compute_flags(self._fv_metrics(sfvcsp=-15.0))["sfvcspFlag"] == "Medium"
        assert compute_flags(self._fv_metrics(sfvcsp=-25.0))["sfvcspFlag"] == "High"

    def test_vhh_compactness_not_flagged_in_fv_mode(self):
        """TAP mode doesn't carry a `cdrh3CompactnessFlag` , only VHH does."""
        flags = compute_flags(self._fv_metrics(cdrh3Compactness=1.0))
        assert "cdrh3CompactnessFlag" not in flags


class TestComputeFlagsVhh:
    """VHH thresholds, pinned verbatim from oxpig/TNP `bin/TNP`
    `assign_flag()` (cohortSize 36)."""

    def _vhh_metrics(self, **overrides):
        base = {
            "mode": "TNP",
            "totalCdrLength": 30,
            "psh": 100.0,
            "ppc": 0.2,
            "pnc": 1.0,
            "cdrh3Compactness": 1.2,
        }
        base.update(overrides)
        return base

    def test_green_band(self):
        flags = compute_flags(self._vhh_metrics())
        assert flags["totalCdrLengthFlag"] == "None"
        assert flags["pshFlag"] == "None"
        assert flags["ppcFlag"] == "None"
        assert flags["pncFlag"] == "None"
        assert flags["cdrh3CompactnessFlag"] == "None"

    def test_totalCdrLength_bidirectional(self):
        # green: 25-36, amber: 20-24 OR 37-39, red: <20 OR >39
        assert compute_flags(self._vhh_metrics(totalCdrLength=22))["totalCdrLengthFlag"] == "Medium"
        assert compute_flags(self._vhh_metrics(totalCdrLength=38))["totalCdrLengthFlag"] == "Medium"
        assert compute_flags(self._vhh_metrics(totalCdrLength=18))["totalCdrLengthFlag"] == "High"
        assert compute_flags(self._vhh_metrics(totalCdrLength=45))["totalCdrLengthFlag"] == "High"

    def test_psh_bidirectional(self):
        # green: 79.60-126.82, amber: 73.40-79.59 OR 126.83-155.47,
        # red: <73.40 OR >155.47
        assert compute_flags(self._vhh_metrics(psh=76.0))["pshFlag"] == "Medium"
        assert compute_flags(self._vhh_metrics(psh=140.0))["pshFlag"] == "Medium"
        assert compute_flags(self._vhh_metrics(psh=70.0))["pshFlag"] == "High"
        assert compute_flags(self._vhh_metrics(psh=160.0))["pshFlag"] == "High"

    def test_ppc_one_sided_high_bad(self):
        # amber: 0.39-1.18, red: >1.18
        assert compute_flags(self._vhh_metrics(ppc=0.5))["ppcFlag"] == "Medium"
        assert compute_flags(self._vhh_metrics(ppc=1.5))["ppcFlag"] == "High"

    def test_compactness_bidirectional(self):
        # green: 0.82-1.56, amber: 0.56-0.81 OR 1.57-1.61, red: <0.56 OR >1.61
        assert compute_flags(self._vhh_metrics(cdrh3Compactness=0.70))["cdrh3CompactnessFlag"] == "Medium"
        assert compute_flags(self._vhh_metrics(cdrh3Compactness=1.59))["cdrh3CompactnessFlag"] == "Medium"
        assert compute_flags(self._vhh_metrics(cdrh3Compactness=0.40))["cdrh3CompactnessFlag"] == "High"
        assert compute_flags(self._vhh_metrics(cdrh3Compactness=1.80))["cdrh3CompactnessFlag"] == "High"

    def test_sfvcsp_not_flagged_in_vhh_mode(self):
        """SFvCSP is Fv-only; the VHH thresholds dict doesn't carry it."""
        flags = compute_flags(self._vhh_metrics(sfvcsp=-30.0))
        assert "sfvcspFlag" not in flags


class TestEmptyAndInvalidMetrics:
    def test_empty_metrics_returns_empty_flags(self):
        assert compute_flags({}) == {}

    def test_missing_mode_returns_empty_flags(self):
        assert compute_flags({"psh": 100.0}) == {}

    def test_unknown_mode_returns_empty_flags(self):
        assert compute_flags({"mode": "scFv", "psh": 100.0}) == {}

    def test_none_value_skipped(self):
        flags = compute_flags({"mode": "TAP", "psh": None, "ppc": 1.0})
        assert "pshFlag" not in flags
        assert "ppcFlag" in flags


class TestCompositeDevelopability:
    """Composite score: motifContribution + metricFlagContribution +
    cysContribution. Each tested in isolation, then combined."""

    def _fv_green(self, **overrides):
        base = {
            "mode": "TAP",
            "totalCdrLength": 50,
            "psh": 130.0,
            "ppc": 1.0,
            "pnc": 1.0,
            "sfvcsp": -5.0,
        }
        base.update(overrides)
        return base

    def test_zero_when_nothing_triggers(self):
        result = compute_developability([], [], self._fv_green(), 0.075)
        assert result["structuralDevelopabilityScore"] == 0.0
        assert result["structuralDevelopabilityRisk"] == "None"
        assert result["structuralIntegrityRisk"] == "None"

    def test_motif_contribution_only(self):
        motif = _motif(weighted_score=3.0)
        result = compute_developability([motif], [], self._fv_green(), 0.075)
        assert result["structuralDevelopabilityScore"] == 3.0

    def test_gated_motifs_excluded(self):
        """Confidence-gated motifs stay in the table but don't
        contribute to motifStructuralRiskScore."""
        confident = _motif(weighted_score=2.0, gated="no")
        gated = _motif(weighted_score=5.0, gated="yes")
        result = compute_developability([confident, gated], [], self._fv_green(), 0.075)
        # Only the confident motif's score lands in the composite.
        assert result["structuralDevelopabilityScore"] == 2.0

    def test_metric_flag_bumps(self):
        """High=8, Medium=3, None=0 per flag. No motifs / cys → score
        equals the flag-bump sum directly."""
        # psh red, totalCdrLength amber, others green
        metrics = self._fv_green(psh=200.0, totalCdrLength=55)
        result = compute_developability([], [], metrics, 0.075)
        # red(psh)=8 + amber(totalCdrLength)=3 = 11
        assert result["structuralDevelopabilityScore"] == 11.0

    def test_cysteine_contributions(self):
        """Cys weights: exposed_extra=8, broken=20, missing=20. No
        motifs / flag bumps (Fv-green metrics) → score equals the cys sum."""
        exposed_extra = _cys("cys_extra", sidechain_rsasa=0.5)
        buried_extra = _cys("cys_extra", sidechain_rsasa=0.01)
        broken = _cys("disulfide_broken", sidechain_rsasa=0.3)
        missing = _cys("disulfide_missing", sidechain_rsasa=None)
        result = compute_developability(
            [], [exposed_extra, buried_extra, broken, missing], self._fv_green(), 0.075
        )
        # buried_extra contributes 0 (sidechainRsasa < cutoff).
        # 8 (exposed) + 0 (buried) + 20 (broken) + 20 (missing) = 48
        assert result["structuralDevelopabilityScore"] == 48.0


class TestR41aRiskClassification:
    """structuralDevelopabilityRisk over engineering-fixable
    items, promoted by amber/red flags. structuralIntegrityRisk Present
    when any cys defect or hard_to_fix/structural motif exists."""

    def _fv_metrics(self, **overrides):
        base = {
            "mode": "TAP",
            "totalCdrLength": 50,
            "psh": 130.0,
            "ppc": 1.0,
            "pnc": 1.0,
            "sfvcsp": -5.0,
        }
        base.update(overrides)
        return base

    def test_no_motifs_no_flags_yields_none(self):
        result = compute_developability([], [], self._fv_metrics(), 0.075)
        assert result["structuralDevelopabilityRisk"] == "None"

    def test_high_motif_risk_floors_at_motif_level(self):
        motif = _motif(fixability="fixable", risk="High")
        result = compute_developability([motif], [], self._fv_metrics(), 0.075)
        assert result["structuralDevelopabilityRisk"] == "High"

    def test_amber_flag_promotes_to_medium(self):
        result = compute_developability([], [], self._fv_metrics(totalCdrLength=55), 0.075)
        assert result["structuralDevelopabilityRisk"] == "Medium"

    def test_red_flag_promotes_to_high(self):
        result = compute_developability([], [], self._fv_metrics(psh=200.0), 0.075)
        assert result["structuralDevelopabilityRisk"] == "High"

    def test_non_fixable_motifs_dont_count_for_dev_risk(self):
        """Structural motifs are tracked separately under integrityRisk; they
        DON'T bump structuralDevelopabilityRisk's base level."""
        motif = _motif(fixability="structural", risk="High")
        result = compute_developability([motif], [], self._fv_metrics(), 0.075)
        assert result["structuralDevelopabilityRisk"] == "None"

    def test_gated_motifs_dont_count_for_dev_risk(self):
        motif = _motif(fixability="fixable", risk="High", gated="yes")
        result = compute_developability([motif], [], self._fv_metrics(), 0.075)
        assert result["structuralDevelopabilityRisk"] == "None"

    def test_integrity_risk_triggered_by_broken_disulfide(self):
        cys = _cys("disulfide_broken", sidechain_rsasa=0.3)
        result = compute_developability([], [cys], self._fv_metrics(), 0.075)
        assert result["structuralIntegrityRisk"] == "Present"

    def test_integrity_risk_triggered_by_missing_canonical(self):
        cys = _cys("disulfide_missing", sidechain_rsasa=None)
        result = compute_developability([], [cys], self._fv_metrics(), 0.075)
        assert result["structuralIntegrityRisk"] == "Present"

    def test_integrity_risk_triggered_by_exposed_extra_cys(self):
        cys = _cys("cys_extra", sidechain_rsasa=0.5)
        result = compute_developability([], [cys], self._fv_metrics(), 0.075)
        assert result["structuralIntegrityRisk"] == "Present"

    def test_integrity_risk_not_triggered_by_buried_extra_cys(self):
        cys = _cys("cys_extra", sidechain_rsasa=0.01)
        result = compute_developability([], [cys], self._fv_metrics(), 0.075)
        assert result["structuralIntegrityRisk"] == "None"

    def test_integrity_risk_triggered_by_structural_motif(self):
        motif = _motif(fixability="structural", risk="High")
        result = compute_developability([motif], [], self._fv_metrics(), 0.075)
        assert result["structuralIntegrityRisk"] == "Present"

    def test_gated_structural_motif_doesnt_trigger_integrity_risk(self):
        """Gated motifs are excluded from scoring side; integrity check
        also skips them (same `confidenceGated == "yes"` guard)."""
        motif = _motif(fixability="structural", risk="High", gated="yes")
        result = compute_developability([motif], [], self._fv_metrics(), 0.075)
        assert result["structuralIntegrityRisk"] == "None"
