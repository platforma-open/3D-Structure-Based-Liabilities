<script setup lang="ts">
import type { GraphMakerState, PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import type { PColumnIdAndSpec } from "@platforma-sdk/model";
import { PlBlockPage } from "@platforma-sdk/ui-vue";
import { computed } from "vue";

// GraphMaker's `pFrame` prop expects `OutputWithStatus<PFrameHandle>` from
// pl-model-common. That type isn't directly importable through the SDK
// re-exports at this block's pinned version, and BlockOutputs adds an
// `__unwrap: false` marker that's incompatible with GraphMaker's prop
// shape. Accept `unknown` here and cast through `as never` at the call
// site — runtime contract is duck-typed (GraphMaker reads `.ok` / `.value`).
type PFrameOutput = unknown;

/**
 * Reusable Spec R54 histogram page. Each block instance binds a single
 * scoresData scalar column (PSH / PPC / PNC / SFvCSP / cdrh3Compactness /
 * developability score) to GraphMaker's histogram chart.
 *
 * Threshold lines (R54 — Raybould amber/red bands) are NOT drawn yet —
 * `composeHistogramSettings` in `@milaboratories/graph-maker` doesn't
 * currently honour the `pl7.app/graph/thresholds` column annotation (only
 * the scatter path does). The workflow still emits the annotation so the
 * lines will appear automatically once graph-maker's histogram code path
 * picks it up.
 */
const props = defineProps<{
  pframe: PFrameOutput | undefined;
  spec: PColumnIdAndSpec | undefined;
  state: GraphMakerState;
  /** Section heading. e.g. "PSH — Patches of Surface Hydrophobicity". */
  title: string;
  /** One-paragraph plain-English explanation of what the metric measures
   * and which direction is bad (Raybould-2019-style risk semantics). */
  description: string;
  /** Raybould 2019 / Gordon 2025 amber/red threshold text. Plain English
   * because GraphMaker's histogram code path doesn't yet honor the
   * `pl7.app/graph/thresholds` column annotation (only the scatter path
   * does); once it does, these will render as dashed lines on the chart
   * and we can drop the prose. */
  thresholds?: string;
  notReadyTitle?: string;
}>();
const emit = defineEmits<{
  "update:state": [GraphMakerState];
}>();

const stateModel = computed({
  get: () => props.state,
  set: (v: GraphMakerState) => emit("update:state", v),
});

const defaults = computed((): PredefinedGraphOption<"histogram">[] | undefined => {
  if (!props.spec?.spec) return undefined;
  return [{ inputName: "value", selectedSource: props.spec.spec }];
});
</script>

<template>
  <PlBlockPage :title="title">
    <p :style="{ fontSize: '13px', color: '#374151', marginTop: '8px', lineHeight: '1.5' }">
      {{ description }}
    </p>
    <p
      v-if="thresholds"
      :style="{
        fontSize: '12px',
        color: '#6b7280',
        marginTop: '4px',
        fontStyle: 'italic',
        lineHeight: '1.5',
      }"
    >
      <strong>Thresholds:</strong> {{ thresholds }}
    </p>
    <p
      :style="{
        fontSize: '11px',
        color: '#a16207',
        background: 'rgba(252, 211, 77, 0.15)',
        border: '1px solid rgba(252, 211, 77, 0.4)',
        borderRadius: '4px',
        padding: '6px 10px',
        marginTop: '8px',
        marginBottom: '12px',
        lineHeight: '1.5',
      }"
    >
      <strong>Note on histogram interpretation at small N:</strong> below ~20 clonotypes each bar
      represents one (or a few) clonotypes, not a distribution shape. Read individual values from
      the Main table instead. Histograms are calibrated against the Raybould 2019 cohort of 242
      antibodies — they become informative once your dataset reaches that scale.
    </p>
    <!-- GraphMaker's pFrame prop is required (typed OutputWithStatus<PFrameHandle>,
         non-nullable). Hide the component entirely while the upstream is
         pending — gives the user a quiet page instead of a typed crash. -->
    <GraphMaker
      v-if="pframe"
      v-model="stateModel"
      chart-type="histogram"
      :data-state-key="pframe as never"
      :p-frame="pframe as never"
      :default-options="defaults"
      :status-text="{
        noPframe: {
          title:
            notReadyTitle ??
            'Run the workflow on a predicted-structures dataset to see the distribution',
        },
      }"
    />
    <p v-else :style="{ fontSize: '14px', color: '#6b7280', marginTop: '12px' }">
      {{
        notReadyTitle ??
        "Run the workflow on a predicted-structures dataset to see the distribution"
      }}
    </p>
  </PlBlockPage>
</template>
