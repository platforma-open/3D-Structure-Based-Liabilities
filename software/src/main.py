import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

import freesasa

from cysteines import detect_cysteines
from diagnostics import check_hallmark_tetrad, cross_check_ssbonds
from metrics import compute_metrics
from motifs import detect_motifs
from parser import parse_pdb
from pframe_writer import AxisSchema, ColumnSchema, chown_paths_to_host, write_pframe
from scoring import compute_developability


# Spec R11 — heavy-atom Ala-X-Ala reference SASAs, re-derived per
# Yang & Blundell 1996 / Shrake-Rupley 1973 (see
# `software/scripts/derive_ala_x_ala_refs.py`). Loaded once at import.
_REFS_PATH = Path(__file__).parent / "ala_x_ala_refs.json"
_AXA_REFS: dict[str, dict[str, float]] = json.loads(_REFS_PATH.read_text())["references"]


def compute_sasa(pdb_path: Path) -> dict[tuple[str, str], dict[str, float]]:
    """Run FreeSASA on the PDB; return dict keyed by (chain_id, residue_number_str)
    mapping to per-residue SASA values. The residue_number_str is FreeSASA's
    residueNumber attribute, which encodes resSeq+insertion code (e.g. "100A").

    rSASA is computed against the block's own heavy-atom Ala-X-Ala references
    (spec R11) rather than FreeSASA's Naccess defaults — `_AXA_REFS` is the
    auditable source of truth. Residues without a reference (HETATMs, ligands,
    non-standard amino acids) get `rsasa = None`.
    """
    structure = freesasa.Structure(str(pdb_path))
    result = freesasa.calc(structure)
    residue_areas = result.residueAreas()

    sasa_lookup: dict[tuple[str, str], dict[str, float]] = {}
    for chain_id, by_res in residue_areas.items():
        for res_number, area in by_res.items():
            ref = _AXA_REFS.get(area.residueType)
            total = _safe_float(area.total)
            side_chain = _safe_float(area.sideChain)
            rsasa = None
            side_rsasa = None
            if ref is not None:
                if total is not None and ref["total"]:
                    rsasa = total / ref["total"]
                if side_chain is not None and ref["sidechain"]:
                    side_rsasa = side_chain / ref["sidechain"]
            sasa_lookup[(chain_id, str(res_number))] = {
                "sasa": total,
                "sideChainSasa": side_chain,
                "rsasa": rsasa,
                "sideChainRsasa": side_rsasa,
            }
    return sasa_lookup


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def chown_to_host(path: Path) -> None:
    """Match output ownership to the bind-mounted workdir's owner so pl-dev's
    post-run MakeCacheReadOnly chmod doesn't fail with EPERM. Silent no-op
    outside Docker."""
    try:
        workdir_stat = os.stat("/workdir")
        os.chown(path, workdir_stat.st_uid, workdir_stat.st_gid)
    except (FileNotFoundError, PermissionError, OSError):
        pass


# Axis values must be non-empty strings — empty axes are rejected by the
# PColumn data layer. 1N8Z and most ImmuneBuilder outputs have no insertion
# codes, so the sentinel applies to every row in practice.
_ICODE_SENTINEL = "-"

# Per-motif PColumn schema. Axes are (chainId, resSeq, iCode, type) — these
# four together uniquely identify a single motif hit (one residue can be
# matched by several patterns). Value columns mirror the JSON report.
_MOTIF_AXES = [
    AxisSchema(id="chainId", type="String"),
    AxisSchema(id="resSeq", type="Long"),
    AxisSchema(id="iCode", type="String"),
    AxisSchema(id="type", type="String"),
]
_MOTIF_COLUMNS = [
    ColumnSchema(id="resName", type="String"),
    ColumnSchema(id="region", type="String"),
    # Spec R18 — absolute SASA in Å² for the chemically-relevant residue,
    # paired with rSASA. Some downstream consumers compare against TAP-style
    # reports that quote raw SASA, so we ship both.
    ColumnSchema(id="sasa", type="Double"),
    ColumnSchema(id="rsasa", type="Double"),
    ColumnSchema(id="exposureFactor", type="Double"),
    ColumnSchema(id="confidence", type="Double"),
    ColumnSchema(id="confidenceGated", type="String"),
    ColumnSchema(id="weightedScore", type="Double"),
    ColumnSchema(id="sequenceRiskClass", type="String"),
    ColumnSchema(id="fixability", type="String"),
]

# String sentinel used in the `region` parquet column when region tagging
# isn't available (chain isn't H/L or no scheme was specified). PColumn
# String axes don't accept empty values; we apply the same convention to
# value columns for consistency.
_REGION_UNKNOWN = "-"

# Per-cysteine PColumn schema. Axes are (chainId, resSeq, iCode) — uniquely
# identifies each Cys residue. Bonded pairs cross-reference each other via
# partner* columns.
_CYS_AXES = [
    AxisSchema(id="chainId", type="String"),
    AxisSchema(id="resSeq", type="Long"),
    AxisSchema(id="iCode", type="String"),
]
_CYS_COLUMNS = [
    ColumnSchema(id="cysClass", type="String"),
    ColumnSchema(id="chainRole", type="String"),
    ColumnSchema(id="bondingState", type="String"),
    ColumnSchema(id="rsasa", type="Double"),
    ColumnSchema(id="sidechainRsasa", type="Double"),
    ColumnSchema(id="sasa", type="Double"),
    ColumnSchema(id="sidechainSasa", type="Double"),
    ColumnSchema(id="partnerChainId", type="String"),
    ColumnSchema(id="partnerResSeq", type="Long"),
    ColumnSchema(id="partnerIcode", type="String"),
]

# Per-structure scalar PFrame (spec R38). One row per structure. The
# `structureId` placeholder axis carries a constant `"static"` value —
# `pt.saveFrameDirect` asserts `len(axes) > 0` even though
# `pframes.processColumn` prepends `[sampleId, scClonotypeKey]` to every
# emitted PColumn. The workflow's `scoresAxesSpec` marks this axis
# `visibility: hidden` so the PlAgDataTable doesn't render it.
_SCORES_AXES = [
    AxisSchema(id="structureId", type="String"),
]
_SCORES_COLUMNS = [
    # Spec R7 mode
    ColumnSchema(id="mode", type="String"),
    # Spec R23 cysteine summary counts
    ColumnSchema(id="extraCysCount", type="Long"),
    ColumnSchema(id="exposedExtraCysCount", type="Long"),
    ColumnSchema(id="brokenCanonicalDisulfideCount", type="Long"),
    ColumnSchema(id="missingCanonicalCysCount", type="Long"),
    # Spec R38 motif counts + composite score + risks
    ColumnSchema(id="surfacedMotifCount", type="Long"),
    ColumnSchema(id="confidenceGatedMotifCount", type="Long"),
    ColumnSchema(id="motifStructuralRiskScore", type="Double"),
    ColumnSchema(id="structuralDevelopabilityScore", type="Double"),
    ColumnSchema(id="structuralDevelopabilityRisk", type="String"),
    ColumnSchema(id="structuralIntegrityRisk", type="String"),
    # Spec R24-R30 surface metrics (sfvcsp / cdrh3Compactness are mode-specific)
    ColumnSchema(id="totalCdrLength", type="Long"),
    ColumnSchema(id="psh", type="Double"),
    ColumnSchema(id="pshPatchCount", type="Long"),
    ColumnSchema(id="ppc", type="Double"),
    ColumnSchema(id="pnc", type="Double"),
    ColumnSchema(id="sfvcsp", type="Double"),
    ColumnSchema(id="cdrh3Compactness", type="Double"),
    # Spec R36 low-confidence-residue fractions
    ColumnSchema(id="totalCdrLengthLowConfidenceResidueFraction", type="Double"),
    ColumnSchema(id="pshLowConfidenceResidueFraction", type="Double"),
    ColumnSchema(id="ppcLowConfidenceResidueFraction", type="Double"),
    ColumnSchema(id="pncLowConfidenceResidueFraction", type="Double"),
    ColumnSchema(id="sfvcspLowConfidenceResidueFraction", type="Double"),
    ColumnSchema(id="cdrh3CompactnessLowConfidenceResidueFraction", type="Double"),
    # Spec R39 threshold flags. Value is "green" / "amber" / "red" / "-"
    # (sentinel when the flag isn't computed in the current mode).
    ColumnSchema(id="totalCdrLengthFlag", type="String"),
    ColumnSchema(id="pshFlag", type="String"),
    ColumnSchema(id="ppcFlag", type="String"),
    ColumnSchema(id="pncFlag", type="String"),
    ColumnSchema(id="sfvcspFlag", type="String"),
    ColumnSchema(id="cdrh3CompactnessFlag", type="String"),
]

# Constant value for the `structureId` placeholder axis (see `_SCORES_AXES`
# comment). Visible in the parquet but hidden in the PlAgDataTable view.
_PLACEHOLDER_STRUCTURE_ID = "static"
# Spec R39 — sentinel used when a flag isn't applicable to the current mode.
_FLAG_SENTINEL = "-"


def _build_scores_row(
    *,
    mode: str,
    motif_hits,
    cys_hits,
    motif_structural_risk_score: float,
    surface_metrics,
    developability,
    rsasa_buried_cutoff: float,
) -> dict:
    """Assemble the single-row dict that becomes the per-structure scores PFrame.

    All the source data already lives in `surface_metrics`, `developability`,
    and the motif / cysteine hit lists — this function is just the spec-
    mandated mapping into one flat dict matching `_SCORES_COLUMNS`. Pulling
    the assembly out keeps `main()` readable and the field-name → source
    correspondence reviewable in one place.

    `surface_metrics` is an empty dict when no scheme/chain mapping was
    provided (R14 fallback); we route every metric field through
    `sm.get(...)` so they cleanly become NULLs in that case.

    `_FLAG_SENTINEL` ("-") goes into the threshold-flag columns when the
    metric is inapplicable in the current mode (e.g. SFvCSP in VHH).
    """
    sm = surface_metrics if isinstance(surface_metrics, dict) and "mode" in surface_metrics else {}
    flags = developability["flags"]

    # R23 — cysteine-class counts. The cys hit list carries the four-state
    # classification; we tally each state into its own PColumn.
    extra_cys = sum(1 for h in cys_hits if h.cysClass == "cys_extra")
    exposed_extra_cys = sum(
        1
        for h in cys_hits
        if h.cysClass == "cys_extra"
        and h.sidechainRsasa is not None
        and h.sidechainRsasa >= rsasa_buried_cutoff
    )
    broken_canonical = sum(1 for h in cys_hits if h.cysClass == "disulfide_broken")
    missing_canonical = sum(1 for h in cys_hits if h.cysClass == "disulfide_missing")

    return {
        # Placeholder axis value; the workflow's `scoresAxesSpec` hides
        # this axis from the PlAgDataTable view. Required because
        # `pt.saveFrameDirect` asserts at least one axis.
        "structureId": _PLACEHOLDER_STRUCTURE_ID,
        "mode": mode,
        # R23 summary counts.
        "extraCysCount": extra_cys,
        "exposedExtraCysCount": exposed_extra_cys,
        "brokenCanonicalDisulfideCount": broken_canonical,
        "missingCanonicalCysCount": missing_canonical,
        # R38 motif counts + composite score + risks.
        "surfacedMotifCount": len(motif_hits),
        "confidenceGatedMotifCount": sum(1 for h in motif_hits if h.confidenceGated == "yes"),
        "motifStructuralRiskScore": motif_structural_risk_score,
        "structuralDevelopabilityScore": developability["structuralDevelopabilityScore"],
        "structuralDevelopabilityRisk": developability["structuralDevelopabilityRisk"],
        "structuralIntegrityRisk": developability["structuralIntegrityRisk"],
        # R24-R30 raw surface metrics (sfvcsp / cdrh3Compactness are mode-specific).
        "totalCdrLength": sm.get("totalCdrLength"),
        "psh": sm.get("psh"),
        "pshPatchCount": sm.get("pshPatchCount"),
        "ppc": sm.get("ppc"),
        "pnc": sm.get("pnc"),
        "sfvcsp": sm.get("sfvcsp"),
        "cdrh3Compactness": sm.get("cdrh3Compactness"),
        # R36 per-metric low-confidence-residue fractions.
        "totalCdrLengthLowConfidenceResidueFraction": sm.get("totalCdrLengthLowConfidenceResidueFraction"),
        "pshLowConfidenceResidueFraction": sm.get("pshLowConfidenceResidueFraction"),
        "ppcLowConfidenceResidueFraction": sm.get("ppcLowConfidenceResidueFraction"),
        "pncLowConfidenceResidueFraction": sm.get("pncLowConfidenceResidueFraction"),
        "sfvcspLowConfidenceResidueFraction": sm.get("sfvcspLowConfidenceResidueFraction"),
        "cdrh3CompactnessLowConfidenceResidueFraction": sm.get("cdrh3CompactnessLowConfidenceResidueFraction"),
        # R39 three-band threshold flags — green/amber/red, or "-" sentinel
        # when the metric is inapplicable in the current mode.
        "totalCdrLengthFlag": flags.get("totalCdrLengthFlag", _FLAG_SENTINEL),
        "pshFlag": flags.get("pshFlag", _FLAG_SENTINEL),
        "ppcFlag": flags.get("ppcFlag", _FLAG_SENTINEL),
        "pncFlag": flags.get("pncFlag", _FLAG_SENTINEL),
        "sfvcspFlag": flags.get("sfvcspFlag", _FLAG_SENTINEL),
        "cdrh3CompactnessFlag": flags.get("cdrh3CompactnessFlag", _FLAG_SENTINEL),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdb", required=True, type=Path)
    ap.add_argument("--motifs-pframe-dir", required=True, type=Path,
                    help="Directory to populate with parquet + .datainfo files "
                         "for the motifs PFrame (consumed by pt.import-dir).")
    ap.add_argument("--cysteines-pframe-dir", required=True, type=Path,
                    help="Directory to populate with parquet + .datainfo files "
                         "for the cysteines PFrame (consumed by pt.import-dir).")
    ap.add_argument("--scores-pframe-dir", required=True, type=Path,
                    help="Directory to populate with parquet + .datainfo files "
                         "for the per-structure scores PFrame (spec R38/R39).")
    # R12: Raybould 2019 canonical cutoff
    ap.add_argument("--rsasa-buried-cutoff", type=float, default=0.075)
    # R10/R14 numbering: scheme + chain role mapping. Optional — when missing,
    # region tagging is null and motif scoring uses neutral weights.
    ap.add_argument("--numbering-scheme", choices=["imgt", "chothia", "kabat"], default=None,
                    help="Numbering scheme for region tagging (R14).")
    ap.add_argument("--chain-h", default=None, help="PDB chain ID treated as the heavy chain.")
    ap.add_argument("--chain-l", default=None, help="PDB chain ID treated as the light chain.")
    # R34: region-aware confidence gating thresholds in Angstroms. Defaults
    # are the spec's calibrated values for ImmuneBuilder error scales.
    ap.add_argument("--fr-conf-thresh", type=float, default=4.0,
                    help="Framework-region confidence gating threshold (Å). Spec R34 default 4.0.")
    ap.add_argument("--cdr-conf-thresh", type=float, default=6.0,
                    help="CDR confidence gating threshold (Å). Spec R34 default 6.0.")
    args = ap.parse_args()

    text = args.pdb.read_text()
    parsed = parse_pdb(text)

    # Spec R7 — chain-count gating. Fail fast before we run FreeSASA on
    # input shapes the block doesn't accept; the failure surfaces back
    # through the workflow's per-row processColumn output so other
    # clonotypes in the batch keep going. Single-chain >180 residues is
    # the canonical "looks like an scFv linker-joined construct" guard
    # (scFv produces malformed surface metrics under ImmuneBuilder's
    # paired-Fv prediction model).
    n_chains = len(parsed.chain_order)
    if n_chains == 0:
        raise ValueError(
            "PDB contains no ATOM records — nothing to analyze (spec R7)"
        )
    if n_chains == 1:
        chain_len = len(parsed.residues_by_chain[parsed.chain_order[0]])
        if chain_len > 180:
            raise ValueError(
                f"Single-chain PDB has {chain_len} residues (>180); "
                f"rejected as suspected scFv (spec R7)"
            )
    if n_chains >= 3:
        raise ValueError(
            f"PDB has {n_chains} chains; this block accepts 1 (VHH/TNP) "
            f"or 2 (paired Fv/TAP) chains only (spec R7)"
        )

    sasa_lookup = compute_sasa(args.pdb)

    # Spec R10 — region tagging needs *some* numbering source. Preferred
    # path is `REMARK 99 PLATFORMA CDR*` records from upstream (`parsed
    # .platforma_cdrs`); fallback is the scheme-aware fixed ranges in
    # `numbering.py:SCHEME_CDR_RANGES` keyed on the user-supplied scheme.
    # If neither is present we fail — without region tagging motif
    # scoring loses its R19 region weights and surface metrics can't
    # define their CDR vicinity, so a silent run would emit garbage.
    has_remark_cdrs = bool(parsed.platforma_cdrs)
    has_scheme = bool(args.numbering_scheme)
    if not has_remark_cdrs and not has_scheme:
        raise ValueError(
            "No numbering source available: PDB has no REMARK 99 PLATFORMA "
            "CDR records and no --numbering-scheme was provided. Region "
            "tagging requires one of the two (spec R10)."
        )
    if not has_remark_cdrs and has_scheme:
        print(
            f"WARN (spec R10): no REMARK 99 PLATFORMA CDR records; falling "
            f"back to scheme-aware fixed ranges for '{args.numbering_scheme}'.",
            file=sys.stderr,
        )

    # Spec R9 — REMARK 99 chain identity is authoritative. When the PDB
    # carries `REMARK 99 PLATFORMA CDR<role><idx> <chain><start>-<chain><end>`
    # records, the chain letter prefix tells us which physical PDB chain
    # is heavy / light, regardless of what the caller passed on the CLI.
    # Falls back to --chain-h / --chain-l (i.e. the user's UI dropdowns)
    # when REMARKs are absent.
    heavy_chain_id = parsed.chain_role_to_pdb_chain.get("H", args.chain_h)
    light_chain_id = parsed.chain_role_to_pdb_chain.get("L", args.chain_l)

    motif_hits = detect_motifs(
        parsed,
        sasa_lookup,
        args.rsasa_buried_cutoff,
        numbering_scheme=args.numbering_scheme,
        heavy_chain_id=heavy_chain_id,
        light_chain_id=light_chain_id,
        fr_confidence_threshold=args.fr_conf_thresh,
        cdr_confidence_threshold=args.cdr_conf_thresh,
    )
    cys_hits = detect_cysteines(
        parsed,
        sasa_lookup,
        numbering_scheme=args.numbering_scheme,
        heavy_chain_id=heavy_chain_id,
        light_chain_id=light_chain_id,
    )

    # Spec R20: motifStructuralRiskScore — sum of non-gated motif weighted
    # scores. Gated motifs (R35) appear in the table for traceability but
    # don't contribute to the aggregate.
    motif_structural_risk_score = sum(
        h.weightedScore for h in motif_hits if h.confidenceGated != "yes"
    )

    # Spec R24-R33 surface developability metrics. Returns {} when no
    # scheme/chain mapping; otherwise a dict keyed by mode + per-metric.
    surface_metrics = compute_metrics(
        parsed,
        sasa_lookup,
        numbering_scheme=args.numbering_scheme,
        heavy_chain_id=heavy_chain_id,
        light_chain_id=light_chain_id,
        rsasa_buried_cutoff=args.rsasa_buried_cutoff,
        fr_conf_thresh=args.fr_conf_thresh,
        cdr_conf_thresh=args.cdr_conf_thresh,
    )

    # Spec R39 / R41 / R41a: threshold flags + composite developability
    # score + categorical risk classifiers.
    developability = compute_developability(
        motif_hits, cys_hits, surface_metrics, args.rsasa_buried_cutoff
    )

    # Spec R37 shape. Mode is settled by the chain-count gate above (R7):
    # only 1 (TNP) or 2 (TAP) chains reach this point.
    mode = "TAP" if n_chains == 2 else "TNP"

    # Defensive checks (spec R21 SSBOND cross-check + R33 hallmark tetrad).
    # The hallmark check needs `mode` so it can warn when the four hallmark
    # residues disagree with chain-count-derived TAP/TNP classification.
    diagnostics = {
        "ssbondCrossCheck": cross_check_ssbonds(parsed.ssbonds, cys_hits),
        "hallmarkTetrad": check_hallmark_tetrad(
            parsed, args.numbering_scheme, heavy_chain_id, chain_count_mode=mode
        ),
    }

    # Diagnostics (R21 SSBOND cross-check, R33 hallmark tetrad) are kept
    # for stderr-side logging callers but no longer surfaced via a JSON
    # report; the per-residue drill-down stack (R37 / R53) was removed
    # from the refreshed spec as out-of-scope. Hold a reference so the
    # variable is not dead code; future stderr emission can reuse it.
    _ = diagnostics

    # PFrame for the spec R38 path. One row per motif hit; axes match
    # _MOTIF_AXES. iCode swapped to sentinel "-" so PColumn axes never see
    # an empty string.
    motif_rows = [
        {
            "chainId": h.chainId,
            "resSeq": h.resSeq,
            "iCode": h.iCode or _ICODE_SENTINEL,
            "type": h.type,
            "resName": h.resName,
            "region": h.region or _REGION_UNKNOWN,
            "sasa": h.sasa,
            "rsasa": h.rsasa,
            "exposureFactor": h.exposureFactor,
            "confidence": h.confidence,
            "confidenceGated": h.confidenceGated,
            "weightedScore": h.weightedScore,
            "sequenceRiskClass": h.sequenceRiskClass,
            "fixability": h.fixability,
        }
        for h in motif_hits
    ]
    written = write_pframe(args.motifs_pframe_dir, motif_rows, _MOTIF_AXES, _MOTIF_COLUMNS)
    chown_paths_to_host(written)

    cys_rows = [
        {
            "chainId": h.chainId,
            "resSeq": h.resSeq,
            "iCode": h.iCode,
            "cysClass": h.cysClass,
            "chainRole": h.chainRole,
            "bondingState": h.bondingState,
            "rsasa": h.rsasa,
            "sidechainRsasa": h.sidechainRsasa,
            "sasa": h.sasa,
            "sidechainSasa": h.sidechainSasa,
            "partnerChainId": h.partnerChainId,
            "partnerResSeq": h.partnerResSeq,
            "partnerIcode": h.partnerIcode,
        }
        for h in cys_hits
    ]
    cys_written = write_pframe(args.cysteines_pframe_dir, cys_rows, _CYS_AXES, _CYS_COLUMNS)
    chown_paths_to_host(cys_written)

    # Spec R23 / R38 / R39 per-structure scalar PFrame. One row per structure,
    # flat layout matching `_SCORES_COLUMNS`. The same scalar data also lives
    # under `report.scores` / `report.surfaceMetrics` / `report.thresholdFlags`
    # in the JSON report above; the PColumn path is what downstream blocks
    # (Lead Selection, etc.) consume.
    scores_row = _build_scores_row(
        mode=mode,
        motif_hits=motif_hits,
        cys_hits=cys_hits,
        motif_structural_risk_score=motif_structural_risk_score,
        surface_metrics=surface_metrics,
        developability=developability,
        rsasa_buried_cutoff=args.rsasa_buried_cutoff,
    )
    scores_written = write_pframe(
        args.scores_pframe_dir, [scores_row], _SCORES_AXES, _SCORES_COLUMNS
    )
    chown_paths_to_host(scores_written)


if __name__ == "__main__":
    main()
