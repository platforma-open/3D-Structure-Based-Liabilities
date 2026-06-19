---
'@platforma-open/milaboratories.3d-structure-based-liabilities.model': patch
'@platforma-open/milaboratories.3d-structure-based-liabilities.ui': patch
'@platforma-open/milaboratories.3d-structure-based-liabilities.workflow': patch
'@platforma-open/milaboratories.3d-structure-based-liabilities.software': patch
'@platforma-open/milaboratories.3d-structure-based-liabilities': patch
---

Migrate block onto the structurer (block-tools `structure refresh`) and upgrade the SDK toolchain. Tool-managed layout now owns tsconfig, oxlint/oxfmt, turbo, the block index, and per-package deps. Catalog bumped to block-tools 2.11.0, workflow-tengo 6.6.3, model/ui-vue/test 1.79.14, tengo-builder 4.0.8.