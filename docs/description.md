# Overview

Per-clonotype structural developability analysis for antibody candidates. Consumes per-clonotype PDB files from the [3D Structure Prediction](https://github.com/platforma-open/3d-structure-prediction) block upstream and emits per-clonotype liability calls, surface developability metrics, and a composite developability cost that downstream blocks (Lead Selection) can rank candidates on.

Sequence-only liability scanners (see our sister [Antibody Sequence Liabilities](https://github.com/platforma-open/antibody-sequence-liabilities) block) flag every regex match without knowing whether the chemically reactive atom is solvent-exposed. This block adds 3D context: filters motif hits by relative solvent-accessible surface area (rSASA), weights each hit by region (CDR3 > CDR1/2 > FR), gates low-confidence residues using the per-residue predicted error emitted by ImmuneBuilder, and adds structural-only signals (surface hydrophobicity / charge patches, free-Cys state, CDR-H3 compactness).

Surface metrics follow [Raybould 2019 TAP](https://doi.org/10.1073/pnas.1810576116) verbatim for paired Fv (surface hydrophobicity, positive-charge patches, negative-charge patches, Fv charge symmetry) and [Gordon 2025 TNP](https://github.com/oxpig/TNP) for VHH (same metrics with type-restricted charge patches plus CDR-H3 compactness). SASA is computed with [FreeSASA](https://freesasa.github.io/) under the Shrake-Rupley algorithm at a 1.4 Å probe radius, the configuration both calibration cohorts use. Threshold bands are pinned to the literature cohorts: cohortSize 242 for Fv (Raybould 2019 Table 2), cohortSize 36 for VHH (Gordon 2025 `assign_flag()`).

Outputs are per-clonotype scalar `PColumn`s keyed on `pl7.app/vdj/scClonotypeKey`. The composite cost `structuralDevelopabilityScore` aggregates motif risk (`fixabilityWeight × regionWeight × exposure`), per-metric threshold-flag bumps, and cysteine penalties. Two categorical risks ride alongside: `structuralDevelopabilityRisk` (None / Low / Medium / High) and `structuralIntegrityRisk` (None / Present, for broken or missing canonical disulfides, exposed extra cysteines, and structural-tier motifs). Per-metric raw values + None/Medium/High threshold flags are exported, with `<metric>LowConfidenceResidueFraction` columns letting users discount metrics dominated by low-confidence regions of the prediction.

## UI

The Main page renders a per-clonotype results table with default-visible columns (developability cost, risk levels, per-metric flags, cysteine counts) and a "Columns" toggle that reveals raw metric values and low-confidence fractions. Double-clicking a row opens a Mol\*-based 3D structure viewer for that clonotype with confidence-coloured per-residue rendering. Five distribution pages (surface hydrophobicity, positive-charge patches, negative-charge patches, mode-specific Fv-charge-symmetry / CDR-H3 compactness, and developability cost) render the Raybould / Gordon threshold lines so each candidate's standing against the literature thresholds is visible without leaving the chart. A run-summary alert fires when more than 25% of clonotypes have at least one confidence-gated motif.

## Honest scope

Flags reflect the **predicted apo conformation**. CDR-H3 in particular can rearrange on antigen binding, so a residue buried in the apo prediction may be exposed in the bound state. The value-prop is "removes apo-state-buried false positives", not "removes all false positives". The per-metric low-confidence-residue fraction lets users discount metrics dominated by uncertain regions of the prediction.

## References

> Raybould MIJ, Marks C, Krawczyk K, Taddese B, Nowak J, Lewis AP, Bujotzek A, Shi J, Deane CM. *Five computational developability guidelines for therapeutic antibody profiling.* PNAS 116(10), 4025–4030 (2019). [https://doi.org/10.1073/pnas.1810576116](https://doi.org/10.1073/pnas.1810576116)

> Gordon GL, Raybould MIJ, Deane CM. *TAP 2.0: a refined platform for assessing the developability of nanobodies (in silico).* bioRxiv (2025). [https://doi.org/10.1101/2025.08.11.669635](https://doi.org/10.1101/2025.08.11.669635)

SASA computation uses [FreeSASA](https://freesasa.github.io/). Please cite:

> Mitternacht S. *FreeSASA: An open source C library for solvent accessible surface area calculations.* F1000Research, 5:189 (2016). [https://doi.org/10.12688/f1000research.7931.1](https://doi.org/10.12688/f1000research.7931.1)
