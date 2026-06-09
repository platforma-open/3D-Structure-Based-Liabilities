---
"@platforma-open/milaboratories.3d-structure-based-liabilities": patch
"@platforma-open/milaboratories.3d-structure-based-liabilities.software": patch
"@platforma-open/milaboratories.3d-structure-based-liabilities.workflow": patch
---

Surfaced motifs column now shows a per-chain CDR summary of the actual liability hits instead of a total count. Mirrors the antibody-sequence-liabilities block's summary column. Compressed for readability: CDR1/CDR2/CDR3 only (framework hits dropped, they're heavily down-weighted in scoring anyway), motif base name only (regex pattern stripped, so `Deamidation (N[GS])` collapses with `Deamidation (N[AHNT])` into `Deamidation`), per-region dedupe. Empty rows render `"None"`. Confidence-gated motifs stay out of the summary and the `confidenceGatedMotifCount` column alongside.

Also reformatted `docs/description.md` to match 3d-structure-prediction / 3d-structure-clustering: prose paragraphs over bullet lists, methodology inline with FreeSASA + Raybould 2019 + Gordon 2025 citations, output schema described, UI summary, references block at the bottom.
