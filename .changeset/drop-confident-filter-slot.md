---
'@platforma-open/milaboratories.3d-structure-based-liabilities.workflow': patch
'@platforma-open/milaboratories.3d-structure-based-liabilities.model': patch
'@platforma-open/milaboratories.3d-structure-based-liabilities.software': patch
'@platforma-open/milaboratories.3d-structure-based-liabilities.ui': patch
'@platforma-open/milaboratories.3d-structure-based-liabilities': patch
---

Select the 3D structures dataset directly. The upstream 3D Structure Prediction block now exports a confident-only PDB map, so there is no subset to choose: the `PlDatasetSelector` picks the PDB dataset directly and the model no longer attaches subset filters (which had begun surfacing unrelated upstream subsets such as Lead Selection's). The optional `--clonotype-filter` sidecar is no longer passed; the block analyses every structure in the (already confident) input map.
