---
"@platforma-open/milabs.3d-structure-based-liabilities": minor
"@platforma-open/milabs.3d-structure-based-liabilities.model": minor
"@platforma-open/milabs.3d-structure-based-liabilities.ui": minor
"@platforma-open/milabs.3d-structure-based-liabilities.workflow": minor
"@platforma-open/milabs.3d-structure-based-liabilities.software": minor
---

PrimaryRef-only release — block now consumes the upstream 3D Structure
Prediction block's `pl7.app/structure/pdb` ResourceMap and iterates per
clonotype. R52 inline `PlStructureViewer` + R53 ClonotypeDetailPanel +
RiskSummaryBar on the Main tab (tab switch to the R51 bulk results table).
R54 distribution pages via hand-rolled SVG (StripPlot at N<20,
MetricHistogram at N≥20) with Raybould / Gordon threshold lines. R42 cluster
columns auto-joined from `3d-structure-clustering` when upstream + viewer
cluster badge + Centroids-only filter. R48 hydrophobicity scale selector
(5 scales). Settings (inputs + numbering + Advanced thresholds + scale) in
PlSlideModal. R44 / R45 run-summary alerts.

Legacy single-PDB upload path removed entirely — block is upstream-only.
BlockData v9 migration strips ten persisted-but-unused fields. Three
clarity passes (Python / workflow / UI) — composables, spec helpers,
shared chart utilities; ~500 lines of duplication removed without
behaviour change.
