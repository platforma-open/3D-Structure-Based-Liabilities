# @platforma-open/milaboratories.3d-structure-based-liabilities.ui

## 1.2.7

### Patch Changes

- 6e0f659: Migrate to the latest block template and add the mandatory kind package

  Refreshed onto block-tools 2.14.3 via `upgrade-sdk`, and added the `kind/`
  package every block must now declare. The kind carries the block's identity
  (`{name}@{version}`, read from its own `package.json`) and its init-params
  contract. The refresh also reshaped `block/` into the slim facade, which
  publishes the whole block from one dependency-free package.

  `BlockParams` is the two confidence gates, `frConfThresh` and `cdrConfThresh`.
  They decide which residues are trusted enough to score, so they are the only
  fields that change what the block computes. Both are optional, so a project
  template can seed either one alone and the model's `init` keeps a default
  behind each. `.templateParams` projects the same two back, so exporting a block
  to a template and initializing one from it are inverses. Everything else is
  excluded by construction: `dataset` is an anchor-bound `DatasetSelection` that
  cannot travel between projects, `tableState` is view state, and
  `customBlockLabel` is a label typed over a derived default.

  Author-code fixes the SDK upgrade required:

  - `ArrayColumnProvider` is gone from `@platforma-sdk/model`. The scores table
    now builds its recipes with `DataColumn.fromColumn`, and passes primary and
    enrichment columns through the separate `primaryColumns` / `columns` fields
    that `createPlDataTableV3` now takes.
  - Column visibility rules match by selector object (`{ name: "..." }`) instead
    of by predicate function.
  - The test used the facade's old `blockSpec` export, which the slim facade
    replaced with a from-pack-v2 `BlockPointer`.

- Updated dependencies [6e0f659]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.3.1

## 1.2.6

### Patch Changes

- Updated dependencies [b490a3f]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.3.0

## 1.2.5

### Patch Changes

- f5bfd0e: Migrate block onto the structurer (block-tools `structure refresh`) and upgrade the SDK toolchain. Tool-managed layout now owns tsconfig, oxlint/oxfmt, turbo, the block index, and per-package deps. Catalog bumped to block-tools 2.11.0, workflow-tengo 6.6.3, model/ui-vue/test 1.79.14, tengo-builder 4.0.8.
- Updated dependencies [f5bfd0e]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.2.5

## 1.2.4

### Patch Changes

- Updated dependencies [c9d3061]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.2.4

## 1.2.3

### Patch Changes

- 0d47058: Select the 3D structures dataset directly. The upstream 3D Structure Prediction block now exports a confident-only PDB map, so there is no subset to choose: the `PlDatasetSelector` picks the PDB dataset directly and the model no longer attaches subset filters (which had begun surfacing unrelated upstream subsets such as Lead Selection's). The optional `--clonotype-filter` sidecar is no longer passed; the block analyses every structure in the (already confident) input map.
- Updated dependencies [0d47058]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.2.3

## 1.2.2

### Patch Changes

- 4606fe5: Fix results-table sorting, remove the manual heavy/light chain inputs (now auto-detected), clarify the advanced threshold tooltips, rename the "Integrity risk" column to "Structural liabilities", and restore the histogram page titles.
- Updated dependencies [4606fe5]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.2.2

## 1.2.1

### Patch Changes

- cce0ff1: Hardcoded the numbering scheme to IMGT. Every supported upstream emits IMGT-numbered structures, the compactness anchors and canonical disulfide positions are defined against IMGT, and the dropdown was already defaulted to IMGT. Dropped the dropdown from the Settings panel and the `numberingScheme` field from BlockArgs; the workflow now passes `--numbering-scheme imgt` unconditionally.
- Updated dependencies [cce0ff1]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.2.1

## 1.2.0

### Minor Changes

- b24dde6: Declared `supportedPlatforms` in block meta. Renamed columns to plain English (Surface hydrophobicity / Positive-charge patches / Negative-charge patches / Fv charge symmetry / Developability cost) and switched flag vocabulary to None/Medium/High consistent with the developability risk discrete tiers. Added column descriptions for hover tooltips, surfaced an Export button on the Main view, moved histogram titles into the graph-maker plot slot. Switched freeSASA to Shrake-Rupley and re-derived the Ala-X-Ala reference SASAs under the same algorithm so rSASA stays consistent. Removed the VHH surface-hydrophobicity same-type restriction that flagged every nanobody at the highest tier. Restructured disulfide classification to one row per canonical pair. Added discrete-filter + score annotations on developabilityRisk so the lead-selection block can filter on it.

### Patch Changes

- Updated dependencies [b24dde6]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.2.0

## 1.1.0

### Minor Changes

- ea76d7e: Declared `supportedPlatforms` in block meta. Renamed columns to plain English (Surface hydrophobicity / Positive-charge patches / Negative-charge patches / Fv charge symmetry / Developability cost) and switched flag vocabulary to None/Medium/High consistent with the developability risk discrete tiers. Added column descriptions for hover tooltips, surfaced an Export button on the Main view, moved histogram titles into the graph-maker plot slot. Switched freeSASA to Shrake-Rupley and re-derived the Ala-X-Ala reference SASAs under the same algorithm so rSASA stays consistent. Removed the VHH surface-hydrophobicity same-type restriction that flagged every nanobody at the highest tier. Restructured disulfide classification to one row per canonical pair. Added discrete-filter + score annotations on developabilityRisk so the lead-selection block can filter on it.
- ea76d7e: Per-clonotype structure-based liability scoring with a metrics table, structure viewer, and per-metric distribution histograms. The Python tool ships via the python-3 run-environment (no Docker needed in dev), score columns are exported to the result pool for downstream blocks, and the dataset mode is emitted as a workflow output. Adds an editable block label and settings tooltips.

### Patch Changes

- Updated dependencies [ea76d7e]
- Updated dependencies [ea76d7e]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.1.0
