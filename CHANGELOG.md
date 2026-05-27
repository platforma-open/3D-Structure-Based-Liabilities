## 1.0.0

Initial release. Per-clonotype structural developability analysis for antibody
candidates, consuming PDB structures from the 3D Structure Prediction block
upstream. 46 of 49 enumerated spec requirements done as spec; 3 externally
blocked (R46 PlDatasetSelector, R52 colorScheme prop, R54 graph-maker
threshold rendering, all pending upstream releases).

**What it does**

Iterates per clonotype over the upstream `pl7.app/structure/pdb` ResourceMap
in a single Python exec and emits, for each predicted Fab / VHH:

- Per-residue **liability motif** hits (R16-R20): the 11-pattern Raybould
  motif set (deamidation N-G, isomerization D-G/D-S/D-D, N-linked
  glycosylation, oxidation M / W, tryptophan oxidation, integrin RGD, etc.),
  filtered to surface-exposed residues only (rSASA ≥ 0.075) so buried false
  positives drop out. Each hit carries a region-aware weighted score (R19 / R20).
- **Cysteine state** (R21-R23): geometry-driven four-state classification
  (`disulfide`, `disulfide_broken`, `disulfide_missing` phantom row, or
  `cys_extra` for orphans + interchain bonds), SG to SG ≤ 3.0 Å plus
  Cα to Cα ≤ 7.0 Å.
- **Surface developability metrics** (R24-R33): Raybould 2019 verbatim for
  paired Fv (TAP), PSH / PPC / PNC / SFvCSP. Gordon 2025 for VHH (TNP):
  same metrics with same-type-pair restriction plus CDRH3 compactness
  (`length / ρ`).
- **Confidence gating** (R34-R36): region-aware B-factor thresholds gate
  motifs and surface-metric residues (FR > 4.0 Å, CDR > 6.0 Å, calibrated
  for ImmuneBuilder per-atom predicted error). Each metric carries a
  parallel `lowConfidenceResidueFraction` so users can discount
  low-confidence calls. R4 fallback to upstream `confidence/perResidue`
  JSON when B-factors are missing.
- **Composite score + categorical risks** (R39, R41, R41a):
  `structuralDevelopabilityScore` (motif + metric-flag bumps + cysteine
  contributions); `structuralDevelopabilityRisk` (None/Low/Medium/High over
  engineering-fixable items, promoted by amber/red flags);
  `structuralIntegrityRisk` (Present iff hard-to-fix / structural items,
  broken disulfides, or surface-exposed extra Cys).

**Inputs (R1)**

`BlockData.primaryRef` carries `{column, filter?}`:

- `column`: PlRef to a `pl7.app/structure/pdb` PColumn (required).
- `filter` (optional, R1 subset): PlRef to a Boolean/Int PColumn
  (e.g. `pl7.app/structure/predictionSuccessful`, `confident`). Workflow
  exports it as a TSV sidecar; Python skips clonotypes whose value is
  falsy before iterating.

R5/R29 numerator: upstream `pl7.app/structure/cdrh3Length` is
auto-discovered as an enrichment, exported as a TSV sidecar, and used
as the R30 CDRH3 compactness numerator instead of the in-block
Cα count. R10 fail-fast when neither REMARK 99 PLATFORMA CDR records
nor `--numbering-scheme` is available.

**Outputs**

Per-clonotype scalar PColumns keyed on `pl7.app/vdj/scClonotypeKey`, all
bundled in the `scoresData` PFrame. R43 `pl7.app/trace` + `pl7.app/blockId`
domain on every emitted column.

- Counts: `surfacedMotifCount`, `confidenceGatedMotifCount`,
  `extraCysCount`, `exposedExtraCysCount`,
  `brokenCanonicalDisulfideCount`, `missingCanonicalCysCount`.
- Composite + risks: `structuralDevelopabilityScore`,
  `structuralDevelopabilityRisk`, `structuralIntegrityRisk`,
  `motifStructuralRiskScore`.
- Raw metrics: `psh`, `pshPatchCount`, `ppc`, `pnc`, `sfvcsp` (Fv only),
  `cdrh3Compactness` (VHH only), `totalCdrLength`. Each carries a
  `<metric>LowConfidenceResidueFraction` (R36).
- Threshold flags: `<metric>Flag` Strings (green / amber / red) per R39.
  Only `*Flag` columns carry `pl7.app/isScore: "true"` (R40).
- Mode + warnings: `mode` (TAP / TNP), `numberingWarning`,
  `hallmarkWarning`.

**UI**

- **Main page**: `PlAgDataTableV2` with spec R51 default-visible columns.
  Mode-specific flag (sfvcspFlag for TAP, cdrh3CompactnessFlag for TNP)
  selected from `BlockData.detectedMode`. Row double-click (R52) opens a
  `PlSlideModal` with `PlStructureViewer` (Mol\*, initialColorScheme
  `uncertainty` = spec's by-confidence) plus the clonotype detail panel.
  When 3D Structure Clustering is upstream, a cluster badge shows
  clusterId + TM-score to centroid.
- **Distribution pages** (R54, five): PSH, PPC, PNC, mode-specific
  (SFvCSP or CDRH3 compactness), developability score. Histograms via
  graph-maker with Raybould / Gordon threshold lines drawn from each
  metric column's `pl7.app/graph/thresholds` annotation.
- **Run-summary alerts**: R44 fires when more than 10% of clonotypes
  carry any red flag; R45 fires when more than 25% have at least one
  confidence-gated motif.
- **Settings slideover**: predicted-structures dropdown, optional
  clonotype filter, numbering scheme override, heavy/light chain
  override, advanced FR/CDR confidence thresholds (R34).

**Externally blocked**

- **R46 PlDatasetSelector**: UI uses `PlDropdownRef` plus a separate
  filter dropdown. Functionally equivalent; spec mandates
  `PlDatasetSelector` for UX consistency. Unblock pending
  [platforma-open/3d-structure-prediction#13](https://github.com/platforma-open/3d-structure-prediction/pull/13)
  (adds `pl7.app/isAnchor: "true"` to upstream `pdbsMap`).
- **R52 colorScheme prop**: block passes `initialColorScheme="uncertainty"`
  via vendored `@milaboratories/structure-viewer` (PR
  [milaboratory/visualizations#89](https://github.com/milaboratory/visualizations/pull/89)).
  Catalog bump waits on the 0.3.0 publish.
- **R54 threshold rendering**: graph-maker honors
  `pl7.app/graph/thresholds` on histograms via vendored
  `@milaboratories/graph-maker` + `@milaboratories/miplots4` (PR
  [milaboratory/visualizations#87](https://github.com/milaboratory/visualizations/pull/87)).

**Testing**

Python pytest suite at `software/tests/`. 65 unit tests covering
R7 chain-count dispatch + scFv heuristic, R9 chain-role mapping,
R10 numbering source check, R39 Fv + VHH threshold flags, R41
composite scoring + R41a risk classification, R4 B-factor fallback.
Block-load smoke test in `test/src/wf.test.ts` adds the block to a
fresh project and asserts it loads without crashing.

See `docs/text/work/projects/3d-structures-and-clustering/block-structure-liabilities.md`
for the full spec.
