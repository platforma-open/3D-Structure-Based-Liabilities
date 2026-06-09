# Overview

Per-clonotype structural developability analysis for antibody candidates.
Consumes per-clonotype PDB files from the [3D Structure
Prediction](https://github.com/platforma-open/3d-structure-prediction) block
upstream and emits per-clonotype liability calls, surface developability
metrics, and a composite developability cost that downstream blocks (Lead
Selection) can rank candidates on.

Sequence-only liability scanners (see our sister [Antibody Sequence
Liabilities](https://github.com/platforma-open/antibody-sequence-liabilities)
block) flag every regex match without knowing whether the chemically reactive
atom is solvent-exposed. This block adds 3D context: filters motif hits by
relative solvent-accessible surface area (rSASA), weights each hit by region
(CDR3 > CDR1/2 > FR), gates low-confidence residues using the per-residue
predicted error emitted by ImmuneBuilder, and adds structural-only signals
(surface hydrophobicity / charge patches, free-Cys state, CDR-H3 compactness).

Surface metrics follow [Raybould 2019
TAP](https://doi.org/10.1073/pnas.1810576116) verbatim for paired Fv (surface
hydrophobicity, positive-charge patches, negative-charge patches, Fv charge
symmetry) and [Gordon 2025 TNP](https://github.com/oxpig/TNP) for VHH (same
metrics with type-restricted charge patches plus CDR-H3 compactness). SASA is
computed with [FreeSASA](https://freesasa.github.io/) under the Shrake-Rupley
algorithm at a 1.4 Å probe radius, the configuration both calibration cohorts
use. Threshold bands are pinned to the literature cohorts: cohortSize 242 for
Fv (Raybould 2019 Table 2), cohortSize 36 for VHH (Gordon 2025
`assign_flag()`).

> Raybould MIJ, Marks C, Krawczyk K, Taddese B, Nowak J, Lewis AP, Bujotzek A,
> Shi J, Deane CM. _Five computational developability guidelines for
> therapeutic antibody profiling._ PNAS 116(10), 4025–4030 (2019).
> [https://doi.org/10.1073/pnas.1810576116](https://doi.org/10.1073/pnas.1810576116)

> Gordon GL, Raybould MIJ, Deane CM. _TAP 2.0: a refined platform for assessing
> the developability of nanobodies (in silico)._ bioRxiv (2025).
> [https://doi.org/10.1101/2025.08.11.669635](https://doi.org/10.1101/2025.08.11.669635)

SASA computation uses [FreeSASA](https://freesasa.github.io/). Please cite:

> Mitternacht S. _FreeSASA: An open source C library for solvent accessible
> surface area calculations._ F1000Research, 5:189 (2016).
> [https://doi.org/10.12688/f1000research.7931.1](https://doi.org/10.12688/f1000research.7931.1)
