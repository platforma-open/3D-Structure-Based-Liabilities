import type { LiabilitiesReport } from "@platforma-open/milabs.3d-structure-based-liabilities.model";
import { getRawPlatformaInstance } from "@platforma-sdk/model";
import { ref, watchEffect, type ComputedRef, type Ref } from "vue";

/**
 * Spec R53 — fetch the per-clonotype `liabilities.json` blob for the
 * currently-selected clonotype and parse it into a LiabilitiesReport.
 *
 * The blob driver fetch is async; if the user clicks through several
 * clonotypes quickly we'd race. `expectedKey` captured at the start of
 * each effect ensures only the most recently-selected fetch lands in
 * `detailReport`. Earlier in-flight fetches that resolve afterwards see
 * the stale key and bail.
 */
type JsonResourceMapEntry = { key: unknown[]; value?: { handle?: unknown } };

export function useClonotypeDetailFetch(
  selectedClonotypeKey: Ref<string | null>,
  jsonsMap: ComputedRef<JsonResourceMapEntry[] | undefined>,
) {
  const detailReport = ref<LiabilitiesReport | null>(null);

  watchEffect(async () => {
    const key = selectedClonotypeKey.value;
    detailReport.value = null;
    if (!key) return;
    const jsonHandle = jsonsMap.value?.find((e) => String(e.key.at(0)) === key)?.value?.handle;
    if (!jsonHandle) return;
    const expectedKey = key;
    try {
      const bytes = await getRawPlatformaInstance().blobDriver.getContent(jsonHandle as never);
      if (selectedClonotypeKey.value !== expectedKey) return;
      const text = new TextDecoder().decode(bytes);
      detailReport.value = JSON.parse(text) as LiabilitiesReport;
    } catch (err) {
      console.warn("[liabilities] failed to load per-clonotype JSON", err);
    }
  });

  return { detailReport };
}
