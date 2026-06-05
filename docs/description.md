# Overview

Per-clonotype structural developability analysis for antibody candidates.
Consumes PDB structures from the
[**3D Structure Prediction**](https://github.com/platforma-open/3d-structure-prediction)
block upstream and emits per-clonotype liability calls, surface
developability metrics, and composite developability costs that
downstream blocks (Lead Selection) can rank candidates on.

## What it does

For each predicted Fab / VHH, the block runs:

- **Surface-exposed motif detection** — the 11-pattern Raybould motif set
  (deamidation N-G, isomerization, N-glycosylation sequons, oxidation M / W,
  integrin RGD, etc.), filtered to surface-exposed residues only so buried
  false positives drop out.
- **Cysteine state classification** — one row per canonical disulfide pair
  (`disulfide` when both Cys are present and bonded, `disulfide_broken` when
  both present but not bonded, `disulfide_missing` when at least one
  canonical position has no Cys) plus per-residue `cys_extra` rows for
  non-canonical Cys.
- **Surface developability metrics** — Raybould 2019 verbatim for paired Fv
  (surface hydrophobicity, positive-charge patches, negative-charge patches,
  Fv charge symmetry) and Gordon 2025 for VHH (same metrics with
  type-restricted charge patches plus CDRH3 compactness).
- **Region-aware confidence gating** — uses the ImmuneBuilder-emitted B-factor
  as per-atom predicted error; low-confidence motifs stay in the table for
  traceability but are excluded from the composite cost.
- **Composite cost + categorical risks** — `structuralDevelopabilityScore`
  (motif + metric-flag bumps + cysteine contributions),
  `structuralDevelopabilityRisk` (None / Low / Medium / High), and
  `structuralIntegrityRisk` (Present / None).

## UI

- **3D viewer** (Mol*) for the selected clonotype, side-by-side with a
  per-clonotype detail panel (motifs grouped by type, cysteine state, surface
  metrics with None/Medium/High flag badges, composite risk readout).
- **Results table** with default-visible columns + a "Columns" toggle that
  reveals raw metric values + low-confidence fractions.
- **Five distribution pages** — one per metric — that render Raybould / Gordon
  threshold lines so the user can read each candidate's standing against the
  literature thresholds without leaving the chart.
- **Run-summary alert** fires when more than 25% of clonotypes have at least
  one confidence-gated motif.

## Input

A `pl7.app/structure/pdb` PColumn from the upstream 3D Structure Prediction
block. The settings slide-modal exposes the numbering scheme, optional
chain mapping overrides (auto-detected from REMARK 99 in the common case),
and advanced thresholds calibrated for ImmuneBuilder.

## Honest scope

Flags reflect the **predicted apo conformation**. CDR3 in particular can
rearrange on antigen binding, so a residue buried in the apo prediction may
be exposed in the bound state. The value-prop is "removes apo-state-buried
false positives", not "removes all false positives". The per-metric
`<metric>LowConfidenceResidueFraction` column lets users discount metrics
dominated by low-confidence regions of the prediction.
