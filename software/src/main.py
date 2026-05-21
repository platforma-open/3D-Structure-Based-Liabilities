import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

import freesasa

from cysteines import detect_cysteines
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


if __name__ == "__main__":
    main()
