import type { GraphMakerState } from "@milaboratories/graph-maker";
import type {
  AxisId,
  ImportFileHandle,
  InferOutputsType,
  PColumnIdAndSpec,
  PFrameHandle,
  PlDataTableStateV2,
  PlRef,
  PrimaryRef,
} from "@platforma-sdk/model";
import {
  BlockModelV3,
  createPlDataTableStateV2,
  createPlDataTableV2,
  createPrimaryRef,
  DataModelBuilder,
  getAxisId,
  parseResourceMap,
} from "@platforma-sdk/model";

/** Spec R14 / R10 , numbering schemes supported for region tagging. */
export type NumberingScheme = "imgt" | "chothia" | "kabat";

/** Original shape; preserved so existing block instances migrate. */
type BlockDataV1 = {
  pdb: ImportFileHandle | undefined;
  tableState: PlDataTableStateV2;
};

/** v2: cysTableState was added alongside the motif tableState. */
type BlockDataV2 = BlockDataV1 & {
  cysTableState: PlDataTableStateV2;
};

/** v3: adds numbering scheme + heavy/light chain mapping so motif scoring
 * can apply R19 region weights and cysteines can be classified against
 * canonical positions (R21). All three are optional ("" / undefined means
 * "unknown" and motif scoring falls back to neutral weights). */
type BlockDataV3 = BlockDataV2 & {
  numberingScheme: NumberingScheme | "";
  heavyChainId: string;
  lightChainId: string;
};

/** v4 , adds R49 advanced thresholds (FR/CDR confidence gating + R12
 * buried/exposed rSASA cutoff). Defaults match the spec's calibrated
 * values for ImmuneBuilder. */
type BlockDataV4 = BlockDataV3 & {
  rsasaBuriedCutoff: number;
  frConfThresh: number;
  cdrConfThresh: number;
};

/** v5 , adds `pdbRef`, a `PlRef` pointing at an upstream
 * `pl7.app/structure/pdb` PColumn (Spec R1-R6). When set, the workflow
 * resolves it into per-clonotype PDBs and runs the software once per
 * clonotype; output PColumns then key on `pl7.app/vdj/scClonotypeKey`
 * rather than the `structureId="static"` placeholder.
 *
 * `pdb` (the legacy `ImportFileHandle` upload) stays for the local
 * single-PDB dev path (e.g. 1N8Z). When both are set, `pdbRef` wins. */
type BlockDataV5 = BlockDataV4 & {
  pdbRef?: PlRef;
};

/** v6 , adds `scoresTableState` for the per-clonotype scalar metrics
 * table (Spec R51). Surfaces the existing `scoresData` PFrame the
 * workflow already emits. */
type BlockDataV6 = BlockDataV5 & {
  scoresTableState: PlDataTableStateV2;
};

/** v7 , adds GraphMaker state for the six Spec R54 distribution histograms:
 * PSH, PPC, PNC, SFvCSP (Fv), CDRH3 compactness (VHH), and the composite
 * developability score. */
type BlockDataV7 = BlockDataV6 & {
  graphStatePshV2: GraphMakerState;
  graphStatePpcV2: GraphMakerState;
  graphStatePncV2: GraphMakerState;
  graphStateSfvcspV2: GraphMakerState;
  graphStateCdrh3CompactnessV2: GraphMakerState;
  graphStateDevScoreV2: GraphMakerState;
};

/** v8 , adds R48 hydrophobicity scale selector. Removed in v13 when
 * the spec refresh fixed Hydrophobicity to KD (R48 removed from the
 * requirements list, spec Concept line: "Hydrophobicity is KD
 * min-max-normalized to [1.0, 2.0]"). */
type BlockDataV8 = BlockDataV7 & {
  hydrophobicityScale: "kd" | "ww" | "hessa" | "em" | "bm";
};

/** v9 , strips the legacy single-PDB path's `pdb` field, the three
 * persisted-but-unused PlAgDataTable v-model states, and the six
 * GraphMakerState fields left over from the GraphMaker→SVG histogram
 * migration. */
type BlockDataV9 = Omit<
  BlockDataV8,
  | "pdb"
  | "tableState"
  | "cysTableState"
  | "scoresTableState"
  | "graphStatePshV2"
  | "graphStatePpcV2"
  | "graphStatePncV2"
  | "graphStateSfvcspV2"
  | "graphStateCdrh3CompactnessV2"
  | "graphStateDevScoreV2"
>;

/** v10 , drops `rsasaBuriedCutoff` per spec R12 (Raybould 0.075 is
 * hardcoded in the workflow now). */
type BlockDataV10 = Omit<BlockDataV9, "rsasaBuriedCutoff">;

/** v11 , replaces the bare `pdbRef: PlRef` field with a `primaryRef:
 * PrimaryRef` envelope per spec R1. */
type BlockDataV11 = Omit<BlockDataV10, "pdbRef"> & {
  primaryRef?: PrimaryRef;
};

/** v12 , adds the dataset-level `detectedMode` per the refreshed spec
 * (BlockData definition lines 222-231). Resolved by a UI watcher after
 * the first successful run from the per-clonotype `pl7.app/liabilities/mode`
 * column (uniform by R7); read by R51 (column selection), R54
 * (mode-specific histogram), R55 (subtitle prefix). */
type BlockDataV12 = BlockDataV11 & {
  detectedMode?: "TAP" | "TNP";
};

/** Current shape (v13) , drops `hydrophobicityScale` per the refreshed
 * spec. R48 (5-scale selector) is gone from the requirements; the spec
 * Concept locks Hydrophobicity to KD min-max-normalized to [1.0, 2.0]. */
export type BlockData = Omit<BlockDataV12, "hydrophobicityScale">;

const initialGraphState = (title: string, fillColor: string): GraphMakerState => ({
  title,
  template: "bins",
  currentTab: null,
  layersSettings: { bins: { fillColor } },
  axesSettings: {
    axisY: { axisLabelsAngle: 0 as const, scale: "linear" },
    other: { binsCount: 30 },
  },
});

const dataModel = new DataModelBuilder()
  .from<BlockDataV1>("v1")
  .migrate<BlockDataV2>("v2", (v1) => ({
    ...v1,
    cysTableState: createPlDataTableStateV2(),
  }))
  .migrate<BlockDataV3>("v3", (v2) => ({
    ...v2,
    numberingScheme: "",
    heavyChainId: "",
    lightChainId: "",
  }))
  .migrate<BlockDataV4>("v4", (v3) => ({
    ...v3,
    rsasaBuriedCutoff: 0.075,
    frConfThresh: 4.0,
    cdrConfThresh: 6.0,
  }))
  .migrate<BlockDataV5>("v5", (v4) => ({
    ...v4,
    pdbRef: undefined,
  }))
  .migrate<BlockDataV6>("v6", (v5) => ({
    ...v5,
    scoresTableState: createPlDataTableStateV2(),
  }))
  .migrate<BlockDataV7>("v7", (v6) => ({
    ...v6,
    graphStatePshV2: initialGraphState("PSH distribution", "#7da3d1"),
    graphStatePpcV2: initialGraphState("PPC distribution", "#e5a06f"),
    graphStatePncV2: initialGraphState("PNC distribution", "#82c79c"),
    graphStateSfvcspV2: initialGraphState("SFvCSP distribution (Fv)", "#bb86d6"),
    graphStateCdrh3CompactnessV2: initialGraphState(
      "CDRH3 compactness distribution (VHH)",
      "#d6b06b",
    ),
    graphStateDevScoreV2: initialGraphState("Developability score distribution", "#cf6e83"),
  }))
  .migrate<BlockDataV8>("v8", (v7) => ({
    ...v7,
    hydrophobicityScale: "kd",
  }))
  .migrate<BlockDataV9>("v9", (v8) => {
    // Strip the persisted-but-unused fields. Destructuring discards them
    // from the object literal returned to downstream code; the runtime
    // payload effectively shrinks for every block instance that lands
    // here. `_unused` names silence the no-unused-vars lint.
    const {
      pdb: _pdb,
      tableState: _t1,
      cysTableState: _t2,
      scoresTableState: _t3,
      graphStatePshV2: _g1,
      graphStatePpcV2: _g2,
      graphStatePncV2: _g3,
      graphStateSfvcspV2: _g4,
      graphStateCdrh3CompactnessV2: _g5,
      graphStateDevScoreV2: _g6,
      ...rest
    } = v8;
    return rest;
  })
  .migrate<BlockDataV10>("v10", (v9) => {
    // Spec R12 , drop the user-tunable rSASA cutoff; the python defaults
    // to 0.075 (the canonical Raybould 2019 value) and the workflow no
    // longer overrides it.
    const { rsasaBuriedCutoff: _r, ...rest } = v9;
    return rest;
  })
  .migrate<BlockDataV11>("v11", (v10) => {
    // Spec R1 , wire shape moves from bare `pdbRef: PlRef` to the
    // `PrimaryRef` envelope `{column: PlRef, filter?: PlRef}` so the
    // block accepts a properly typed primary input. Existing
    // installations have a PlRef in `pdbRef`; we wrap it via
    // `createPrimaryRef` (filter stays undefined for now, R47 fills
    // it in later).
    const { pdbRef, ...rest } = v10;
    return {
      ...rest,
      primaryRef: pdbRef ? createPrimaryRef(pdbRef) : undefined,
    };
  })
  .migrate<BlockDataV12>("v12", (v11) => ({
    // Spec BlockData definition (lines 222-231): dataset-level
    // detectedMode resolved by the UI after the first successful run.
    // Undefined until then, so the migration just adds the field as
    // undefined; the UI watcher fills it once scoresTable is ready.
    ...v11,
    detectedMode: undefined,
  }))
  .migrate<BlockData>("v13", (v12) => {
    // R48 dropped from the refreshed spec; existing instances may carry
    // the legacy field. Strip it so the model shape matches the new spec.
    const { hydrophobicityScale: _drop, ...rest } = v12;
    return rest;
  })
  .init(() => ({
    primaryRef: undefined,
    // R14 default scheme , upstream's 3D Structure Prediction block always
    // produces IMGT-numbered PDBs (the `pl7.app/structure/numbering` domain
    // we match on already requires `imgt`), so defaulting here saves the
    // first-run user a dropdown click. Override if you're feeding the block
    // a custom non-IMGT PDB.
    numberingScheme: "imgt",
    heavyChainId: "",
    lightChainId: "",
    frConfThresh: 4.0,
    cdrConfThresh: 6.0,
  }));

export const platforma = BlockModelV3.create(dataModel)
  .args((data) => {
    // Spec R1 , primary input is a `PrimaryRef` envelope; the workflow's
    // `wf.prepare` resolves `primaryRef.column` (the PlRef inside the
    // envelope) into per-clonotype PDBs and iterates via
    // `pframes.processColumn`. The envelope's optional `filter` slot
    // (clonotype subset, R47) is not yet wired through , primaryRef
    // is constructed with no filter today.
    if (!data.primaryRef?.column) {
      throw new Error("Pick a predicted structures dataset");
    }
    return {
      primaryRef: data.primaryRef,
      numberingScheme: data.numberingScheme,
      heavyChainId: data.heavyChainId,
      lightChainId: data.lightChainId,
      frConfThresh: data.frConfThresh,
      cdrConfThresh: data.cdrConfThresh,
    };
  })
  // Spec R1-R6 , surface `pl7.app/structure/pdb` PColumns from the result
  // pool so the UI can show a dropdown of predicted-structure datasets.
  // Matches what the 3D Structure Prediction block exports (`pdbsMap`
  // PFrame, IMGT-numbered PDBs keyed by clonotype).
  .output("pdbOptions", (ctx) =>
    ctx.resultPool.getOptions([
      {
        name: "pl7.app/structure/pdb",
        domain: { "pl7.app/structure/numbering": "imgt" },
      },
    ]),
  )
  // Pass `undefined` for tableState (instead of ctx.data.tableState) so
  // grid state writes via the UI's v-model don't trigger model re-runs ,
  // that feedback loop kept AG-Grid in placeholder state on multi-table
  // pages. UI binds v-model to local refs to preserve state per-session.
  .outputWithStatus("motifsTable", (ctx) => {
    const pCols = ctx.outputs?.resolve("motifsData")?.getPColumns();
    if (pCols === undefined) return undefined;
    return createPlDataTableV2(ctx, pCols, undefined);
  })
  .outputWithStatus("cysTable", (ctx) => {
    const pCols = ctx.outputs?.resolve("cysData")?.getPColumns();
    if (pCols === undefined) return undefined;
    return createPlDataTableV2(ctx, pCols, undefined);
  })
  // Spec R51 , per-clonotype scalar metrics table. PColumns come from the
  // PrimaryRef-path `scoresData` PFrame (axes: [scClonotypeKey]). Hidden
  // on the legacy single-PDB path (`scoresData` not emitted; resolve
  // returns undefined).
  //
  // Isolation test: pass `undefined` for tableState (instead of
  // ctx.data.scoresTableState) so AG-Grid state writes don't trigger model
  // re-runs. If this lets the table render rows, the bug is the
  // model→UI→model feedback loop via v-model on table state.
  //
  // Spec R5 , upstream `pl7.app/structure/cdrh3Length` is enriched in as
  // an additional column so the user can sanity-check our REMARK 99 / scheme
  // fallback against the prediction block's CDRH3 length. Auto-joined on
  // the shared `pl7.app/vdj/scClonotypeKey` axis by the PFrame driver.
  .outputWithStatus("scoresTable", (ctx) => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const upstreamCdrh3 = ctx.resultPool.findDataWithCompatibleSpec({
      kind: "PColumn",
      name: "pl7.app/structure/cdrh3Length",
      valueType: "Long",
      axesSpec: [{ type: "String", name: "pl7.app/vdj/scClonotypeKey" }],
    });
    // Upstream emits a single-axis String `pl7.app/label` column anchored
    // on `scClonotypeKey`. PlAgDataTable's isLabelColumn picks it up and
    // substitutes the label into the row-axis cell display, so opaque
    // clonotype keys become readable clone names.
    const upstreamLabel = ctx.resultPool.findDataWithCompatibleSpec({
      kind: "PColumn",
      name: "pl7.app/label",
      valueType: "String",
      axesSpec: [{ type: "String", name: "pl7.app/vdj/scClonotypeKey" }],
    });
    // Spec R42 , surface the cluster axis when the 3D Structure Clustering
    // block is upstream. The block emits these on the same scClonotypeKey
    // axis, so the PFrame driver auto-joins them into per-clonotype rows.
    // Users can then sort / filter / group by cluster in the table UI.
    // No-op (empty join) when no clustering block is in the pipeline.
    const clusterId = ctx.resultPool.findDataWithCompatibleSpec({
      kind: "PColumn",
      name: "pl7.app/clusterId",
      valueType: "String",
      axesSpec: [{ type: "String", name: "pl7.app/vdj/scClonotypeKey" }],
    });
    const isCentroid = ctx.resultPool.findDataWithCompatibleSpec({
      kind: "PColumn",
      name: "pl7.app/structure/clustering/isCentroid",
      valueType: "Int",
      axesSpec: [{ type: "String", name: "pl7.app/vdj/scClonotypeKey" }],
    });
    const tmDistance = ctx.resultPool.findDataWithCompatibleSpec({
      kind: "PColumn",
      name: "pl7.app/structure/clustering/tmDistanceToCentroid",
      valueType: "Double",
      axesSpec: [{ type: "String", name: "pl7.app/vdj/scClonotypeKey" }],
    });
    const tmScore = ctx.resultPool.findDataWithCompatibleSpec({
      kind: "PColumn",
      name: "pl7.app/structure/clustering/tmScoreToCentroid",
      valueType: "Double",
      axesSpec: [{ type: "String", name: "pl7.app/vdj/scClonotypeKey" }],
    });
    // Spec R51 , default-visible columns include the mode-appropriate
    // flag only. Mode lives on `BlockData.detectedMode`, filled by the UI
    // watcher after the first successful run. Until it is set, both
    // flags fall through to their workflow-side default (visible).
    const mode = ctx.data?.detectedMode;
    const modeSpecific: Record<string, "TAP" | "TNP"> = {
      "pl7.app/liabilities/sfvcspFlag": "TAP",
      "pl7.app/liabilities/cdrh3CompactnessFlag": "TNP",
    };
    const pColsForMode = pCols.map((c) => {
      const owner = modeSpecific[c.spec.name];
      if (!owner || !mode) return c;
      const annotations = { ...(c.spec.annotations ?? {}) };
      annotations["pl7.app/table/visibility"] = owner === mode ? "default" : "optional";
      return { ...c, spec: { ...c.spec, annotations } };
    });
    const allCols = [
      ...pColsForMode,
      ...(upstreamCdrh3 as typeof pCols),
      ...(upstreamLabel as typeof pCols),
      ...(clusterId as typeof pCols),
      ...(isCentroid as typeof pCols),
      ...(tmDistance as typeof pCols),
      ...(tmScore as typeof pCols),
    ];
    return createPlDataTableV2(ctx, allCols, undefined);
  })
  // Spec R54 , per-metric histograms. One PFrame + Spec output pair per
  // metric. We use `ctx.createPFrame([col])` rather than
  // `createPFrameForGraphs` because the latter pulls related columns
  // from the result pool (everything sharing the scClonotypeKey axis):
  // psh, ppc, cdrh3Length, etc. all end up in the same PFrame, and
  // graph-maker picks the first numeric column it sees regardless of
  // our defaultOptions binding. Single-column PFrame removes the
  // ambiguity.
  .outputWithStatus("pshPf", (ctx): PFrameHandle | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find((c) => c.spec.name === "pl7.app/liabilities/psh");
    if (!col) return undefined;
    return ctx.createPFrame([col]);
  })
  .output("pshSpec", (ctx): PColumnIdAndSpec | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find((c) => c.spec.name === "pl7.app/liabilities/psh");
    return col ? { columnId: col.id, spec: col.spec } : undefined;
  })
  .outputWithStatus("ppcPf", (ctx): PFrameHandle | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find((c) => c.spec.name === "pl7.app/liabilities/ppc");
    if (!col) return undefined;
    return ctx.createPFrame([col]);
  })
  .output("ppcSpec", (ctx): PColumnIdAndSpec | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find((c) => c.spec.name === "pl7.app/liabilities/ppc");
    return col ? { columnId: col.id, spec: col.spec } : undefined;
  })
  .outputWithStatus("pncPf", (ctx): PFrameHandle | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find((c) => c.spec.name === "pl7.app/liabilities/pnc");
    if (!col) return undefined;
    return ctx.createPFrame([col]);
  })
  .output("pncSpec", (ctx): PColumnIdAndSpec | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find((c) => c.spec.name === "pl7.app/liabilities/pnc");
    return col ? { columnId: col.id, spec: col.spec } : undefined;
  })
  .outputWithStatus("sfvcspPf", (ctx): PFrameHandle | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find((c) => c.spec.name === "pl7.app/liabilities/sfvcsp");
    if (!col) return undefined;
    return ctx.createPFrame([col]);
  })
  .output("sfvcspSpec", (ctx): PColumnIdAndSpec | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find((c) => c.spec.name === "pl7.app/liabilities/sfvcsp");
    return col ? { columnId: col.id, spec: col.spec } : undefined;
  })
  .outputWithStatus("cdrh3CompactnessPf", (ctx): PFrameHandle | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find((c) => c.spec.name === "pl7.app/liabilities/cdrh3Compactness");
    if (!col) return undefined;
    return ctx.createPFrame([col]);
  })
  .output("cdrh3CompactnessSpec", (ctx): PColumnIdAndSpec | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find((c) => c.spec.name === "pl7.app/liabilities/cdrh3Compactness");
    return col ? { columnId: col.id, spec: col.spec } : undefined;
  })
  .outputWithStatus("devScorePf", (ctx): PFrameHandle | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find(
      (c) => c.spec.name === "pl7.app/liabilities/structuralDevelopabilityScore",
    );
    if (!col) return undefined;
    return ctx.createPFrame([col]);
  })
  .output("devScoreSpec", (ctx): PColumnIdAndSpec | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find(
      (c) => c.spec.name === "pl7.app/liabilities/structuralDevelopabilityScore",
    );
    return col ? { columnId: col.id, spec: col.spec } : undefined;
  })
  // Upstream `pl7.app/label` column anchored on scClonotypeKey. Exposed as
  // a standalone PFrame so the strip plot can resolve readable clone names
  // for each dot; the scoresTable already auto-substitutes labels in its
  // row-axis cell display via PlAgDataTable's isLabelColumn detection.
  .output("clonotypeLabelsPf", (ctx): PFrameHandle | undefined => {
    // Source from scoresData.getPColumns() instead of resultPool query.
    // The PFrame driver auto-joins upstream `pl7.app/label` (and other
    // scClonotypeKey-anchored columns) into scoresData's column set, but
    // resultPool.findDataWithCompatibleSpec returns empty here in
    // PrimaryRef-path runs. Mirrors 3d-structure-prediction's model
    // pattern (structuresTable.getPColumns()).
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (!pCols) return undefined;
    const labelCol = pCols.find(
      (c) =>
        c.spec.name === "pl7.app/label" &&
        c.spec.axesSpec.length === 1 &&
        c.spec.axesSpec[0].name === "pl7.app/vdj/scClonotypeKey",
    );
    if (!labelCol) return undefined;
    return ctx.createPFrame([labelCol]);
  })
  // Spec R52 , per-clonotype PDB ResourceMap exposed for the viewer modal.
  // Reads the upstream `pl7.app/structure/pdb` PColumn (axis:
  // scClonotypeKey, valueType File) and parses it into [{key, value}]
  // pairs; UI consumes via `entry.value.handle` (a RemoteBlobHandle) and
  // hands it to PlStructureViewer.
  .output("clonotypePdbsMap", (ctx) => {
    // Resolve through the user-picked PlRef inside the PrimaryRef
    // envelope rather than fuzzy-matching the result pool. The PlRef
    // lives at `primaryRef.column` (spec R1); `findDataWithCompatibleSpec`
    // was returning empty here even with name + valueType + axes + domain
    // all aligned, so we use the canonical ref-based path , same as how
    // the workflow accesses it.
    const ref = ctx.args?.primaryRef?.column ?? ctx.data?.primaryRef?.column;
    if (!ref) return undefined;
    const pdbCol = ctx.resultPool.getPColumnByRef(ref);
    if (!pdbCol) return undefined;
    const parsed = parseResourceMap(
      (pdbCol as unknown as { data: unknown }).data as never,
      (acc) => acc.getRemoteFileHandle(),
      false,
    );
    if (!parsed.isComplete) return undefined;
    return parsed.data;
  })
  // Spec R52 , axis identifier for the scClonotypeKey axis on the scoresTable.
  // UI uses this to attach PlAgDataTable's `show-cell-button-for-axis-id`
  // so the viewer-trigger button renders on the clonotype-key column.
  .output("clonotypeAxisId", (ctx): AxisId | undefined => {
    // Resolve through the user-picked PlRef inside the PrimaryRef envelope
    // (spec R1), then read its spec.
    const ref = ctx.args?.primaryRef?.column ?? ctx.data?.primaryRef?.column;
    if (!ref) return undefined;
    const pdbSpec = ctx.resultPool.getPColumnSpecByRef(ref);
    if (!pdbSpec) return undefined;
    // The upstream PDB column carries [sampleId, scClonotypeKey] , match
    // the clonotype axis by name rather than index, since `[0]` is
    // sampleId here and the cell button must hang off the clonotype axis.
    const found = pdbSpec.axesSpec.find((a) => a.name === "pl7.app/vdj/scClonotypeKey");
    if (!found) return undefined;
    // Return a stripped AxisId , `PlAgDataTableV2` does an `isJsonEqual`
    // against its own column's axisId (run through `getAxisId`, dropping
    // `annotations` etc). Returning the raw `AxisSpec` with extra fields
    // silently breaks the deep-equal check → no open button renders.
    return getAxisId(found);
  })
  .sections((ctx) => {
    const mode = ctx.data?.detectedMode;
    // Spec R54 mode-specific slot. Before the first successful run the
    // mode is undefined and the slot label is generic; once resolved it
    // names the active metric so the sidebar reads as the slot's content.
    const modeSpecificLabel =
      mode === "TNP"
        ? "CDRH3 compactness (VHH)"
        : mode === "TAP"
          ? "SFvCSP (Fv)"
          : "Mode-specific distribution";
    return [
      { type: "link", href: "/", label: "Main" },
      { type: "link", href: "/motifs", label: "Motifs" },
      { type: "link", href: "/cysteines", label: "Cysteine state" },
      { type: "link", href: "/histogram-psh", label: "PSH distribution" },
      { type: "link", href: "/histogram-ppc", label: "PPC distribution" },
      { type: "link", href: "/histogram-pnc", label: "PNC distribution" },
      { type: "link", href: "/histogram-mode-specific", label: modeSpecificLabel },
      { type: "link", href: "/histogram-developability", label: "Developability score" },
    ];
  })
  .title(() => "3D Structure-Based Liabilities")
  // Spec R55 , active-parameter summary at the block header. Mode prefix
  // comes from BlockData.detectedMode; before the first successful run it
  // is omitted (the field is undefined and we just show the cutoffs).
  // Format: "TAP, rSASA<0.075, confidence-gated FR>4 Å / CDR>6 Å".
  .subtitle((ctx) => {
    if (!ctx.args) return "";
    const a = ctx.args;
    const mode = ctx.data?.detectedMode;
    const fr = Number.isInteger(a.frConfThresh) ? a.frConfThresh : a.frConfThresh.toFixed(1);
    const cdr = Number.isInteger(a.cdrConfThresh) ? a.cdrConfThresh : a.cdrConfThresh.toFixed(1);
    const tail = `rSASA<0.075, confidence-gated FR>${fr} Å / CDR>${cdr} Å`;
    return mode ? `${mode}, ${tail}` : tail;
  })
  .done();

export type BlockOutputs = InferOutputsType<typeof platforma>;
