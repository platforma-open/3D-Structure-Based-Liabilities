import { platforma } from "@platforma-open/milaboratories.3d-structure-based-liabilities.model";
import { defineAppV3 } from "@platforma-sdk/ui-vue";
import HistogramDevScorePage from "./pages/HistogramDevScorePage.vue";
import HistogramModeSpecificPage from "./pages/HistogramModeSpecificPage.vue";
import HistogramPncPage from "./pages/HistogramPncPage.vue";
import HistogramPpcPage from "./pages/HistogramPpcPage.vue";
import HistogramPshPage from "./pages/HistogramPshPage.vue";
import MainPage from "./pages/MainPage.vue";

export const sdkPlugin = defineAppV3(platforma, () => {
  return {
    routes: {
      "/": () => MainPage,
      // The mode-specific slot resolves to SFvCSP (TAP) or CDRH3 compactness
      // (TNP) at render time from the workflow's detectedMode output.
      "/histogram-psh": () => HistogramPshPage,
      "/histogram-ppc": () => HistogramPpcPage,
      "/histogram-pnc": () => HistogramPncPage,
      "/histogram-mode-specific": () => HistogramModeSpecificPage,
      "/histogram-developability": () => HistogramDevScorePage,
    },
  };
});

export const useApp = sdkPlugin.useApp;
