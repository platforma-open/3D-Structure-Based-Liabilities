# @platforma-open/milaboratories.3d-structure-based-liabilities

## 1.2.4

### Patch Changes

- 4606fe5: Fix results-table sorting, remove the manual heavy/light chain inputs (now auto-detected), clarify the advanced threshold tooltips, rename the "Integrity risk" column to "Structural liabilities", and restore the histogram page titles.
- Updated dependencies [4606fe5]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.2.2
  - @platforma-open/milaboratories.3d-structure-based-liabilities.ui@1.2.2
  - @platforma-open/milaboratories.3d-structure-based-liabilities.workflow@1.2.3

## 1.2.3

### Patch Changes

- bedffc2: Switch the release channel from unstable to stable. Each push to main now publishes the new version straight to the stable channel (matching 3d-structure-prediction and antibody-sequence-liabilities) instead of staging it in unstable and waiting on a manual mark-stable workflow.

## 1.2.2

### Patch Changes

- e6a520a: Surfaced motifs column now shows a per-chain CDR summary of the actual liability hits instead of a total count. Mirrors the antibody-sequence-liabilities block's summary column. Compressed for readability: CDR1/CDR2/CDR3 only (framework hits dropped, they're heavily down-weighted in scoring anyway), motif base name only (regex pattern stripped, so `Deamidation (N[GS])` collapses with `Deamidation (N[AHNT])` into `Deamidation`), per-region dedupe. Empty rows render `"None"`. Confidence-gated motifs stay out of the summary and the `confidenceGatedMotifCount` column alongside.

  Also reformatted `docs/description.md` to match 3d-structure-prediction / 3d-structure-clustering: prose paragraphs over bullet lists, methodology inline with FreeSASA + Raybould 2019 + Gordon 2025 citations, output schema described, UI summary, references block at the bottom.

- Updated dependencies [e6a520a]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.workflow@1.2.2

## 1.2.1

### Patch Changes

- cce0ff1: Hardcoded the numbering scheme to IMGT. Every supported upstream emits IMGT-numbered structures, the compactness anchors and canonical disulfide positions are defined against IMGT, and the dropdown was already defaulted to IMGT. Dropped the dropdown from the Settings panel and the `numberingScheme` field from BlockArgs; the workflow now passes `--numbering-scheme imgt` unconditionally.
- Updated dependencies [cce0ff1]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.2.1
  - @platforma-open/milaboratories.3d-structure-based-liabilities.ui@1.2.1
  - @platforma-open/milaboratories.3d-structure-based-liabilities.workflow@1.2.1

## 1.2.0

### Minor Changes

- b24dde6: Declared `supportedPlatforms` in block meta. Renamed columns to plain English (Surface hydrophobicity / Positive-charge patches / Negative-charge patches / Fv charge symmetry / Developability cost) and switched flag vocabulary to None/Medium/High consistent with the developability risk discrete tiers. Added column descriptions for hover tooltips, surfaced an Export button on the Main view, moved histogram titles into the graph-maker plot slot. Switched freeSASA to Shrake-Rupley and re-derived the Ala-X-Ala reference SASAs under the same algorithm so rSASA stays consistent. Removed the VHH surface-hydrophobicity same-type restriction that flagged every nanobody at the highest tier. Restructured disulfide classification to one row per canonical pair. Added discrete-filter + score annotations on developabilityRisk so the lead-selection block can filter on it.

### Patch Changes

- Updated dependencies [b24dde6]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.2.0
  - @platforma-open/milaboratories.3d-structure-based-liabilities.ui@1.2.0
  - @platforma-open/milaboratories.3d-structure-based-liabilities.workflow@1.2.0

## 1.1.0

### Minor Changes

- ea76d7e: Declared `supportedPlatforms` in block meta. Renamed columns to plain English (Surface hydrophobicity / Positive-charge patches / Negative-charge patches / Fv charge symmetry / Developability cost) and switched flag vocabulary to None/Medium/High consistent with the developability risk discrete tiers. Added column descriptions for hover tooltips, surfaced an Export button on the Main view, moved histogram titles into the graph-maker plot slot. Switched freeSASA to Shrake-Rupley and re-derived the Ala-X-Ala reference SASAs under the same algorithm so rSASA stays consistent. Removed the VHH surface-hydrophobicity same-type restriction that flagged every nanobody at the highest tier. Restructured disulfide classification to one row per canonical pair. Added discrete-filter + score annotations on developabilityRisk so the lead-selection block can filter on it.
- ea76d7e: Per-clonotype structure-based liability scoring with a metrics table, structure viewer, and per-metric distribution histograms. The Python tool ships via the python-3 run-environment (no Docker needed in dev), score columns are exported to the result pool for downstream blocks, and the dataset mode is emitted as a workflow output. Adds an editable block label and settings tooltips.

### Patch Changes

- Updated dependencies [ea76d7e]
- Updated dependencies [ea76d7e]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.1.0
  - @platforma-open/milaboratories.3d-structure-based-liabilities.ui@1.1.0
  - @platforma-open/milaboratories.3d-structure-based-liabilities.workflow@1.1.0
