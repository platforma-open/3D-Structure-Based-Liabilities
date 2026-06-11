# @platforma-open/milaboratories.3d-structure-based-liabilities.model

## 1.2.4

### Patch Changes

- c9d3061: Fix Open button for bulk dataset

## 1.2.3

### Patch Changes

- 0d47058: Select the 3D structures dataset directly. The upstream 3D Structure Prediction block now exports a confident-only PDB map, so there is no subset to choose: the `PlDatasetSelector` picks the PDB dataset directly and the model no longer attaches subset filters (which had begun surfacing unrelated upstream subsets such as Lead Selection's). The optional `--clonotype-filter` sidecar is no longer passed; the block analyses every structure in the (already confident) input map.

## 1.2.2

### Patch Changes

- 4606fe5: Fix results-table sorting, remove the manual heavy/light chain inputs (now auto-detected), clarify the advanced threshold tooltips, rename the "Integrity risk" column to "Structural liabilities", and restore the histogram page titles.

## 1.2.1

### Patch Changes

- cce0ff1: Hardcoded the numbering scheme to IMGT. Every supported upstream emits IMGT-numbered structures, the compactness anchors and canonical disulfide positions are defined against IMGT, and the dropdown was already defaulted to IMGT. Dropped the dropdown from the Settings panel and the `numberingScheme` field from BlockArgs; the workflow now passes `--numbering-scheme imgt` unconditionally.

## 1.2.0

### Minor Changes

- b24dde6: Declared `supportedPlatforms` in block meta. Renamed columns to plain English (Surface hydrophobicity / Positive-charge patches / Negative-charge patches / Fv charge symmetry / Developability cost) and switched flag vocabulary to None/Medium/High consistent with the developability risk discrete tiers. Added column descriptions for hover tooltips, surfaced an Export button on the Main view, moved histogram titles into the graph-maker plot slot. Switched freeSASA to Shrake-Rupley and re-derived the Ala-X-Ala reference SASAs under the same algorithm so rSASA stays consistent. Removed the VHH surface-hydrophobicity same-type restriction that flagged every nanobody at the highest tier. Restructured disulfide classification to one row per canonical pair. Added discrete-filter + score annotations on developabilityRisk so the lead-selection block can filter on it.

## 1.1.0

### Minor Changes

- ea76d7e: Declared `supportedPlatforms` in block meta. Renamed columns to plain English (Surface hydrophobicity / Positive-charge patches / Negative-charge patches / Fv charge symmetry / Developability cost) and switched flag vocabulary to None/Medium/High consistent with the developability risk discrete tiers. Added column descriptions for hover tooltips, surfaced an Export button on the Main view, moved histogram titles into the graph-maker plot slot. Switched freeSASA to Shrake-Rupley and re-derived the Ala-X-Ala reference SASAs under the same algorithm so rSASA stays consistent. Removed the VHH surface-hydrophobicity same-type restriction that flagged every nanobody at the highest tier. Restructured disulfide classification to one row per canonical pair. Added discrete-filter + score annotations on developabilityRisk so the lead-selection block can filter on it.
- ea76d7e: Per-clonotype structure-based liability scoring with a metrics table, structure viewer, and per-metric distribution histograms. The Python tool ships via the python-3 run-environment (no Docker needed in dev), score columns are exported to the result pool for downstream blocks, and the dataset mode is emitted as a workflow output. Adds an editable block label and settings tooltips.
