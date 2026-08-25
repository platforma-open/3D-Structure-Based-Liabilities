---
'@platforma-open/milaboratories.3d-structure-based-liabilities.model': minor
'@platforma-open/milaboratories.3d-structure-based-liabilities.workflow': patch
'@platforma-open/milaboratories.3d-structure-based-liabilities': minor
---

Join the scores table on whichever record-key axis the input uses

The dataset selector already accepted any anchor-marked `pl7.app/structure/pdb` column, so
structures of an `import-vdj-data` bare antibody set — keyed on `pl7.app/variantKey` — could be
picked and scored. Two things downstream of that were still keyed by name.

**The enrichment join was hardcoded to `pl7.app/vdj/scClonotypeKey`.** Label, CDRH3 length and
the clustering columns were queried on that axis literally, so they came back empty for any
input that was not legacy MiXCR single-cell — bulk `pl7.app/vdj/clonotypeKey` included. The
axis name is now read off the scores columns (`recordAxisName`) and the query built from it.
Single-cell behaviour is unchanged: the query is still by axis name and type with no domain,
which is exactly what the constant expressed.

**The viewer-trigger button did not attach** for imported sets: `clonotypeAxisId` matched
`scClonotypeKey` or `clonotypeKey` and returned undefined for `variantKey`. It now matches all
three.

No functional workflow change — the output axis spec is already inherited from the input PDB
column. One panic message that named `scClonotypeKey` now names the record-key axis generically.
