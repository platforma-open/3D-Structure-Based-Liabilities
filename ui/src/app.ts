import { platforma } from "@platforma-open/milabs.3d-structure-based-liabilities.model";
import { defineAppV3 } from "@platforma-sdk/ui-vue";
import CysteinesPage from "./pages/CysteinesPage.vue";
import HistogramCdrh3CompactnessPage from "./pages/HistogramCdrh3CompactnessPage.vue";
import HistogramDevScorePage from "./pages/HistogramDevScorePage.vue";
import HistogramPncPage from "./pages/HistogramPncPage.vue";
import HistogramPpcPage from "./pages/HistogramPpcPage.vue";
import HistogramPshPage from "./pages/HistogramPshPage.vue";
import HistogramSfvcspPage from "./pages/HistogramSfvcspPage.vue";
import MainPage from "./pages/MainPage.vue";
import MotifsPage from "./pages/MotifsPage.vue";

export const sdkPlugin = defineAppV3(platforma, () => {
  return {
    routes: {
      "/": () => MainPage,
      // Spec R51 drill-downs — one PlAgDataTableV2 per page (multi-table
      // pages hit a race that keeps AG-Grid stuck in placeholder state).
      "/motifs": () => MotifsPage,
      "/cysteines": () => CysteinesPage,
      // Spec R54 — per-metric distribution histograms.
      "/histogram-psh": () => HistogramPshPage,
      "/histogram-ppc": () => HistogramPpcPage,
      "/histogram-pnc": () => HistogramPncPage,
      "/histogram-sfvcsp": () => HistogramSfvcspPage,
      "/histogram-cdrh3-compactness": () => HistogramCdrh3CompactnessPage,
      "/histogram-developability": () => HistogramDevScorePage,
    },
  };
});

export const useApp = sdkPlugin.useApp;
