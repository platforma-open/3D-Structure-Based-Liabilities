/**
 * Spec R54 — per-metric distribution page configs.
 *
 * The six histogram routes (PSH / PPC / PNC / SFvCSP / CDRH3 compactness /
 * Developability score) all render the same `HistogramPage` component with
 * different titles, descriptions, threshold prose, and which scoresTable
 * column to read. Centralising the strings here so the per-route .vue
 * files become trivial wrappers — change a description in one place
 * instead of in six near-duplicate files.
 *
 * `notReadyTitle` is set on the two mode-specific pages (SFvCSP only in
 * Fv mode; CDRH3 compactness only in VHH mode) to explain why the chart
 * is empty when the user's data is in the other mode.
 */
export type HistogramConfig = {
  title: string;
  description: string;
  thresholds?: string;
  columnName: string;
  notReadyTitle?: string;
};

export const histogramConfigs = {
  psh: {
    title: "PSH — Patches of Surface Hydrophobicity",
    description:
      "Surface-area-weighted hydrophobicity in the CDR vicinity (Raybould 2019, spec R25). Computed as Σ H(R₁)·H(R₂) / r₁₂² over all surface-exposed residue pairs within 7.5 Å heavy-atom distance, using Kyte-Doolittle hydrophobicity normalized to [1.0, 2.0]. High = sticky surfaces → aggregation, viscosity at high concentration, non-specific binding. Very low = suspiciously hydrophilic (also flagged). Bidirectional risk.",
    thresholds: "Green ~100–156. Amber 84–100 or 156–174. Red < 84 or > 174.",
    columnName: "pl7.app/liabilities/psh",
  },
  ppc: {
    title: "PPC — Patches of Positive Charge",
    description:
      "Surface-area-weighted positive-charge density in the CDR vicinity (Raybould 2019, spec R26). Same pair formula as PSH but with charge magnitudes — sums over K/R/H pairs within 7.5 Å heavy-atom distance, using D/E=−1, K/R=+1, H=+0.1. Salt-bridge residues (R15a) zeroed. High = faster clearance (PK risk), non-specific receptor binding (FcRn, polyspecificity panels).",
    thresholds: "Green ≤ 1.25. Amber 1.25–3.16. Red > 3.16.",
    columnName: "pl7.app/liabilities/ppc",
  },
  pnc: {
    title: "PNC — Patches of Negative Charge",
    description:
      "Surface-area-weighted negative-charge density in the CDR vicinity (Raybould 2019, spec R26). Pair formula sums over D/E pairs within 7.5 Å heavy-atom distance. Salt-bridge residues zeroed. High = expression heterogeneity, charge variants under cation-exchange or imaging cIEF analytics, and similar PK concerns as PPC at high values.",
    thresholds: "Green ≤ 1.84. Amber 1.84–3.50. Red > 3.50.",
    columnName: "pl7.app/liabilities/pnc",
  },
  sfvcsp: {
    title: "SFvCSP — Symmetry of Fv Charges Product",
    description:
      "Inter-chain charge symmetry (Raybould 2019, spec R28; paired-Fv mode only). Computed as (Σ Q on surface-exposed VH residues) × (Σ Q on surface-exposed VL residues) over the whole V-domain, not CDR-restricted. Salt-bridge residues zeroed. Very negative = strongly asymmetric charges between heavy and light chains → viscosity at high concentration (typical at ≥ 100 mg/mL formulations).",
    thresholds: "Green ≥ −6.3. Amber −20.4 to −6.3. Red < −20.4.",
    notReadyTitle:
      "SFvCSP is only computed in paired-Fv (TAP) mode. Run the block on a paired-Fv dataset to populate this distribution.",
    columnName: "pl7.app/liabilities/sfvcsp",
  },
  cdrh3Compactness: {
    title: "CDRH3 compactness (VHH only)",
    description:
      "CDR3 length divided by its radius (spec R30, VHH/TNP mode only). Radius ρ is the distance between centroids of CDR3 Cα atoms (IMGT 105–117) and IMGT anchor Cα atoms (102, 103, 118, 119). Bidirectional: too compact suggests an unfolded or aberrant CDR3, too elongated suggests aggregation-prone loops. IMGT numbering required — falls back to the scheme-aware ranges in other schemes.",
    thresholds: "Green 0.82–1.57. Amber 0.56–0.82 or 1.57–1.61. Red < 0.56 or > 1.61.",
    notReadyTitle:
      "CDRH3 compactness is only computed in VHH (TNP) mode. Run the block on a VHH dataset to populate this distribution.",
    columnName: "pl7.app/liabilities/cdrh3Compactness",
  },
  developability: {
    title: "Developability score — composite engineering burden",
    description:
      "R41 composite. Sum of three contributions: (1) motif structural risk score — Σ over surfaced motifs of fixability × region × exposure (R20); (2) per-metric flag bumps — red = 8, amber = 3, green = 0 across PSH/PPC/PNC/SFvCSP/CDRH3 compactness/totalCdrLength; (3) cysteine penalties — exposedExtraCysCount × 8 + brokenCanonicalDisulfideCount × 20 + missingCanonicalCysCount × 20. Higher = more engineering work to bring the candidate to clinic. There is no pass/fail cut — use this for ranking candidates against each other; the categorical Developability risk and Integrity risk columns on the Main table apply the spec R41a rules and are easier to read at a glance.",
    columnName: "pl7.app/liabilities/structuralDevelopabilityScore",
  },
} as const satisfies Record<string, HistogramConfig>;
