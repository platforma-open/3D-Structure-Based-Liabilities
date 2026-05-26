import type { PFrameHandle } from "@platforma-sdk/model";
import { getColumnsFull, getSingleColumnData } from "@platforma-sdk/model";
import { ref, watch, type ComputedRef } from "vue";

export type DetectedMode = "TAP" | "TNP";

/**
 * Dataset-level mode read from the per-clonotype `pl7.app/liabilities/mode`
 * column. Uniform across rows by R7 (one chain-count regime per upstream
 * PDB dataset). Spec text places this on `BlockData.detectedMode`, but a
 * model output callback cannot read PColumn data synchronously; deriving
 * from the scoresTable PFrame in a composable gives the same value to
 * R51 column visibility, R54 mode-specific histogram, and R55 subtitle.
 */
export function useDetectedMode(scoresPf: ComputedRef<PFrameHandle | undefined>) {
  const mode = ref<DetectedMode | undefined>(undefined);

  watch(
    scoresPf,
    async (handle) => {
      if (!handle) {
        mode.value = undefined;
        return;
      }
      try {
        const cols = await getColumnsFull(handle, {
          selectedSources: [],
          strictlyCompatible: false,
          names: ["pl7.app/liabilities/mode"],
        });
        const match = cols.find((c) => c.spec.valueType === "String");
        if (!match) {
          mode.value = undefined;
          return;
        }
        const { data } = await getSingleColumnData(handle, match.columnId);
        const first = data.find((v) => v === "TAP" || v === "TNP");
        mode.value = (first as DetectedMode | undefined) ?? undefined;
      } catch (err) {
        console.warn("useDetectedMode: failed to resolve mode", err);
        mode.value = undefined;
      }
    },
    { immediate: true },
  );

  return { mode };
}
