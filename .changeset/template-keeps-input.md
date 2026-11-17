---
"@platforma-open/milaboratories.3d-structure-based-liabilities.kind": minor
"@platforma-open/milaboratories.3d-structure-based-liabilities.model": patch
---

Keep the input dataset in a project template. A project made from a template came with 3D Structure-Based Liabilities without its dataset, so the block could not run until the dataset was picked by hand. The kind now carries `dataset`, the selection of the predicted structures of an upstream block, and the block made from a template points at the structures the original project scored.
