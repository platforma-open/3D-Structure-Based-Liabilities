import type { GraphMakerState } from "@milaboratories/graph-maker";

/**
 * Per-metric distribution page configs.
 *
 * The six histogram routes render the same `HistogramPage` component with a
 * different title, fill color, threshold legend, and which scoresTable column
 * to read. `notReadyTitle` is set on the two mode-specific pages to explain
 * why the chart is empty when the dataset is in the other mode.
 *
 * `thresholds` is a small tier-keyed legend rendered above the chart so the
 * reader can interpret the dashed threshold lines graph-maker draws from
 * the column's `pl7.app/graph/thresholds` annotation. Optional; the
 * developability cost has no fixed band cuts (composite score is for ranking).
 */
export type ThresholdBands = {
  none?: string;
  medium?: string;
  high?: string;
};

export type HistogramConfig = {
  title: string;
  columnName: string;
  notReadyTitle?: string;
  // Bar fill color for graph-maker's bins layer. Required because the
  // template's default fillColor is 'white' when no grouping is set,
  // which renders as invisible bars on the chart background.
  fillColor: string;
  thresholds?: ThresholdBands;
};

export const histogramConfigs = {
  psh: {
    title: "Hydrophobicity",
    columnName: "pl7.app/liabilities/psh",
    fillColor: "#7da3d1",
    thresholds: {
      none: "100 to 156",
      medium: "84 to 100 or 156 to 174",
      high: "below 84 or above 174",
    },
  },
  ppc: {
    title: "Positive charge patches",
    columnName: "pl7.app/liabilities/ppc",
    fillColor: "#e5a06f",
    thresholds: {
      none: "≤ 1.25",
      medium: "1.25 to 3.16",
      high: "above 3.16",
    },
  },
  pnc: {
    title: "Negative charge patches",
    columnName: "pl7.app/liabilities/pnc",
    fillColor: "#82c79c",
    thresholds: {
      none: "≤ 1.84",
      medium: "1.84 to 3.50",
      high: "above 3.50",
    },
  },
  sfvcsp: {
    title: "Fv charge symmetry",
    notReadyTitle:
      "Fv charge symmetry is only computed in paired-Fv (TAP) mode. Run the block on a paired-Fv dataset to populate this distribution.",
    columnName: "pl7.app/liabilities/sfvcsp",
    fillColor: "#bb86d6",
    thresholds: {
      none: "≥ -6.3",
      medium: "-20.4 to -6.3",
      high: "below -20.4",
    },
  },
  cdrh3Compactness: {
    title: "CDRH3 compactness",
    notReadyTitle:
      "CDRH3 compactness is only computed in VHH (TNP) mode. Run the block on a VHH dataset to populate this distribution.",
    columnName: "pl7.app/liabilities/cdrh3Compactness",
    fillColor: "#d6b06b",
    thresholds: {
      none: "0.82 to 1.57",
      medium: "0.56 to 0.82 or 1.57 to 1.61",
      high: "below 0.56 or above 1.61",
    },
  },
  developability: {
    title: "Developability cost",
    columnName: "pl7.app/liabilities/structuralDevelopabilityScore",
    fillColor: "#cf6e83",
  },
} as const satisfies Record<string, HistogramConfig>;

/** Seed a graph-maker `bins` template from a histogram config. The `bins`
 * layer needs an explicit fillColor; the template's default ('white') is
 * invisible against the chart background. `title` is graph-maker's own chart
 * title (part of its v-model state, editable in the chart), which carries the
 * page label since the page renders no PlBlockPage heading of its own. */
export function makeGraphState(cfg: HistogramConfig): GraphMakerState {
  return {
    template: "bins",
    title: cfg.title,
    currentTab: null,
    layersSettings: { bins: { fillColor: cfg.fillColor } },
  };
}
