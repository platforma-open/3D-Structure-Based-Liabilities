---
"@platforma-open/milaboratories.3d-structure-based-liabilities": minor
"@platforma-open/milaboratories.3d-structure-based-liabilities.model": minor
"@platforma-open/milaboratories.3d-structure-based-liabilities.ui": minor
"@platforma-open/milaboratories.3d-structure-based-liabilities.workflow": minor
"@platforma-open/milaboratories.3d-structure-based-liabilities.software": minor
---

Declared `supportedPlatforms` in block meta. Renamed columns to plain English (Surface hydrophobicity / Positive-charge patches / Negative-charge patches / Fv charge symmetry / Developability cost) and switched flag vocabulary to None/Medium/High consistent with the developability risk discrete tiers. Added column descriptions for hover tooltips, surfaced an Export button on the Main view, moved histogram titles into the graph-maker plot slot. Switched freeSASA to Shrake-Rupley and re-derived the Ala-X-Ala reference SASAs under the same algorithm so rSASA stays consistent. Removed the VHH surface-hydrophobicity same-type restriction that flagged every nanobody at the highest tier. Restructured disulfide classification to one row per canonical pair. Added discrete-filter + score annotations on developabilityRisk so the lead-selection block can filter on it.
