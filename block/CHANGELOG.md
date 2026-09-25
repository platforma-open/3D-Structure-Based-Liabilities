# @platforma-open/milaboratories.3d-structure-based-liabilities

## 1.3.2

### Patch Changes

- d7c3ca9: Update SDK: PlAgDataTableV2 no longer recreates its grid in an endless loop

## 1.3.1

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

## 1.3.0

### Minor Changes

- b490a3f: Join the scores table on whichever record-key axis the input uses

  The dataset selector already accepted any anchor-marked `pl7.app/structure/pdb` column, so
  structures of an `import-vdj-data` bare antibody set — keyed on `pl7.app/variantKey` — could be
  picked and scored. Two things downstream of that were still keyed by name.

  **The enrichment join was hardcoded to `pl7.app/vdj/scClonotypeKey`.** Label, CDRH3 length and
  the clustering columns were queried on that axis literally, so they came back empty for any
  input that was not legacy MiXCR single-cell — bulk `pl7.app/vdj/clonotypeKey` included. The
  axis name is now read off the scores columns (`recordAxisName`) and the query built from it.
  Single-cell behaviour is unchanged: the query is still by axis name and type with no domain,
  which is exactly what the constant expressed.

  **The viewer-trigger button did not attach** for imported sets: `clonotypeAxisId` matched
  `scClonotypeKey` or `clonotypeKey` and returned undefined for `variantKey`. It now matches all
  three.

  No functional workflow change — the output axis spec is already inherited from the input PDB
  column. One panic message that named `scClonotypeKey` now names the record-key axis generically.

### Patch Changes

- 0031d85: Pass `--registry-serve-url` when publishing the block

  `block-tools` made `--registry-serve-url` a required option for `publish`, and the facade's
  `prepublishOnly` predates that. With block-tools moving from 2.11.0 to 2.14.3 on this branch, the
  release would have failed the way 3d-structure-prediction's already did:

  ```
  error: required option '--registry-serve-url <url>' not specified
  ```

  The component packages publish to npm before the facade runs, so the failure leaves the block
  itself unpublished at a version whose parts are already out. Fixed before that happens rather
  than after.

  The redundant `block-tools pack &&` prefix goes with it: `build` already runs
  `shx rm -rf ./block-pack && block-tools pack`, and CI publishes with `build-script-name: 'build'`.

- Updated dependencies [b490a3f]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.3.0
  - @platforma-open/milaboratories.3d-structure-based-liabilities.workflow@1.2.6
  - @platforma-open/milaboratories.3d-structure-based-liabilities.ui@1.2.6

## 1.2.7

### Patch Changes

- f5bfd0e: Migrate block onto the structurer (block-tools `structure refresh`) and upgrade the SDK toolchain. Tool-managed layout now owns tsconfig, oxlint/oxfmt, turbo, the block index, and per-package deps. Catalog bumped to block-tools 2.11.0, workflow-tengo 6.6.3, model/ui-vue/test 1.79.14, tengo-builder 4.0.8.
- Updated dependencies [f5bfd0e]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.2.5
  - @platforma-open/milaboratories.3d-structure-based-liabilities.ui@1.2.5
  - @platforma-open/milaboratories.3d-structure-based-liabilities.workflow@1.2.5

## 1.2.6

### Patch Changes

- Updated dependencies [c9d3061]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.2.4
  - @platforma-open/milaboratories.3d-structure-based-liabilities.ui@1.2.4

## 1.2.5

### Patch Changes

- 0d47058: Select the 3D structures dataset directly. The upstream 3D Structure Prediction block now exports a confident-only PDB map, so there is no subset to choose: the `PlDatasetSelector` picks the PDB dataset directly and the model no longer attaches subset filters (which had begun surfacing unrelated upstream subsets such as Lead Selection's). The optional `--clonotype-filter` sidecar is no longer passed; the block analyses every structure in the (already confident) input map.
- Updated dependencies [0d47058]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.workflow@1.2.4
  - @platforma-open/milaboratories.3d-structure-based-liabilities.model@1.2.3
  - @platforma-open/milaboratories.3d-structure-based-liabilities.ui@1.2.3

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
