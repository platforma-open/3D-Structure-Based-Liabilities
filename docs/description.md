# Overview

Identifies sequence-level developability liabilities in therapeutic antibody
structures supplied as PDB files. The block parses the uploaded structure and
reports four classes of hits per chain:

- **Unpaired cysteines** — Cys residues not participating in any SSBOND. Free
  Cys can drive aggregation, mispair during expression, or be oxidized.
- **Deamidation hotspots** — N-G and N-S dipeptide motifs. The N-G motif in
  particular shows the highest rate of non-enzymatic deamidation to aspartate
  / iso-aspartate.
- **N-glycosylation sequons** — N-X-[S/T] consensus motifs (X ≠ P). Surface-
  exposed sequons in CDRs are a major manufacturability risk.
- **Oxidation-prone residues** — methionine and tryptophan positions.
  M oxidizes to methionine sulfoxide under formulation stress, W to
  kynurenine derivatives under photo-oxidation.

## Caveats

All detections are **sequence-only**. A buried Met is reported the same as a
surface-exposed one; a sequon in framework is reported the same as one in a
CDR. Real developability assessment requires solvent-accessible surface area
filtering and antibody numbering (Kabat / Chothia / IMGT) to identify CDRs —
both planned for a future release.

## Input

A single `.pdb` file. The block reads ATOM/HETATM records from the first
MODEL block and SSBOND records to identify residues and disulfide pairs.
