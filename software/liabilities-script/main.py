"""Batched per-clonotype liability analysis per the spec Software Interface.

Reads a `pdb_index.tsv` (clonotypeKey \\t pdb_filename), loops over each PDB
in `--pdb-dir`, and writes a single `--output-tsv` whose columns match
spec R38 (scalar atomic PColumns) + R39 (threshold flags). One row per
clonotype; mode (R7), numbering warnings, and hallmark mismatches are
in the TSV alongside the metrics.
"""

import argparse
import csv
import json
import math
import os
import sys
from io import StringIO
from pathlib import Path
from typing import Iterator

import freesasa

from cysteines import detect_cysteines
from metrics import compute_metrics
from motifs import detect_motifs
from scoring import compute_developability
from structure import check_hallmark_tetrad, cross_check_ssbonds, parse_pdb


# Heavy-atom Ala-X-Ala SASA references (R11), loaded from
# data/heavy_atom_max_sasa.tsv (residue, total, sidechain columns).
_REFS_PATH = Path(__file__).parent / "data" / "heavy_atom_max_sasa.tsv"


def _load_axa_refs(path: Path) -> dict[str, dict[str, float]]:
    refs: dict[str, dict[str, float]] = {}
    with path.open() as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#") or line.startswith("residue"):
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            refs[parts[0]] = {"total": float(parts[1]), "sidechain": float(parts[2])}
    return refs


_AXA_REFS: dict[str, dict[str, float]] = _load_axa_refs(_REFS_PATH)


def compute_sasa(pdb_path: Path) -> dict[tuple[str, str], dict[str, float]]:
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
    return None if math.isnan(f) else f


def _iter_clonotype_keyed_tsv(path: Path) -> Iterator[tuple[str, str]]:
    """Yield (clonotype_key, raw_value) for each row of an xsv-exported TSV
    with a `pl7.app/vdj/scClonotypeKey`-named first column and exactly one
    value column. Skips rows with empty value. Used by the three sidecar
    loaders below."""
    with path.open() as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fields = reader.fieldnames or []
        key_col = next((c for c in fields if "scClonotypeKey" in c), None)
        val_col = next((c for c in fields if c != key_col), None)
        if not key_col or not val_col:
            return
        for r in reader:
            raw = r.get(val_col)
            if raw is None or raw == "":
                continue
            yield r[key_col], raw


def chown_to_host(path: Path) -> None:
    try:
        workdir_stat = os.stat("/workdir")
        os.chown(path, workdir_stat.st_uid, workdir_stat.st_gid)
    except (FileNotFoundError, PermissionError, OSError):
        pass


_FLAG_SENTINEL = "-"

# Spec R38 / R39 - per-clonotype scalar columns. `clonotypeKey` is first
# (matches the spec's Software Interface TSV header); the workflow's
# `xsv.importFile` maps it to the upstream PDB column's scClonotypeKey
# axis. R2's `sampleId` axis is not present in the deployed upstream
# PDB column shape, so the output TSV stays single-keyed.
_TSV_COLUMNS = [
    "clonotypeKey",
    "mode",
    "numberingWarning",
    "structuralDevelopabilityRisk",
    "structuralIntegrityRisk",
    "structuralDevelopabilityScore",
    "motifStructuralRiskScore",
    "surfacedMotifCount",
    "confidenceGatedMotifCount",
    "extraCysCount",
    "exposedExtraCysCount",
    "brokenCanonicalDisulfideCount",
    "missingCanonicalCysCount",
    "totalCdrLength",
    "totalCdrLengthFlag",
    "totalCdrLengthLowConfidenceResidueFraction",
    "psh",
    "pshPatchCount",
    "pshFlag",
    "pshLowConfidenceResidueFraction",
    "ppc",
    "ppcFlag",
    "ppcLowConfidenceResidueFraction",
    "pnc",
    "pncFlag",
    "pncLowConfidenceResidueFraction",
    "sfvcsp",
    "sfvcspFlag",
    "sfvcspLowConfidenceResidueFraction",
    "cdrh3Compactness",
    "cdrh3CompactnessFlag",
    "cdrh3CompactnessLowConfidenceResidueFraction",
    "hallmarkWarning",
]


def _tsv_value(v):
    """Empty cell for None; preserves Python int/float/bool repr otherwise."""
    if v is None:
        return ""
    return str(v)


def analyze_pdb(
    *,
    pdb_path: Path,
    numbering_scheme: str | None,
    chain_h: str | None,
    chain_l: str | None,
    rsasa_buried_cutoff: float,
    fr_conf_thresh: float,
    cdr_conf_thresh: float,
    upstream_cdrh3_length: int | None = None,
    confidence_fallback: dict | None = None,
) -> dict:
    """Run the full per-clonotype analysis on a single PDB. Returns a dict
    matching the TSV column set. Raises ValueError on R7 / R10 failures.
    """
    text = pdb_path.read_text()
    parsed = parse_pdb(text)

    n_chains = len(parsed.chain_order)
    if n_chains == 0:
        raise ValueError("PDB contains no ATOM records (spec R7)")
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

    # R10 fail-fast: numbering source check must happen before FreeSASA so
    # the run aborts cheaply when both REMARK 99 records and --numbering-scheme
    # are missing.
    has_remark_cdrs = bool(parsed.platforma_cdrs)
    has_scheme = bool(numbering_scheme)
    if not has_remark_cdrs and not has_scheme:
        raise ValueError(
            "No numbering source available: PDB has no REMARK 99 PLATFORMA "
            "CDR records and no --numbering-scheme was provided. Region "
            "tagging requires one of the two (spec R10)."
        )

    sasa_lookup = compute_sasa(pdb_path)

    numbering_warning = ""
    if not has_remark_cdrs and has_scheme:
        numbering_warning = (
            f"no REMARK 99 PLATFORMA CDR records; fell back to scheme-aware "
            f"fixed ranges for '{numbering_scheme}'"
        )

    heavy_chain_id = parsed.chain_role_to_pdb_chain.get("H", chain_h)
    light_chain_id = parsed.chain_role_to_pdb_chain.get("L", chain_l)

    motif_hits = detect_motifs(
        parsed, sasa_lookup, rsasa_buried_cutoff,
        numbering_scheme=numbering_scheme,
        heavy_chain_id=heavy_chain_id,
        light_chain_id=light_chain_id,
        fr_confidence_threshold=fr_conf_thresh,
        cdr_confidence_threshold=cdr_conf_thresh,
        confidence_fallback=confidence_fallback,
    )
    cys_hits = detect_cysteines(
        parsed, sasa_lookup,
        numbering_scheme=numbering_scheme,
        heavy_chain_id=heavy_chain_id,
        light_chain_id=light_chain_id,
    )
    motif_structural_risk_score = sum(
        h.weightedScore for h in motif_hits if h.confidenceGated != "yes"
    )
    surface_metrics = compute_metrics(
        parsed, sasa_lookup,
        numbering_scheme=numbering_scheme,
        heavy_chain_id=heavy_chain_id,
        light_chain_id=light_chain_id,
        rsasa_buried_cutoff=rsasa_buried_cutoff,
        fr_conf_thresh=fr_conf_thresh,
        cdr_conf_thresh=cdr_conf_thresh,
        upstream_cdrh3_length=upstream_cdrh3_length,
    )
    developability = compute_developability(
        motif_hits, cys_hits, surface_metrics, rsasa_buried_cutoff
    )
    mode = "TAP" if n_chains == 2 else "TNP"

    # R21 SSBOND cross-check + R33 hallmark tetrad. Hallmark mismatch
    # surfaces in the TSV; SSBOND mismatches stay stderr-only.
    cross_check_ssbonds(parsed.ssbonds, cys_hits)
    hallmark = check_hallmark_tetrad(
        parsed, numbering_scheme, heavy_chain_id, chain_count_mode=mode
    )
    hallmark_warning = ""
    if hallmark and hallmark.get("mismatch"):
        impl = hallmark.get("impliedMode", "?")
        hallmark_warning = (
            f"hallmark tetrad implies {impl} but chain count says {mode}"
        )

    # compute_metrics returns {} when neither chain is mapped; .get(...) below
    # returns None for every metric in that case.
    sm = surface_metrics
    flags = developability["flags"]
    extra_cys = sum(1 for h in cys_hits if h.cysClass == "cys_extra")
    exposed_extra_cys = sum(
        1 for h in cys_hits
        if h.cysClass == "cys_extra"
        and h.sidechainRsasa is not None
        and h.sidechainRsasa >= rsasa_buried_cutoff
    )
    broken_canonical = sum(1 for h in cys_hits if h.cysClass == "disulfide_broken")
    missing_canonical = sum(1 for h in cys_hits if h.cysClass == "disulfide_missing")

    return {
        "mode": mode,
        "numberingWarning": numbering_warning,
        "structuralDevelopabilityRisk": developability["structuralDevelopabilityRisk"],
        "structuralIntegrityRisk": developability["structuralIntegrityRisk"],
        "structuralDevelopabilityScore": developability["structuralDevelopabilityScore"],
        "motifStructuralRiskScore": motif_structural_risk_score,
        "surfacedMotifCount": len(motif_hits),
        "confidenceGatedMotifCount": sum(1 for h in motif_hits if h.confidenceGated == "yes"),
        "extraCysCount": extra_cys,
        "exposedExtraCysCount": exposed_extra_cys,
        "brokenCanonicalDisulfideCount": broken_canonical,
        "missingCanonicalCysCount": missing_canonical,
        "totalCdrLength": sm.get("totalCdrLength"),
        "totalCdrLengthFlag": flags.get("totalCdrLengthFlag", _FLAG_SENTINEL),
        "totalCdrLengthLowConfidenceResidueFraction": sm.get("totalCdrLengthLowConfidenceResidueFraction"),
        "psh": sm.get("psh"),
        "pshPatchCount": sm.get("pshPatchCount"),
        "pshFlag": flags.get("pshFlag", _FLAG_SENTINEL),
        "pshLowConfidenceResidueFraction": sm.get("pshLowConfidenceResidueFraction"),
        "ppc": sm.get("ppc"),
        "ppcFlag": flags.get("ppcFlag", _FLAG_SENTINEL),
        "ppcLowConfidenceResidueFraction": sm.get("ppcLowConfidenceResidueFraction"),
        "pnc": sm.get("pnc"),
        "pncFlag": flags.get("pncFlag", _FLAG_SENTINEL),
        "pncLowConfidenceResidueFraction": sm.get("pncLowConfidenceResidueFraction"),
        "sfvcsp": sm.get("sfvcsp"),
        "sfvcspFlag": flags.get("sfvcspFlag", _FLAG_SENTINEL),
        "sfvcspLowConfidenceResidueFraction": sm.get("sfvcspLowConfidenceResidueFraction"),
        "cdrh3Compactness": sm.get("cdrh3Compactness"),
        "cdrh3CompactnessFlag": flags.get("cdrh3CompactnessFlag", _FLAG_SENTINEL),
        "cdrh3CompactnessLowConfidenceResidueFraction": sm.get("cdrh3CompactnessLowConfidenceResidueFraction"),
        "hallmarkWarning": hallmark_warning,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdb-dir", required=True, type=Path,
                    help="Directory holding the PDB files referenced by --pdb-index.")
    ap.add_argument("--pdb-index", required=True, type=Path,
                    help="TSV with two columns (clonotypeKey, pdb_filename); "
                         "filenames are resolved relative to --pdb-dir.")
    ap.add_argument("--output-tsv", required=True, type=Path,
                    help="Output TSV path. One row per clonotype.")
    ap.add_argument("--rsasa-buried-cutoff", type=float, default=0.075,
                    help="Spec R12 default 0.075 (Raybould 2019 canonical).")
    ap.add_argument("--fr-confidence-gating-threshold", type=float, default=4.0,
                    dest="fr_conf_thresh",
                    help="Spec R34 default 4.0 Å (framework region).")
    ap.add_argument("--cdr-confidence-gating-threshold", type=float, default=6.0,
                    dest="cdr_conf_thresh",
                    help="Spec R34 default 6.0 Å (CDR region).")
    ap.add_argument("--numbering-scheme", choices=["imgt", "chothia", "kabat"],
                    default=None,
                    help="Numbering scheme for region tagging (R14). Fallback "
                         "when REMARK 99 PLATFORMA CDR records are absent.")
    ap.add_argument("--chain-h", default=None,
                    help="PDB chain ID treated as the heavy chain when REMARK "
                         "99 doesn't declare it.")
    ap.add_argument("--chain-l", default=None,
                    help="PDB chain ID treated as the light chain when REMARK "
                         "99 doesn't declare it.")
    ap.add_argument("--cdrh3-lengths", type=Path, default=None,
                    dest="cdrh3_lengths_tsv",
                    help="Optional TSV exported from upstream's "
                         "`pl7.app/structure/cdrh3Length` PColumn. When "
                         "provided, the per-clonotype value overrides the "
                         "in-block CDR3 Cα count as the R30 compactness "
                         "numerator (R5 / R29).")
    ap.add_argument("--clonotype-filter", type=Path, default=None,
                    dest="clonotype_filter_tsv",
                    help="Optional TSV exported from a Boolean/Int PColumn "
                         "(spec R1 `PrimaryRef.filter`). Clonotypes whose "
                         "value is falsy (0, false, empty) are skipped "
                         "before iteration.")
    ap.add_argument("--per-residue-confidence", type=Path, default=None,
                    dest="per_residue_confidence_tsv",
                    help="Optional TSV exported from upstream's "
                         "`pl7.app/structure/confidence/perResidue` JSON "
                         "PColumn. Per-residue errorAngstroms values feed "
                         "the R4 fallback for motif confidence gating when "
                         "the PDB's B-factor column is empty.")
    args = ap.parse_args()

    if not args.pdb_dir.is_dir():
        raise SystemExit(f"--pdb-dir is not a directory: {args.pdb_dir}")
    if not args.pdb_index.is_file():
        raise SystemExit(f"--pdb-index does not exist: {args.pdb_index}")

    with args.pdb_index.open() as fh:
        index_rows = [tuple(line.rstrip("\n").split("\t")) for line in fh if line.strip()]
    if not index_rows:
        raise SystemExit(f"--pdb-index is empty: {args.pdb_index}")

    upstream_cdrh3: dict[str, int] = {}
    if args.cdrh3_lengths_tsv is not None and args.cdrh3_lengths_tsv.is_file():
        for k, raw in _iter_clonotype_keyed_tsv(args.cdrh3_lengths_tsv):
            try:
                upstream_cdrh3[k] = int(float(raw))
            except (TypeError, ValueError):
                continue

    per_residue_confidence: dict[str, dict[tuple[str, str], float]] = {}
    if args.per_residue_confidence_tsv is not None and args.per_residue_confidence_tsv.is_file():
        for k, raw in _iter_clonotype_keyed_tsv(args.per_residue_confidence_tsv):
            try:
                records = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if not isinstance(records, list):
                continue
            lookup: dict[tuple[str, str], float] = {}
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                pos = rec.get("pos")
                chain = rec.get("chain")
                err = rec.get("errorAngstroms")
                if pos is None or chain is None or err is None:
                    continue
                try:
                    lookup[(str(chain), str(pos))] = float(err)
                except (TypeError, ValueError):
                    continue
            if lookup:
                per_residue_confidence[k] = lookup

    # `None` means no filter picked, run on every clonotype. An empty set
    # means the filter was picked but no clonotype passed (skip them all).
    keep_clonotypes: set[str] | None = None
    if args.clonotype_filter_tsv is not None and args.clonotype_filter_tsv.is_file():
        keep_clonotypes = set()
        for k, raw in _iter_clonotype_keyed_tsv(args.clonotype_filter_tsv):
            v = raw.strip().lower()
            if v in {"0", "false", "no", "null"}:
                continue
            try:
                if float(v) == 0.0:
                    continue
            except ValueError:
                pass
            keep_clonotypes.add(k)

    out_buf = StringIO()
    writer = csv.writer(out_buf, delimiter="\t", lineterminator="\n")
    writer.writerow(_TSV_COLUMNS)

    for entry in index_rows:
        if len(entry) != 2:
            raise SystemExit(
                "--pdb-index row malformed (expected "
                f"clonotypeKey<TAB>filename): {entry}"
            )
        clonotype_key, pdb_filename = entry
        if keep_clonotypes is not None and clonotype_key not in keep_clonotypes:
            continue
        pdb_path = args.pdb_dir / pdb_filename
        if not pdb_path.is_file():
            raise SystemExit(
                f"PDB referenced by index missing on disk: {pdb_path}"
            )
        try:
            row = analyze_pdb(
                pdb_path=pdb_path,
                numbering_scheme=args.numbering_scheme,
                chain_h=args.chain_h,
                chain_l=args.chain_l,
                rsasa_buried_cutoff=args.rsasa_buried_cutoff,
                fr_conf_thresh=args.fr_conf_thresh,
                cdr_conf_thresh=args.cdr_conf_thresh,
                upstream_cdrh3_length=upstream_cdrh3.get(clonotype_key),
                confidence_fallback=per_residue_confidence.get(clonotype_key),
            )
        except ValueError as e:
            print(
                f"WARN ({clonotype_key}): {e}; skipping row",
                file=sys.stderr,
            )
            continue
        row["clonotypeKey"] = clonotype_key
        writer.writerow([_tsv_value(row.get(c)) for c in _TSV_COLUMNS])

    args.output_tsv.parent.mkdir(parents=True, exist_ok=True)
    args.output_tsv.write_text(out_buf.getvalue())
    chown_to_host(args.output_tsv)


if __name__ == "__main__":
    main()
