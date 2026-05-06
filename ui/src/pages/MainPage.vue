<script setup lang="ts">
/**
 * MainPage
 * --------
 * Parses the uploaded PDB and renders the four sequence-based liability
 * detectors. No structural / descriptive views — those were stripped.
 */
import { computedResult, PlBlockPage, PlFileInput } from "@platforma-sdk/ui-vue";
import { computed } from "vue";
import { useApp } from "../app";

import { parsePdb } from "../pdb/parser";
import {
  deamidationHotspots,
  glycosylationSequons,
  oxidationHotspots,
  unpairedCysteines,
} from "../pdb/liabilities";

import PdbLiabilityList from "../components/pdb/PdbLiabilityList.vue";
import PdbLiabilityMap from "../components/pdb/PdbLiabilityMap.vue";

const app = useApp();
const pdbContent = computedResult(() => app.model.outputs.pdbContent);

const parsed = computed(() => {
  const text = pdbContent.value.value;
  return text ? parsePdb(text) : null;
});

const unpairedCys = computed(() => (parsed.value ? unpairedCysteines(parsed.value) : []));
const deamidations = computed(() => (parsed.value ? deamidationHotspots(parsed.value) : []));
const glycosylations = computed(() => (parsed.value ? glycosylationSequons(parsed.value) : []));
const oxidations = computed(() => (parsed.value ? oxidationHotspots(parsed.value) : []));
</script>

<template>
  <PlBlockPage>
    <PlFileInput
      v-model="app.model.data.pdb"
      label="PDB file"
      :extensions="['.pdb']"
      placeholder="Drop a .pdb file"
      required
      clearable
    />

    <div v-if="parsed">
      <PdbLiabilityMap
        :parsed="parsed"
        :unpaired-cys="unpairedCys"
        :deamidations="deamidations"
        :glycosylations="glycosylations"
        :oxidations="oxidations"
      />
      <PdbLiabilityList
        v-if="unpairedCys.length"
        title="Unpaired cysteines"
        description="Cys residues not participating in any disulfide bond. Free Cys can drive aggregation, mispair during expression, or be oxidized."
        :hits="unpairedCys"
      />
      <PdbLiabilityList
        v-if="deamidations.length"
        title="Deamidation hotspots"
        description="N-G and N-S dipeptides — asparagine residues most prone to non-enzymatic deamidation to aspartate / iso-aspartate over time."
        :hits="deamidations"
      />
      <PdbLiabilityList
        v-if="glycosylations.length"
        title="N-glycosylation sequons"
        description="Consensus N-X-[S/T] motifs (X ≠ P). Surface-exposed sequons in CDRs are a major manufacturability risk."
        :hits="glycosylations"
      />
      <PdbLiabilityList
        v-if="oxidations.length"
        title="Oxidation-prone residues"
        description="Methionine and tryptophan positions. Real risk depends on solvent exposure — needs SASA filtering (next pass)."
        :hits="oxidations"
      />
    </div>
  </PlBlockPage>
</template>
