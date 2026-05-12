import argparse
import json
import os
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


def compute_sasa(pdb_path: Path) -> dict[tuple[str, str], dict[str, float]]:
    """Run FreeSASA on the PDB; return dict keyed by (chain_id, residue_number_str)
    mapping to per-residue SASA values. The residue_number_str is FreeSASA's
    residueNumber attribute, which encodes resSeq+insertion code (e.g. "100A").
    rSASA values use FreeSASA's heavy-atom Ala-X-Ala reference (NaN for residues
    where no reference exists, e.g. ligands)."""
    structure = freesasa.Structure(str(pdb_path))
    result = freesasa.calc(structure)
    residue_areas = result.residueAreas()

    sasa_lookup: dict[tuple[str, str], dict[str, float]] = {}
    for chain_id, by_res in residue_areas.items():
        for res_number, area in by_res.items():
            sasa_lookup[(chain_id, str(res_number))] = {
                "sasa": _safe_float(area.total),
                "sideChainSasa": _safe_float(area.sideChain),
                "rsasa": _safe_float(area.relativeTotal),
                "sideChainRsasa": _safe_float(area.relativeSideChain),
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
# `structureId` axis is a placeholder until upstream provides a clonotype
# key via PrimaryRef (R1-R6). R23 summary counts, R38 motif/score scalars,
# R24-R30 surface metrics, R36 low-conf fractions, R39 threshold flags
# all live here. Workflow side annotates `*Flag` columns with
# `pl7.app/isScore: "true"` (R40); raw metrics ship as plain features.
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

# Placeholder axis value for the scores PColumn — replaced by the upstream
# clonotype key once a PrimaryRef-emitting structure-prediction block lands.
_PLACEHOLDER_STRUCTURE_ID = "static"
# Spec R39 — sentinel used when a flag isn't applicable to the current mode.
_FLAG_SENTINEL = "-"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdb", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
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
    sasa_lookup = compute_sasa(args.pdb)

    chains = []
    for chain_id in parsed.chain_order:
        residues = []
        for r in parsed.residues_by_chain[chain_id]:
            res_key = (chain_id, f"{r.res_seq}{r.i_code}".strip())
            sasa_info = sasa_lookup.get(res_key, {})
            residues.append(
                {
                    "resSeq": r.res_seq,
                    "iCode": r.i_code,
                    "resName": r.res_name,
                    "sasa": sasa_info.get("sasa"),
                    "rsasa": sasa_info.get("rsasa"),
                    "sideChainSasa": sasa_info.get("sideChainSasa"),
                    "sideChainRsasa": sasa_info.get("sideChainRsasa"),
                }
            )
        chains.append({"id": chain_id, "residues": residues})

    motif_hits = detect_motifs(
        parsed,
        sasa_lookup,
        args.rsasa_buried_cutoff,
        numbering_scheme=args.numbering_scheme,
        heavy_chain_id=args.chain_h,
        light_chain_id=args.chain_l,
        fr_confidence_threshold=args.fr_conf_thresh,
        cdr_confidence_threshold=args.cdr_conf_thresh,
    )
    cys_hits = detect_cysteines(
        parsed,
        sasa_lookup,
        numbering_scheme=args.numbering_scheme,
        heavy_chain_id=args.chain_h,
        light_chain_id=args.chain_l,
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
        heavy_chain_id=args.chain_h,
        light_chain_id=args.chain_l,
        rsasa_buried_cutoff=args.rsasa_buried_cutoff,
        fr_conf_thresh=args.fr_conf_thresh,
        cdr_conf_thresh=args.cdr_conf_thresh,
    )

    # Spec R39 / R41 / R41a: threshold flags + composite developability
    # score + categorical risk classifiers.
    developability = compute_developability(
        motif_hits, cys_hits, surface_metrics, args.rsasa_buried_cutoff
    )

    # Spec R37 shape. Mode auto-detected from chain count (R7): we don't
    # error on 3+ chains here (the spec says reject), only mark "complex"
    # so dev structures like 1N8Z (Fab + antigen) still produce outputs.
    mode = {0: "empty", 1: "TNP", 2: "TAP"}.get(len(parsed.chain_order), "complex")

    # Defensive checks (spec R21 SSBOND cross-check + R33 hallmark tetrad).
    diagnostics = {
        "ssbondCrossCheck": cross_check_ssbonds(parsed.ssbonds, cys_hits),
        "hallmarkTetrad": check_hallmark_tetrad(
            parsed, args.numbering_scheme, args.chain_h
        ),
    }

    report = {
        "numberingScheme": args.numbering_scheme,
        "mode": mode,
        "motifs": [asdict(h) for h in motif_hits],
        "cysteines": [asdict(h) for h in cys_hits],
        "chains": chains,
        "scores": {
            "motifStructuralRiskScore": motif_structural_risk_score,
            "confidenceGatedMotifCount": sum(
                1 for h in motif_hits if h.confidenceGated == "yes"
            ),
            "surfacedMotifCount": len(motif_hits),
            "structuralDevelopabilityScore": developability["structuralDevelopabilityScore"],
            "structuralDevelopabilityRisk": developability["structuralDevelopabilityRisk"],
            "structuralIntegrityRisk": developability["structuralIntegrityRisk"],
        },
        "surfaceMetrics": surface_metrics,
        "thresholdFlags": developability["flags"],
        "developabilityComponents": developability["components"],
        "diagnostics": diagnostics,
    }
    args.output.write_text(json.dumps(report, indent=2))
    chown_to_host(args.output)

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

    # Spec R23 / R38 / R39 per-structure scalar PFrame. R23 summary counts
    # are derived here from cys_hits; the rest of the row is the same data
    # that's already in the JSON `scores` / `surfaceMetrics` / `thresholdFlags`.
    flags = developability["flags"]
    sm = surface_metrics if isinstance(surface_metrics, dict) and "mode" in surface_metrics else {}
    extra_cys = sum(1 for h in cys_hits if h.cysClass == "cys_extra")
    exposed_extra_cys = sum(
        1 for h in cys_hits
        if h.cysClass == "cys_extra"
        and h.sidechainRsasa is not None
        and h.sidechainRsasa >= args.rsasa_buried_cutoff
    )
    broken_canonical = sum(1 for h in cys_hits if h.cysClass == "disulfide_broken")
    missing_canonical = sum(1 for h in cys_hits if h.cysClass == "disulfide_missing")
    scores_row = {
        "structureId": _PLACEHOLDER_STRUCTURE_ID,
        "mode": mode,
        "extraCysCount": extra_cys,
        "exposedExtraCysCount": exposed_extra_cys,
        "brokenCanonicalDisulfideCount": broken_canonical,
        "missingCanonicalCysCount": missing_canonical,
        "surfacedMotifCount": len(motif_hits),
        "confidenceGatedMotifCount": sum(
            1 for h in motif_hits if h.confidenceGated == "yes"
        ),
        "motifStructuralRiskScore": motif_structural_risk_score,
        "structuralDevelopabilityScore": developability["structuralDevelopabilityScore"],
        "structuralDevelopabilityRisk": developability["structuralDevelopabilityRisk"],
        "structuralIntegrityRisk": developability["structuralIntegrityRisk"],
        "totalCdrLength": sm.get("totalCdrLength"),
        "psh": sm.get("psh"),
        "pshPatchCount": sm.get("pshPatchCount"),
        "ppc": sm.get("ppc"),
        "pnc": sm.get("pnc"),
        "sfvcsp": sm.get("sfvcsp"),
        "cdrh3Compactness": sm.get("cdrh3Compactness"),
        "totalCdrLengthLowConfidenceResidueFraction": sm.get("totalCdrLengthLowConfidenceResidueFraction"),
        "pshLowConfidenceResidueFraction": sm.get("pshLowConfidenceResidueFraction"),
        "ppcLowConfidenceResidueFraction": sm.get("ppcLowConfidenceResidueFraction"),
        "pncLowConfidenceResidueFraction": sm.get("pncLowConfidenceResidueFraction"),
        "sfvcspLowConfidenceResidueFraction": sm.get("sfvcspLowConfidenceResidueFraction"),
        "cdrh3CompactnessLowConfidenceResidueFraction": sm.get("cdrh3CompactnessLowConfidenceResidueFraction"),
        "totalCdrLengthFlag": flags.get("totalCdrLengthFlag", _FLAG_SENTINEL),
        "pshFlag": flags.get("pshFlag", _FLAG_SENTINEL),
        "ppcFlag": flags.get("ppcFlag", _FLAG_SENTINEL),
        "pncFlag": flags.get("pncFlag", _FLAG_SENTINEL),
        "sfvcspFlag": flags.get("sfvcspFlag", _FLAG_SENTINEL),
        "cdrh3CompactnessFlag": flags.get("cdrh3CompactnessFlag", _FLAG_SENTINEL),
    }
    scores_written = write_pframe(
        args.scores_pframe_dir, [scores_row], _SCORES_AXES, _SCORES_COLUMNS
    )
    chown_paths_to_host(scores_written)


if __name__ == "__main__":
    main()
