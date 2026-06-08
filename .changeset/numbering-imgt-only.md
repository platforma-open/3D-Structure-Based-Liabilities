---
"@platforma-open/milaboratories.3d-structure-based-liabilities": patch
"@platforma-open/milaboratories.3d-structure-based-liabilities.model": patch
"@platforma-open/milaboratories.3d-structure-based-liabilities.ui": patch
"@platforma-open/milaboratories.3d-structure-based-liabilities.workflow": patch
---

Hardcoded the numbering scheme to IMGT. Every supported upstream emits IMGT-numbered structures, the compactness anchors and canonical disulfide positions are defined against IMGT, and the dropdown was already defaulted to IMGT. Dropped the dropdown from the Settings panel and the `numberingScheme` field from BlockArgs; the workflow now passes `--numbering-scheme imgt` unconditionally.
