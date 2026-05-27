---
"@platforma-open/milabs.3d-structure-based-liabilities": minor
"@platforma-open/milabs.3d-structure-based-liabilities.model": minor
"@platforma-open/milabs.3d-structure-based-liabilities.ui": minor
"@platforma-open/milabs.3d-structure-based-liabilities.workflow": minor
"@platforma-open/milabs.3d-structure-based-liabilities.software": minor
---

Spec compliance pass + SDK 1.77 bump. 46 of 49 enumerated requirements done as spec; 3 externally blocked.

PrimaryRef path: workflow's `wf.prepare` resolves `BlockData.primaryRef.column` to the upstream `pl7.app/structure/pdb` PColumn and builds a bundle for enrichments. `wf.body` stages every PDB into one exec call, writes a 2-column `pdb_index.tsv`, runs Python once, imports `per_clonotype.tsv` via `xsv.importFile`. R43 `pl7.app/trace` stamped on every emitted PColumn via `pSpec.makeTrace`. R47 subset filter: optional second `PlDropdownRef` over discovered Boolean/Int PColumns; workflow exports the picked column as a TSV sidecar and Python skips clonotypes whose value is falsy. R5/R29 cdrh3Length numerator: upstream `pl7.app/structure/cdrh3Length` auto-discovered, exported as TSV sidecar, used as the R30 compactness numerator. R4 B-factor JSON fallback: upstream `pl7.app/structure/confidence/perResidue` JSON parsed per clonotype, used as the motif confidence value when in-PDB B-factor is 0.

Surface metrics + scoring: R39 thresholds pinned in `data/thresholds.json` from Raybould 2019 Table 2 (Fv, cohortSize 242) and oxpig/TNP `bin/TNP` `assign_flag()` (VHH, cohortSize 36). R41 composite + R41a categorical risks shipped end-to-end. R34/R35/R36 region-aware confidence gating with `*LowConfidenceResidueFraction` doubles for each surface metric.

UI: R51 `PlAgDataTableV2` with spec default-visible columns + mode-specific flag (driven by `BlockData.detectedMode`). R52 row double-click opens `PlSlideModal` with `PlStructureViewer` (initialColorScheme="uncertainty" = spec's by-confidence) + clonotype detail panel + cluster badge when 3D Structure Clustering is upstream. R54 five distribution histograms via graph-maker; mode-specific page dispatches SFvCSP (TAP) or CDRH3 compactness (TNP). R44/R45 run-summary alerts (>10% red flags, >25% confidence-gated). R55 parameter-summary subtitle with mode prefix.

Externally blocked: R46 `PlDatasetSelector` (needs upstream `pl7.app/isAnchor` annotation, see platforma-open/3d-structure-prediction#13); R52 colorScheme prop wiring (needs structure-viewer 0.3.0 publish, milaboratory/visualizations#89, vendored); R54 graph-maker threshold rendering (milaboratory/visualizations#87, vendored).

SDK catalog: `@platforma-sdk/model` and `@platforma-sdk/ui-vue` 1.64.0 to 1.77.4; `@platforma-sdk/workflow-tengo` 5.13.1 to 5.25.0; `@platforma-sdk/tengo-builder` 2.5.8 to 3.0.4 (major); `@platforma-sdk/block-tools` 2.7.7 to 2.9.1; `@platforma-sdk/test` 1.64.0 to 1.77.5; `@milaboratories/ts-builder` 1.3.1 to 1.5.0.

Python pytest suite: 65 unit tests covering R7 chain-count dispatch, R10 numbering source check, R9 chain-role mapping, R39 Fv + VHH threshold flags, R41 composite scoring, R41a risk classification, R4 B-factor fallback. Layout matches workspace convention (pyproject.toml, uv.lock, software/tests/).
