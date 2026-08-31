# @platforma-open/milaboratories.3d-structure-based-liabilities.kind

## 1.0.1

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
