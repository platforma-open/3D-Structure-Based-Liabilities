<script setup lang="ts">
/**
 * MainPage
 * --------
 * Thin orchestrator for the PDB report: takes the raw PDB content output
 * from the workflow, parses it once, computes each visualization's data
 * shape via pure derivation functions, and hands the results to the
 * dedicated `Pdb*` components for rendering.
 *
 * No visualization logic lives here — see `src/pdb/parser.ts`,
 * `src/pdb/derivations.ts`, and `src/components/pdb/*.vue` for that.
 */
import { computedResult, PlBlockPage, PlFileInput } from "@platforma-sdk/ui-vue";
import { computed } from "vue";
import { useApp } from "../app";

import { parsePdb } from "../pdb/parser";
import {
  allBFactors,
  bFactorByChain,
  bounds,
  chainSummary,
  contactMap,
  elements,
  residueTypes,
  sequences,
  ssByChain,
  ssCounts,
  validation,
} from "../pdb/derivations";
import {
  deamidationHotspots,
  glycosylationSequons,
  oxidationHotspots,
  unpairedCysteines,
} from "../pdb/liabilities";

import PdbBFactorHistogram from "../components/pdb/PdbBFactorHistogram.vue";
import PdbChains from "../components/pdb/PdbChains.vue";
import PdbContactMap from "../components/pdb/PdbContactMap.vue";
import PdbCountsTable from "../components/pdb/PdbCountsTable.vue";
import PdbDisulfides from "../components/pdb/PdbDisulfides.vue";
import PdbLiabilityList from "../components/pdb/PdbLiabilityList.vue";
import PdbModifiedResidues from "../components/pdb/PdbModifiedResidues.vue";
import PdbSecondaryStructure from "../components/pdb/PdbSecondaryStructure.vue";
import PdbSequences from "../components/pdb/PdbSequences.vue";
import PdbSummary from "../components/pdb/PdbSummary.vue";
import PdbValidation from "../components/pdb/PdbValidation.vue";

const app = useApp();
const pdbContent = computedResult(() => app.model.outputs.pdbContent);

const parsed = computed(() => {
  const text = pdbContent.value.value;
  return text ? parsePdb(text) : null;
});

const chains = computed(() => (parsed.value ? chainSummary(parsed.value) : []));
const ss = computed(() => (parsed.value ? ssByChain(parsed.value) : new Map()));
const ssAgg = computed(() => ssCounts(ss.value));
const seq = computed(() => (parsed.value ? sequences(parsed.value, ss.value) : []));
const valid = computed(() => (parsed.value ? validation(parsed.value) : []));
const bFactorChains = computed(() => (parsed.value ? bFactorByChain(parsed.value) : new Map()));
const resTypes = computed(() => (parsed.value ? residueTypes(parsed.value) : []));
const elems = computed(() => (parsed.value ? elements(parsed.value) : []));
const bFactors = computed(() => (parsed.value ? allBFactors(parsed.value) : []));
const xyzBounds = computed(() => (parsed.value ? bounds(parsed.value) : null));
const contacts = computed(() => (parsed.value ? contactMap(parsed.value) : null));

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
      <PdbSummary :parsed="parsed" :chains="chains" :bounds="xyzBounds" />
      <PdbSecondaryStructure :counts="ssAgg" />
      <PdbChains :chains="chains" :b-factor-profiles="bFactorChains" />
      <PdbSequences :sequences="seq" />
      <PdbValidation :rows="valid" />
      <PdbCountsTable
        title="Residue types"
        key-header="Residue"
        :rows="resTypes"
        color="rgba(139, 92, 246, 0.35)"
        :limit="20"
      />
      <PdbCountsTable
        title="Elements"
        key-header="Element"
        :rows="elems"
        color="rgba(245, 158, 11, 0.45)"
      />
      <PdbBFactorHistogram :values="bFactors" />
      <PdbContactMap v-if="contacts" :data="contacts" />
      <PdbDisulfides v-if="parsed.ssbonds.length" :bonds="parsed.ssbonds" />
      <PdbModifiedResidues v-if="parsed.modres.length" :modres="parsed.modres" />

      <h2>Sequence-based liabilities</h2>
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
        description="Methionine and tryptophan positions. Real risk depends on solvent exposure needs SASA filtering (next pass)."
        :hits="oxidations"
      />
    </div>
  </PlBlockPage>
</template>
