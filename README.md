# 3D Structure-Based Liabilities

Per-clonotype structural developability analysis for therapeutic antibody
candidates. Consumes PDB structures from the [3D Structure Prediction
block](../3d-structure-prediction/) and produces per-clonotype liability
calls, surface developability metrics, and composite developability scores
that downstream blocks (Lead Selection, etc.) can rank candidates on.

The block reproduces the [Raybould 2019 TAP](https://doi.org/10.1073/pnas.1810576116)
methodology for paired Fv (PSH / PPC / PNC / SFvCSP) and
[Gordon 2025 TNP](https://github.com/oxpig/TNP) for VHH (same metrics with
type-restricted patches plus CDRH3 compactness), with one extra signal
beyond both papers: **region-aware per-residue confidence gating** using
ImmuneBuilder B-factor as predicted error.

## What problem does this solve

Sequence-only liability scanners (e.g. our sister
[antibody-sequence-liabilities](../antibody-sequence-liabilities/) block)
report every regex match (NG, NS, NXT/NXS, etc.) without knowing whether
the chemically reactive atom is solvent-exposed. A buried N-G can't be
deamidated, so flagging it is a false positive.

This block adds 3D context: filters motif hits by rSASA, weights each
hit by region (CDR3 > CDR1/2 > FR), gates low-confidence regions using
B-factors, and adds structural-only signals (surface charge / hydrophobicity
patches, free-Cys state, CDR3 compactness) that have no sequence-only
equivalent.

## Inputs

The block runs in **PrimaryRef mode only**. It expects a
`pl7.app/structure/pdb` PColumn upstream, emitted by the 3D Structure
Prediction block when run on a single-cell clonotype dataset. The
settings slideover exposes:

- **Predicted structures**: picks the upstream PDB column (required).
- **Clonotype filter** (optional): picks an upstream Boolean/Int column
  (e.g. `pl7.app/structure/predictionSuccessful`, `pl7.app/structure/confident`)
  to narrow the clonotype set. Workflow exports the column to a TSV
  sidecar; Python skips clonotypes whose value is falsy before iterating.
- **Numbering scheme**: IMGT (default) / Chothia / Kabat. Falls back to
  scheme-aware fixed CDR ranges when REMARK 99 PLATFORMA CDR records
  are absent (spec R10).
- **Heavy / light chain override**: auto-detected from
  `REMARK 99 PLATFORMA CDR*` records on IMGT-numbered ImmuneBuilder
  PDBs (spec R9). Override only when REMARK 99 is absent.
- **Advanced thresholds**: FR / CDR confidence gating thresholds (R34
  defaults 4.0 / 6.0 Å for ImmuneBuilder per-atom predicted error).
  rSASA buried cutoff is hardcoded at 0.075 per spec R12.

## Outputs

Per-clonotype scalar PColumns keyed on `pl7.app/vdj/scClonotypeKey`,
all bundled in the `scoresData` PFrame. R43 trace step + `pl7.app/blockId`
domain on every output.

- **Counts**: `surfacedMotifCount`, `confidenceGatedMotifCount`,
  `extraCysCount`, `exposedExtraCysCount`, `brokenCanonicalDisulfideCount`,
  `missingCanonicalCysCount`.
- **Composite + risks**: `structuralDevelopabilityScore` (R41),
  `structuralDevelopabilityRisk` (None/Low/Medium/High over engineering-
  fixable items, R41a), `structuralIntegrityRisk` (Present iff hard-to-fix
  or structural motifs, broken disulfides, or surface-exposed extra Cys).
- **Raw surface metrics**: `psh`, `pshPatchCount`, `ppc`, `pnc`,
  `sfvcsp` (Fv only), `cdrh3Compactness` (VHH only), `totalCdrLength`,
  `motifStructuralRiskScore`. Each carries a parallel
  `<metric>LowConfidenceResidueFraction` Double (R36).
- **Threshold flags**: `<metric>Flag` Strings (green / amber / red) per
  R39 thresholds. Only `*Flag` columns carry `pl7.app/isScore: "true"` per R40.
- **Mode + warnings**: `mode` (TAP / TNP), `numberingWarning`,
  `hallmarkWarning`.

## UI

- **Main page**: `PlAgDataTableV2` with spec R51 default-visible
  columns. Mode-specific flag (sfvcspFlag for TAP, cdrh3CompactnessFlag
  for TNP) is selected from `BlockData.detectedMode`. Row double-click
  opens a `PlSlideModal` (R52) containing `PlStructureViewer` (Mol\*,
  initialColorScheme `uncertainty` = spec's by-confidence) plus the
  clonotype detail panel. When the 3D Structure Clustering block is
  upstream, a cluster badge shows the selected clonotype's clusterId
  + TM-score to centroid.
- **Distribution pages** (5): PSH, PPC, PNC, mode-specific (SFvCSP or
  CDRH3 compactness), developability score. Histograms via graph-maker
  with Raybould / Gordon threshold lines drawn from each metric column's
  `pl7.app/graph/thresholds` annotation (R54).
- **Run-summary alerts**: R44 fires when more than 10% of clonotypes
  carry any red flag; R45 fires when more than 25% have at least one
  confidence-gated motif.

## How it works

1. **Input**: `wf.prepare` resolves `args.primaryRef.column` to the
   upstream PDB PColumn and builds a bundle for enrichments
   (`cdrh3Length`, `confidence/perResidue`, optional filter).
2. **Single-shot**: `wf.body` stages every PDB into one exec call,
   writes a 2-column `pdb_index.tsv`, and runs `python main.py` once
   against the whole dataset. Optional sidecar TSVs: cdrh3 lengths
   (R5/R29 numerator), per-residue confidence JSON (R4 fallback),
   clonotype filter (R1 subset).
3. **Python** (`software/liabilities-script/`):
   - Parses PDB (`structure.py`): v3.30 fixed-column parser; pulls
     ATOM / HETATM / `REMARK 99 PLATFORMA CDR*` records.
   - Runs FreeSASA against in-block Ala-X-Ala heavy-atom references
     (`data/heavy_atom_max_sasa.tsv`, spec R11).
   - Detects motifs (`motifs.py`): 11 patterns from
     `antibody-sequence-liabilities/definitions.py`, identical risk
     taxonomy and fixability weights. Buried matches dropped (R17).
     Region weights applied (R19). Confidence-gated motifs marked but
     excluded from the composite score (R35).
   - Classifies cysteines (`cysteines.py`): pairwise SG to SG ≤ 3.0 Å
     plus Cα to Cα ≤ 7.0 Å geometry test; canonical-position-anchored
     four-state classification (R21-R23).
   - Computes surface metrics (`metrics.py`): CDR-vicinity residue
     pairs within 7.5 Å, salt-bridge zeroed; PSH/PPC/PNC formula from
     R25/R26; SFvCSP over whole V-domain (Fv only); CDRH3 compactness
     via IMGT anchor centroids (VHH only).
   - Composite score + risks (`scoring.py`): R41 composite (motif +
     flag bumps + cys contributions); R41a categorical risks.
4. **Import**: workflow imports `per_clonotype.tsv` via
   `xsv.importFile`, attaches R43 trace, exports as `scoresData` PFrame.

## See also

- [block-structure-liabilities.md](../../docs/text/work/projects/3d-structures-and-clustering/block-structure-liabilities.md) , full spec (R1-R55).
- [`software/liabilities-script/`](software/liabilities-script/) , Python source with spec citations.
- [`workflow/src/specs.lib.tengo`](workflow/src/specs.lib.tengo) , PColumn spec definitions.
- [`software/tests/`](software/tests/) , pytest suite covering R7/R9/R10/R4/R39/R41 paths.
