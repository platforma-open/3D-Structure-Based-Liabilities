# 3D Structure-Based Liabilities

Per-clonotype structural developability analysis for therapeutic antibody candidates. Consumes PDB structures from the [3D Structure Prediction block](../3d-structure-prediction/) and reproduces [Raybould 2019 TAP](https://doi.org/10.1073/pnas.1810576116) (paired Fv: PSH / PPC / PNC / SFvCSP) and [Gordon 2025 TNP](https://github.com/oxpig/TNP) (VHH: same metrics with type-restricted patches plus CDRH3 compactness), with **region-aware per-residue confidence gating** using ImmuneBuilder B-factor as predicted error.

Sequence-only liability scanners (see our sister [antibody-sequence-liabilities](../antibody-sequence-liabilities/) block) flag every regex match without knowing whether the chemically reactive atom is solvent-exposed. This block adds 3D context: filters motif hits by rSASA, weights each hit by region (CDR3 > CDR1/2 > FR), gates low-confidence regions, and adds structural-only signals (surface charge / hydrophobicity patches, free-Cys state, CDR3 compactness).

## Inputs

`PlDatasetSelector` over `pl7.app/structure/pdb` anchor PColumns. Optional clonotype filter (Boolean/Int subset PColumn, e.g. `predictionSuccessful`, `confident`). Settings: numbering scheme (IMGT default), heavy / light chain overrides (auto-detected from REMARK 99), FR / CDR confidence thresholds (defaults 4.0 / 6.0 Å for ImmuneBuilder).

## Outputs

Per-clonotype scalar PColumns keyed on `pl7.app/vdj/scClonotypeKey`, bundled in the `scoresData` PFrame with R43 trace + `pl7.app/blockId` domain. Composite score (`structuralDevelopabilityScore`) plus categorical risks (`structuralDevelopabilityRisk`, `structuralIntegrityRisk`); per-metric raw values + threshold flags (green / amber / red); cysteine and motif counts; per-metric low-confidence-residue fractions. Mode-specific columns (`sfvcsp` for Fv, `cdrh3Compactness` for VHH). Full list with annotations in `workflow/src/specs.lib.tengo`.

## UI

- **Main**: `PlAgDataTableV2` with R51 default-visible columns; row double-click opens a `PlSlideModal` with `PlStructureViewer` (Mol\*, `initialColorScheme="uncertainty"`). Cluster badge surfaces when the 3D Structure Clustering block is upstream.
- **Five distribution pages** (R54): PSH, PPC, PNC, mode-specific (SFvCSP or CDRH3 compactness), developability score, via graph-maker with Raybould / Gordon threshold lines.
- **Run-summary alerts**: R44 fires when more than 10% of clonotypes carry any red flag; R45 fires when more than 25% have at least one confidence-gated motif.

## See Also

- [block-structure-liabilities.md](../../docs/text/work/projects/3d-structures-and-clustering/block-structure-liabilities.md) , full spec (R1-R55)
- [`software/liabilities-script/`](software/liabilities-script/) , Python source with spec citations
- [`software/tests/`](software/tests/) , 65 pytest tests covering R4/R7/R9/R10/R39/R41 paths
