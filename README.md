# 3D Structure-Based Liabilities

Assess antibody and nanobody developability on predicted 3D structure rather than sequence alone. This Platforma block reads per-clonotype PDB models, keeps only the liability motifs whose reactive atom is actually solvent-exposed, adds surface metrics from the TAP and TNP developability guidelines, and emits a composite developability cost that downstream blocks can rank candidates on.

Open-source analysis block for Platforma, the biologics discovery platform by MiLaboratories. For the full no-code workflow, see [platforma.bio](https://platforma.bio/).

## What it does

A sequence-only liability scanner flags every regex match it finds — including motifs buried in the protein core, where the reactive chemistry never happens. That inflates the liability count and buries the hits that matter.

This block resolves that with structure. Each motif hit is located in the predicted model and weighted by the **relative solvent-accessible surface area** of its chemically relevant residue, so a buried asparagine contributes almost nothing while an exposed one contributes fully. Exposure is a smooth weight centered near 0.30 rSASA rather than a hard cutoff, with fully buried residues below 0.075 dropped. Hits are then weighted by region — CDR3 counts 1.5×, CDR1 and CDR2 1.2×, down to FR4 at 0.3× — using the CDR boundaries the upstream prediction block writes into the model, so a liability in the binding loop is priced above the same motif in a framework.

Because the structure is predicted, not solved, low-confidence regions are handled explicitly. Per-residue predicted error from ImmuneBuilder gates each call against separate framework and CDR thresholds you control. Gated motifs stay visible in the results table but are excluded from scoring, and the block warns when more than 25% of motifs in a run were gated — a signal that the structure, not the sequence, is the limiting factor.

Structure also enables signals sequence cannot produce: surface hydrophobicity and charge patches in the CDR vicinity, free cysteine state determined from actual disulfide geometry rather than counting residues, and CDR-H3 compactness.

### Two modes, detected automatically

* **TAP** — paired Fv (VH + VL). Surface hydrophobicity, positive-charge patches, negative-charge patches, Fv charge symmetry, and total CDR length, following Raybould 2019 verbatim, with threshold bands pinned to that paper's 242-antibody clinical-stage cohort.
* **TNP** — single-chain VHH nanobodies. The same patch metrics with type-restricted charge patches, plus CDR-H3 compactness, following the Therapeutic Nanobody Profiler, with bands pinned to its 36-nanobody cohort.

Each metric carries a three-band flag — `None`, `Medium`, `High` — placing the candidate against the reference cohort, plus the fraction of low-confidence residues contributing to it.

### Metrics

| Metric | Meaning | Mode |
|---|---|---|
| Surface hydrophobicity (PSH) | Hydrophobic surface exposed in the CDR vicinity; higher is worse | Both |
| Surface hydrophobicity patch count | Number of distinct hydrophobic patches | Both |
| Positive-charge patches (PPC) | Exposed positive-charge patches near the CDRs | Both |
| Negative-charge patches (PNC) | Exposed negative-charge patches near the CDRs | Both |
| Fv charge symmetry (SFvCSP) | Cross-chain charge product; lower means more asymmetric, raising viscosity risk | TAP only |
| CDR-H3 compactness | CDR-H3 length normalized by anchor-centroid distance; both unusually compact and unusually elongated loops can drive aggregation | TNP only |
| Total CDR length | Combined CDR length against the cohort distribution | Both |

## Inputs & outputs

* **Input:** per-clonotype PDB structures from the [3D Structure Prediction](https://github.com/platforma-open/3d-structure-prediction) block, which models paired antibodies with ABodyBuilder2 and nanobodies with NanoBodyBuilder2 and writes IMGT numbering and CDR boundaries into each model. Chain roles and mode are detected automatically.
* **Output:** per-clonotype surfaced motif calls with rSASA and confidence, a motif structural risk score, structural liabilities including free cysteine state, the surface metrics above with cohort flags and low-confidence fractions, total CDR length, mode, and a **developability risk** band plus a continuous **developability cost** — all as columns [Lead Selection](https://github.com/platforma-open/antibody-tcr-lead-selection) and other downstream blocks can filter and rank on. Distribution histograms are provided for hydrophobicity, both charge-patch metrics, the mode-specific metric, and developability cost.

## Specifications

| | |
|---|---|
| Block title in app | 3D Structure-Based Liabilities |
| Input | Predicted per-clonotype PDB models from 3D Structure Prediction |
| Modes | TAP (paired Fv) and TNP (VHH nanobody), detected from the structure |
| Exposure weighting | Relative SASA, smooth weight centered near 0.30; residues below 0.075 rSASA treated as buried |
| SASA computation | [FreeSASA](https://freesasa.github.io/), Shrake–Rupley algorithm, 1.4 Å probe radius — the configuration both calibration cohorts use |
| Region weights | CDR3 1.5, CDR1 1.2, CDR2 1.2, FR1 1.0, FR2 0.5, FR3 0.5, FR4 0.3 |
| Confidence gating | Per-residue predicted error from ImmuneBuilder, with separate user-set framework and CDR thresholds in Å |
| Cohort calibration | 242 clinical-stage antibodies for TAP; 36 clinical-stage nanobodies for TNP |
| Numbering | IMGT |
| Outputs | Surfaced motifs, motif structural risk score, structural liabilities, surface metrics with flags, total CDR length, mode, developability risk, developability cost |

## Use cases

* **De-inflate a liability list:** keep only the motifs whose reactive atom is actually exposed, instead of triaging every regex hit in the sequence.
* **Viscosity and aggregation risk:** read surface hydrophobicity, charge patches, and Fv charge symmetry against a clinical-stage cohort before committing to expression.
* **Nanobody developability:** profile VHH candidates with nanobody-specific bands and CDR-H3 compactness, rather than metrics calibrated on paired antibodies.
* **Free cysteine detection:** identify unpaired cysteines from real disulfide geometry, which residue counting cannot distinguish from a correctly bonded pair.
* **Structure-aware lead ranking:** supply developability cost to Lead Selection so structural risk carries weight in the final panel.
* **Model quality check:** use the confidence-gated fraction to see when a candidate's assessment is limited by structure quality rather than by the molecule.

## How it compares to other Platforma blocks
* **[Sequence Liabilities](https://github.com/platforma-open/antibody-sequence-liabilities)** scans amino acid sequence for the same motif families without structural context. It is far cheaper and runs on any dataset, making it the right first pass.

Using both is the normal pattern: screen broadly on sequence, then predict structures for the survivors and profile them here.

## FAQ

### Why does solvent exposure change the answer?

Liability chemistry — deamidation, isomerization, oxidation, glycosylation — needs the reactive atom to be reachable by solvent. A motif buried in the protein core is inert in practice, but a sequence scanner cannot tell. Weighting each hit by relative SASA removes those false positives and concentrates attention on the exposed hits that actually pose risk.

### What is the difference between TAP and TNP mode?

TAP is the paired-Fv guideline set from Raybould 2019, calibrated on 242 clinical-stage antibodies. TNP is the Therapeutic Nanobody Profiler equivalent for single-domain VHH, calibrated on 36 clinical-stage nanobodies, with type-restricted charge patches and a CDR-H3 compactness metric. Nanobodies differ enough that antibody-calibrated thresholds mislead, which is why the mode is selected from the structure rather than left to the user.

### What is confidence gating and why keep gated motifs visible?

Predicted structures are less reliable in some regions than others. Each residue carries a predicted error from ImmuneBuilder, and motifs on residues above your framework or CDR threshold are excluded from the score — a low-confidence position should not drive a developability call. They stay in the table because knowing a motif exists but could not be confidently placed is different from knowing it is absent.

### What does the 25% warning mean?

That more than a quarter of the run's motifs were confidence-gated, so the scores rest on a minority of confidently placed residues. Treat those results as provisional; the limiting factor is model quality, not the candidates.

### Do I need to run structure prediction first?

Yes. The block consumes predicted PDB models from [3D Structure Prediction](https://github.com/platforma-open/3d-structure-prediction), which also writes the IMGT numbering and CDR boundaries this block relies on for region weighting.

### Which thresholds can I change?

The framework and CDR confidence thresholds, in Å. Everything else — exposure weighting, region weights, cohort bands, SASA parameters — is pinned to the published methods so results stay comparable to the reference cohorts.

### Does it work on TCRs?

No. Both metric sets are calibrated on antibody and nanobody cohorts, and the block is built for antibody formats.

## Citation

If you use this block in your research, please cite the guideline set that applies to your input, and FreeSASA:

> Raybould, M. I. J., Marks, C., Krawczyk, K., Taddese, B., Nowak, J., Lewis, A. P., Bujotzek, A., Shi, J., & Deane, C. M. (2019). Five computational developability guidelines for therapeutic antibody profiling. *PNAS* **116**(10), 4025–4030. [https://doi.org/10.1073/pnas.1810576116](https://doi.org/10.1073/pnas.1810576116)

> Gordon, G. L., Gervasio, J., Souders, C., & Deane, C. M. (2025). The Therapeutic Nanobody Profiler: characterising and predicting nanobody developability to improve therapeutic design. *bioRxiv*. [https://doi.org/10.1101/2025.08.11.669635](https://doi.org/10.1101/2025.08.11.669635)

> Mitternacht, S. (2016). FreeSASA: An open source C library for solvent accessible surface area calculations. *F1000Research* **5**, 189. [https://doi.org/10.12688/f1000research.7931.1](https://doi.org/10.12688/f1000research.7931.1)

## Part of the Platforma ecosystem

This block is part of [Platforma](https://platforma.bio/) by [MiLaboratories](https://github.com/milaboratory), built on [FreeSASA](https://freesasa.github.io/) and the [TAP](https://doi.org/10.1073/pnas.1810576116) and [TNP](https://github.com/oxpig/TNP) developability guidelines from the Oxford Protein Informatics Group. Explore the other open-source blocks at [github.com/platforma-open](https://github.com/platforma-open) and the docs for antibody discovery at [docs.platforma.bio/biology-guides/antibody-discovery](https://docs.platforma.bio/biology-guides/antibody-discovery/).
