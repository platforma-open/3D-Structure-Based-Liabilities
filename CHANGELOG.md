## 1.0.0

Initial release. Per-clonotype structural developability analysis for antibody
candidates, consuming PDB structures from the 3D Structure Prediction block
upstream.

**What it does**

Iterates per clonotype over the upstream `pl7.app/structure/pdb` ResourceMap and
emits, for each predicted Fab / VHH:

- Per-residue **liability motif** hits (R16–R20): the 11-pattern Raybould motif
  set (deamidation N-G, isomerization D-G/D-S/D-D, N-linked glycosylation,
  oxidation M / W, tryptophan oxidation, integrin RGD, etc.), filtered to
  surface-exposed residues only (rSASA ≥ 0.075) so buried false positives drop
  out. Each hit carries a region-aware weighted score (R19 / R20).
- **Cysteine state** (R21–R23): geometry-driven four-state classification —
  `disulfide` (canonical bonded pair), `disulfide_broken`, `disulfide_missing`
  (phantom row), or `cys_extra` for orphans + interchain bonds.
- **Surface developability metrics** (R24–R30): Raybould 2019 verbatim for
  paired Fv (TAP) — PSH, PPC, PNC, SFvCSP — and Gordon 2025 for VHH (TNP) —
  PSH/PPC/PNC with same-type-pair restriction + CDRH3 compactness `length / ρ`.
- **Confidence gating** (R34–R36): region-aware B-factor thresholds gate
  motifs and surface-metric residues (FR > 4.0 Å, CDR > 6.0 Å — calibrated for
  ImmuneBuilder per-atom predicted error). Each metric carries a parallel
  `lowConfidenceResidueFraction` so users can discount low-confidence calls.
- **Composite score + categorical risks** (R39, R41, R41a):
  `structuralDevelopabilityScore` (motif + metric-flag bumps + cysteine
  contributions), `structuralDevelopabilityRisk` (None/Low/Medium/High over
  engineering-fixable items, promoted by amber/red flags), and
  `structuralIntegrityRisk` (Present iff hard-to-fix / structural items,
  broken disulfides, or surface-exposed extra Cys).

**Outputs**

PColumns suitable for downstream consumption (Lead Selection, etc.), all keyed
on `pl7.app/vdj/scClonotypeKey`:

- `motifs` PFrame: one row per motif hit (axes include chainId / resSeq /
  iCode / motifType).
- `cysteines` PFrame: one row per Cys (axes: chainId / resSeq / iCode).
- `scores` PFrame: per-clonotype scalars — counts, composite score, flags,
  raw metrics, low-conf fractions.
- `liabilitiesJsons` ResourceMap: per-clonotype JSON reports for UI drill-down.

R43 trace step + `pl7.app/blockId` domain on every emitted PColumn.

**UI**

Main page: settings slide-modal (R3 dataset selector + numbering scheme +
chain mapping overrides + R49 advanced thresholds + R48 hydrophobicity scale).
Tab switch between (a) 3D viewer (PlStructureViewer / Mol*) + per-clonotype
detail panel (R52 / R53) — defaults to the first clonotype, "Centroids only"
filter when the 3D Structure Clustering block is upstream — and (b) the R51
results table. Six R54 distribution pages — SVG strip plot at N<20, hand-rolled
SVG histogram at N≥20, both with Raybould / Gordon dashed threshold lines.
Run-summary alerts (R44 red ≥ 10%, R45 gated ≥ 25%).

**Known gaps**

- R52 viewer color schemes (`by-confidence` / `by-rsasa` / `by-hydrophobicity`)
  await `@milaboratories/structure-viewer` ≥ 0.3.0 publish — features are in
  workspace source. Ships with Mol*'s default cartoon-by-chain preset.
- M1 calibration vs Raybould Dataset S3 / AZ paired set pending.
- VHH (TNP) end-to-end validation needs a camelid PDB fixture.

See `docs/text/work/projects/structure-liabilities-block/` for the full spec
and the live progression doc.
