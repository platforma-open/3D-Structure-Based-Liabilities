# @platforma-open/milaboratories.3d-structure-based-liabilities.workflow

## 1.1.0

### Minor Changes

- ea76d7e: Declared `supportedPlatforms` in block meta. Renamed columns to plain English (Surface hydrophobicity / Positive-charge patches / Negative-charge patches / Fv charge symmetry / Developability cost) and switched flag vocabulary to None/Medium/High consistent with the developability risk discrete tiers. Added column descriptions for hover tooltips, surfaced an Export button on the Main view, moved histogram titles into the graph-maker plot slot. Switched freeSASA to Shrake-Rupley and re-derived the Ala-X-Ala reference SASAs under the same algorithm so rSASA stays consistent. Removed the VHH surface-hydrophobicity same-type restriction that flagged every nanobody at the highest tier. Restructured disulfide classification to one row per canonical pair. Added discrete-filter + score annotations on developabilityRisk so the lead-selection block can filter on it.
- ea76d7e: Per-clonotype structure-based liability scoring with a metrics table, structure viewer, and per-metric distribution histograms. The Python tool ships via the python-3 run-environment (no Docker needed in dev), score columns are exported to the result pool for downstream blocks, and the dataset mode is emitted as a workflow output. Adds an editable block label and settings tooltips.

### Patch Changes

- Updated dependencies [ea76d7e]
- Updated dependencies [ea76d7e]
  - @platforma-open/milaboratories.3d-structure-based-liabilities.software@0.2.0
