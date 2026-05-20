# Overview

Per-clonotype structural developability analysis for antibody candidates.
Consumes PDB structures from the **3D Structure Prediction** block upstream
and emits per-clonotype liability calls, surface developability metrics, and
composite developability scores that downstream blocks (Lead Selection)
can rank candidates on.

## What it does

For each predicted Fab / VHH, the block runs:

- **Surface-exposed motif detection** — the 11-pattern Raybould motif set
  (deamidation N-G, isomerization, N-glycosylation sequons, oxidation M / W,
  integrin RGD, etc.), filtered to surface-exposed residues only so buried
  false positives drop out.
- **Cysteine state classification** — geometry-driven four-state per Cys:
  `disulfide` (canonical bonded pair), `disulfide_broken`, `disulfide_missing`
  (a canonical position with no Cys at all), or `cys_extra` for orphans
  and interchain bonds. Spec R21–R23.
- **Surface developability metrics** — Raybould 2019 verbatim for paired Fv
  (PSH / PPC / PNC / SFvCSP) and Gordon 2025 for VHH (same metrics with
  type-restricted patches + CDRH3 compactness).
- **Region-aware confidence gating** — uses the ImmuneBuilder-emitted B-factor
  as per-atom predicted error; low-confidence motifs stay in the table for
  traceability but are excluded from the composite score.
- **Composite score + categorical risks** — `structuralDevelopabilityScore`
  (motif + metric-flag bumps + cysteine contributions),
  `structuralDevelopabilityRisk` (None / Low / Medium / High), and
  `structuralIntegrityRisk` (Present / None).

## UI

- **3D viewer** (Mol*) for the selected clonotype, side-by-side with a
  per-clonotype detail panel (motifs grouped by type, cysteine state, surface
  metrics with green/amber/red flag badges, composite risk readout).
- **Results table** with the spec-mandated default-visible columns + a
  "Columns" toggle that reveals raw metric values + low-confidence fractions.
- **Six distribution pages** — one per metric — that render Raybould / Gordon
  amber+red dashed threshold lines so the user can read each candidate's
  standing against the literature thresholds without leaving the chart.
- **Run-summary alerts** when > 10 % of clonotypes carry any red flag or
  > 25 % have confidence-gated motifs.

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
