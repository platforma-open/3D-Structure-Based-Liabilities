import type { GraphMakerState } from "@milaboratories/graph-maker";

/**
 * Per-metric distribution page configs.
 *
 * The six histogram routes render the same `HistogramPage` component with a
 * different title, fill color, and which scoresTable column to read.
 * `notReadyTitle` is set on the two mode-specific pages to explain why the
 * chart is empty when the dataset is in the other mode.
 */
export type HistogramConfig = {
  title: string;
  columnName: string;
  notReadyTitle?: string;
  // Bar fill color for graph-maker's bins layer. Required because the
  // template's default fillColor is 'white' when no grouping is set,
  // which renders as invisible bars on the chart background.
  fillColor: string;
};

export const histogramConfigs = {
  psh: {
    title: "Patches of Surface Hydrophobicity",
    columnName: "pl7.app/liabilities/psh",
    fillColor: "#7da3d1",
  },
  ppc: {
    title: "Patches of Positive Charge",
    columnName: "pl7.app/liabilities/ppc",
    fillColor: "#e5a06f",
  },
  pnc: {
    title: "Patches of Negative Charge",
    columnName: "pl7.app/liabilities/pnc",
    fillColor: "#82c79c",
  },
  sfvcsp: {
    title: "Symmetry of Fv Charges Product",
    notReadyTitle:
      "SFvCSP is only computed in paired-Fv (TAP) mode. Run the block on a paired-Fv dataset to populate this distribution.",
    columnName: "pl7.app/liabilities/sfvcsp",
    fillColor: "#bb86d6",
  },
  cdrh3Compactness: {
    title: "CDRH3 compactness",
    notReadyTitle:
      "CDRH3 compactness is only computed in VHH (TNP) mode. Run the block on a VHH dataset to populate this distribution.",
    columnName: "pl7.app/liabilities/cdrh3Compactness",
    fillColor: "#d6b06b",
  },
  developability: {
    title: "Developability score",
    columnName: "pl7.app/liabilities/structuralDevelopabilityScore",
    fillColor: "#cf6e83",
  },
} as const satisfies Record<string, HistogramConfig>;

/** Seed a graph-maker `bins` template from a histogram config. The `bins`
 * layer needs an explicit fillColor; the template's default ('white') is
 * invisible against the chart background. */
export function makeGraphState(cfg: HistogramConfig): GraphMakerState {
  return {
    template: "bins",
    title: cfg.title,
    currentTab: null,
    layersSettings: { bins: { fillColor: cfg.fillColor } },
  };
}
