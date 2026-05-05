<script setup lang="ts">
/**
 * PdbCountsTable
 * --------------
 * Generic two-column "name + bar" table used for the residue-type and
 * element-distribution sections. Each row's bar is sized as a percentage of
 * the largest count in the dataset, so the visual scale is internal to the
 * table (the longest bar always fills its cell).
 *
 * Optional `limit` truncates to the top N rows; useful for the residue-type
 * table which can have ~30 distinct codes including non-standard ones.
 */
import { computed } from "vue";
import type { CountEntry } from "../../pdb/derivations";
import { bar, barCellStyle, barTextStyle, pct } from "../../pdb/styles";

const props = defineProps<{
  title: string;
  keyHeader: string;
  rows: CountEntry[];
  color: string;
  limit?: number;
}>();

const visible = computed(() => (props.limit ? props.rows.slice(0, props.limit) : props.rows));
const max = computed(() => Math.max(1, ...props.rows.map((r) => r.count)));
</script>

<template>
  <h3>{{ title }}</h3>
  <table>
    <thead>
      <tr>
        <th>{{ keyHeader }}</th>
        <th>Atoms</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="r in visible" :key="r.key">
        <td>{{ r.key }}</td>
        <td :style="barCellStyle">
          <div :style="bar(pct(r.count, max), color)" />
          <span :style="barTextStyle">{{ r.count }}</span>
        </td>
      </tr>
    </tbody>
  </table>
</template>
