# 3D Structure-Based Liabilities

Per-clonotype structural developability analysis for therapeutic antibody candidates. Consumes PDB structures from the [3D Structure Prediction block](https://github.com/platforma-open/3d-structure-prediction) and reproduces [Raybould 2019 TAP](https://doi.org/10.1073/pnas.1810576116) (paired Fv: surface hydrophobicity / positive-charge patches / negative-charge patches / Fv charge symmetry) and [Gordon 2025 TNP](https://github.com/oxpig/TNP) (VHH: same metrics with type-restricted charge patches plus CDRH3 compactness), with **region-aware per-residue confidence gating** using ImmuneBuilder B-factor as predicted error.

Sequence-only liability scanners (see our sister [antibody-sequence-liabilities](https://github.com/platforma-open/antibody-sequence-liabilities) block) flag every regex match without knowing whether the chemically reactive atom is solvent-exposed. This block adds 3D context: filters motif hits by rSASA, weights each hit by region (CDR3 > CDR1/2 > FR), gates low-confidence regions, and adds structural-only signals (surface charge / hydrophobicity patches, free-Cys state, CDR3 compactness).

## Inputs

`PlDatasetSelector` over `pl7.app/structure/pdb` anchor PColumns. Optional clonotype filter (Boolean/Int subset PColumn, e.g. `predictionSuccessful`, `confident`). Settings: numbering scheme (IMGT default), heavy / light chain overrides (auto-detected from REMARK 99), FR / CDR confidence thresholds (defaults 4.0 / 6.0 Å for ImmuneBuilder).

## Outputs

Per-clonotype scalar PColumns keyed on `pl7.app/vdj/scClonotypeKey`, bundled in the `scoresData` PFrame with `pl7.app/blockId` domain. Composite cost (`structuralDevelopabilityScore`) plus categorical risks (`structuralDevelopabilityRisk`, `structuralIntegrityRisk`); per-metric raw values + threshold flags (None / Medium / High); cysteine and motif counts; per-metric low-confidence-residue fractions. Mode-specific columns (`sfvcsp` for Fv, `cdrh3Compactness` for VHH). Full list with annotations in `workflow/src/specs.lib.tengo`.

## UI

- **Main**: `PlAgDataTableV2` with default-visible columns; row double-click opens a `PlSlideModal` with `PlStructureViewer` (Mol\*, `initialColorScheme="uncertainty"`). Cluster badge surfaces when the 3D Structure Clustering block is upstream.
- **Five distribution pages**: hydrophobicity, positive charge patches, negative charge patches, mode-specific (Fv charge symmetry or CDRH3 compactness), developability cost, via graph-maker with Raybould / Gordon threshold lines.
- **Run-summary alert** fires when more than 25% of clonotypes have at least one confidence-gated motif.

## See Also

- [`software/liabilities-script/`](software/liabilities-script/) , Python source
- [`software/tests/`](software/tests/) , pytest suite covering rejection and scoring paths
