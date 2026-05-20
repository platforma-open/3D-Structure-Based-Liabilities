# 3D Structure-Based Liabilities

Per-clonotype structural developability analysis for therapeutic antibody
candidates. Consumes PDB structures from the [3D Structure Prediction
block](../3d-structure-prediction/) and produces per-clonotype liability
calls, surface developability metrics, and composite developability scores
that downstream blocks (Lead Selection, etc.) can rank candidates on.

The block reproduces the [Raybould 2019 TAP](https://doi.org/10.1073/pnas.1810576116)
methodology for paired Fv (PSH / PPC / PNC / SFvCSP) and
[Gordon 2025 TNP](https://github.com/oxpig/TNP) for VHH (same metrics with
type-restricted patches + CDRH3 compactness), with one extra signal beyond
both papers: **region-aware per-residue confidence gating** using
ImmuneBuilder B-factor as predicted error.

## What problem does this solve

Sequence-only liability scanners (e.g. our sister
[antibody-sequence-liabilities](../antibody-sequence-liabilities/) block)
report every regex match — every NG, NS, NXT/NXS, etc. — without knowing
whether the chemically reactive atom is solvent-exposed. A buried N-G can't
be deamidated, so flagging it is a false positive.

This block adds 3D context: it filters motif hits by rSASA, weights each
hit by region (CDR3 > CDR1/2 > FR), gates low-confidence regions using
B-factors, and adds structural-only signals (surface charge / hydrophobicity
patches, free-Cys state, CDR3 compactness) that have no sequence-only
equivalent.

## Inputs

The block runs in **PrimaryRef mode only**. It expects a
`pl7.app/structure/pdb` PColumn upstream — emitted by the
3D Structure Prediction block when run on a single-cell clonotype dataset.
The settings slide-modal exposes:

- **Predicted structures** — picks the upstream PDB column (the only required input).
- **Numbering scheme** — IMGT / Chothia / Kabat. Default "unknown" turns off
  region weighting and falls back to neutral motif scoring.
- **Heavy / light chain override** — auto-detected from `REMARK 99 PLATFORMA CDR*`
  records on IMGT-numbered ImmuneBuilder PDBs (spec R9). Override only when
  REMARK 99 is absent.
- **Advanced thresholds** — rSASA buried cutoff (R12), FR / CDR confidence
  thresholds (R34). Defaults calibrated for ImmuneBuilder.
- **Hydrophobicity scale** (R48) — Kyte-Doolittle default, Wimley-White / Hessa /
  Eisenberg-McLachlan / Black-Mould available for sensitivity analysis.

## Outputs

PColumns keyed on `pl7.app/vdj/scClonotypeKey`. R43 trace step + blockId
domain on every output.

- **`motifs`** — one row per surfaced motif hit. Axes: chainId, resSeq, iCode,
  motifType. Columns: resName, region, rsasa, exposureFactor, confidence,
  confidenceGated, weightedScore, sequenceRiskClass, fixability.
- **`cysteines`** — one row per Cys (incl. phantom rows for missing canonical
  positions). Axes: chainId, resSeq, iCode. Columns: cysClass, chainRole,
  bondingState, rsasa, sidechainRsasa, partner fields.
- **`scores`** — per-clonotype scalar PFrame. Counts (extraCys / exposedExtra
  / brokenCanonical / missingCanonical / surfacedMotif / confidenceGatedMotif),
  composite score (`structuralDevelopabilityScore`), categorical risks
  (`structuralDevelopabilityRisk`, `structuralIntegrityRisk`), raw surface
  metrics (PSH, PPC, PNC, SFvCSP, CDRH3 compactness, totalCdrLength) with
  per-metric `lowConfidenceResidueFraction`, and three-band flags (green / amber
  / red).
- **`liabilitiesJsons`** — per-clonotype full JSON report as a File ResourceMap.
  The UI fetches it on demand for the detail panel; downstream blocks
  generally don't need to read this directly.

## UI

- **Main tab** — two views toggled by `PlTabs`:
  - **3D structure + detail** (default): inline Mol\* viewer of the selected
    clonotype's PDB, plus a per-clonotype detail panel (motifs grouped by
    type, cysteine state, surface metrics with flag badges). When the
    3D Structure Clustering block is upstream, a cluster badge shows the
    selected clonotype's clusterId + centroid flag, and a "Centroids only"
    toggle filters the dropdown to cluster representatives.
  - **Per-clonotype table**: bulk-view R51 results table. Default-visible
    columns per spec; everything else behind "Columns".
- **Six distribution routes** in the sidebar (PSH / PPC / PNC / SFvCSP / CDRH3
  compactness / Developability score) — strip plot at N<20, histogram at
  N≥20, both with Raybould / Gordon dashed threshold lines.
- **Motifs / Cysteine state** sidebar drill-downs — full PFrame tables.

## How it works

1. **Input** — workflow's `wf.prepare` resolves the upstream PDB ResourceMap.
2. **Per-clonotype iteration** — `pframes.processColumn` fires the
   `process-pdb` body template for every row of the upstream map.
3. **Body** — calls the `liabilities` Python software with the clonotype's PDB.
4. **Python** —
   - Parses PDB (`parser.py`) — minimal v3.30 fixed-column parser; pulls
     ATOM / HETATM / SSBOND / `REMARK 99 PLATFORMA CDR*` records.
   - Runs FreeSASA against in-block Ala-X-Ala heavy-atom references (R11).
   - Detects motifs (`motifs.py`) — 11 patterns from
     `antibody-sequence-liabilities/definitions.py`, identical risk taxonomy
     and fixability weights. Buried matches dropped (R17). Region weights
     applied (R19). Confidence-gated motifs marked but excluded from the
     composite score (R35).
   - Classifies cysteines (`cysteines.py`) — pairwise SG–SG ≤ 3.0 Å +
     Cα–Cα ≤ 7.0 Å geometry test; canonical-position anchored four-state
     classification (R21–R23).
   - Computes surface metrics (`metrics.py`) — CDR-vicinity residue pairs
     within 7.5 Å, salt-bridge zeroed; PSH/PPC/PNC formula from R25/R26;
     SFvCSP (Fv only) over whole V-domain; CDRH3 compactness (VHH only) via
     IMGT anchor centroids.
   - Composite score + risks (`scoring.py`) — R41 composite (motif + flag
     bumps + cys contributions); R41a categorical risks (None/Low/Medium/High
     for fixable items, Present/None for hard-to-fix / structural integrity).
5. **Workflow** — imports the per-clonotype parquet via xsv-import-pt; builds
   the four PFrames + the JSON ResourceMap; attaches the R43 trace step.

## See also

- [block-structure-liabilities.md](../../docs/text/work/projects/structure-liabilities-block/block-structure-liabilities.md) — full spec (R1–R55).
- [progression.md](../../docs/text/work/projects/structure-liabilities-block/progression.md) — live progression doc.
- [`software/src/`](software/src/) — Python source with spec citations.
- [`workflow/src/specs.lib.tengo`](workflow/src/specs.lib.tengo) — PColumn spec definitions.
