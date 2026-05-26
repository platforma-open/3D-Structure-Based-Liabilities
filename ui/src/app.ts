import { platforma } from "@platforma-open/milabs.3d-structure-based-liabilities.model";
import { defineAppV3 } from "@platforma-sdk/ui-vue";
import CysteinesPage from "./pages/CysteinesPage.vue";
import HistogramDevScorePage from "./pages/HistogramDevScorePage.vue";
import HistogramModeSpecificPage from "./pages/HistogramModeSpecificPage.vue";
import HistogramPncPage from "./pages/HistogramPncPage.vue";
import HistogramPpcPage from "./pages/HistogramPpcPage.vue";
import HistogramPshPage from "./pages/HistogramPshPage.vue";
import MainPage from "./pages/MainPage.vue";
import MotifsPage from "./pages/MotifsPage.vue";

export const sdkPlugin = defineAppV3(platforma, () => {
  return {
    routes: {
      "/": () => MainPage,
      // Spec R51 drill-downs , one PlAgDataTableV2 per page (multi-table
      // pages hit a race that keeps AG-Grid stuck in placeholder state).
      "/motifs": () => MotifsPage,
      "/cysteines": () => CysteinesPage,
      // Spec R54 , five distribution histograms. The mode-specific slot
      // resolves to SFvCSP (TAP) or CDRH3 compactness (TNP) at render
      // time from BlockData.detectedMode.
      "/histogram-psh": () => HistogramPshPage,
      "/histogram-ppc": () => HistogramPpcPage,
      "/histogram-pnc": () => HistogramPncPage,
      "/histogram-mode-specific": () => HistogramModeSpecificPage,
      "/histogram-developability": () => HistogramDevScorePage,
    },
  };
});

export const useApp = sdkPlugin.useApp;
