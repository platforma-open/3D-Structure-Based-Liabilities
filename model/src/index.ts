import type {
  AxisId,
  BlockRenderCtx,
  DatasetOption,
  DatasetSelection,
  InferOutputsType,
  PColumn,
  PColumnDataUniversal,
  PColumnIdAndSpec,
  PFrameHandle,
  PObjectSpec,
  PlRef,
  ValueType,
} from "@platforma-sdk/model";
import {
  BlockModelV3,
  buildDatasetOptions,
  createPlDataTableV2,
  DataModelBuilder,
  getAxisId,
  isPColumnSpec,
  parseResourceMap,
} from "@platforma-sdk/model";

/** Spec R14 / R10: numbering schemes supported for region tagging. */
export type NumberingScheme = "imgt" | "chothia" | "kabat";

export type BlockData = {
  /** Spec R1 / R46 dataset envelope picked via `PlDatasetSelector`.
   * `.args()` unwraps `dataset.primary` back into the `PrimaryRef`
   * shape the workflow's `wf.prepare` already knows how to resolve. */
  dataset?: DatasetSelection;
  /** R14 / R10 numbering scheme: empty string means unknown (motif
   * scoring then falls back to neutral region weights). */
  numberingScheme: NumberingScheme | "";
  /** R9 heavy / light chain overrides. Auto-detected from REMARK 99
   * PLATFORMA CDR records; these fields are populated only when the
   * user needs to override the detected mapping (e.g. on PDBs without
   * REMARK 99 records). */
  heavyChainId: string;
  lightChainId: string;
  /** R34 region-aware confidence gating thresholds (Å). Calibrated for
   * ImmuneBuilder per-atom predicted error; raise for crystal PDBs
   * whose B-factor column carries Å² temperature factors. */
  frConfThresh: number;
  cdrConfThresh: number;
  /** Spec BlockData.detectedMode: dataset-level TAP / TNP resolved by
   * the UI after the first successful run from the per-clonotype
   * `pl7.app/liabilities/mode` column (uniform by R7). Drives R51
   * mode-specific column visibility, R54 mode-specific histogram
   * dispatch, and the R55 subtitle prefix. */
  detectedMode?: "TAP" | "TNP";
};

const dataModel = new DataModelBuilder().from<BlockData>("v1").init(() => ({
  dataset: undefined,
  // R14 default scheme: upstream's 3D Structure Prediction block always
  // produces IMGT-numbered PDBs (the `pl7.app/structure/numbering`
  // domain we match on already requires `imgt`), so defaulting here
  // saves the first-run user a dropdown click.
  numberingScheme: "imgt",
  heavyChainId: "",
  lightChainId: "",
  frConfThresh: 4.0,
  cdrConfThresh: 6.0,
}));

// Helpers for the per-metric histogram output pairs below. Each pair
// resolves a single `scoresData` PColumn by name; `pfFromScores` wraps
// it in a single-column PFrame for graph-maker binding, `specFromScores`
// returns the `{columnId, spec}` pair the HistogramPage default options
// bind to.
type ScoresPColumn = PColumn<PColumnDataUniversal | undefined>;
type ScoresCtx = BlockRenderCtx<unknown, unknown>;
function findScoresCol(ctx: ScoresCtx, name: string): ScoresPColumn | undefined {
  const cols = ctx.outputs?.resolve("scoresData")?.getPColumns() as ScoresPColumn[] | undefined;
  return cols?.find((c) => c.spec.name === name);
}
function pfFromScores(ctx: ScoresCtx, name: string): PFrameHandle | undefined {
  const col = findScoresCol(ctx, name);
  return col ? ctx.createPFrame([col]) : undefined;
}
function specFromScores(ctx: ScoresCtx, name: string): PColumnIdAndSpec | undefined {
  const col = findScoresCol(ctx, name);
  return col ? { columnId: col.id, spec: col.spec } : undefined;
}

const SC_CLONOTYPE_AXIS = { type: "String", name: "pl7.app/vdj/scClonotypeKey" } as const;

function findOnScClonotype(ctx: ScoresCtx, name: string, valueType: ValueType) {
  return ctx.resultPool.findDataWithCompatibleSpec({
    kind: "PColumn",
    name,
    valueType,
    axesSpec: [SC_CLONOTYPE_AXIS],
  });
}

function resolvePrimaryRef(ctx: {
  args?: { primaryRef?: { column?: PlRef } };
  data?: BlockData;
}): PlRef | undefined {
  return ctx.args?.primaryRef?.column ?? ctx.data?.dataset?.primary?.column;
}

export const platforma = BlockModelV3.create(dataModel)
  .args((data) => {
    // Spec R1 / R46. UI carries `dataset: DatasetSelection`; we unwrap
    // back to the PrimaryRef envelope the workflow already knows how to
    // resolve (`wf.prepare` reads `args.primaryRef.column` for the PDB
    // PColumn, `.filter` for the optional clonotype subset).
    if (!data.dataset?.primary?.column) {
      throw new Error("Pick a predicted structures dataset");
    }
    return {
      primaryRef: data.dataset.primary,
      numberingScheme: data.numberingScheme,
      heavyChainId: data.heavyChainId,
      lightChainId: data.lightChainId,
      frConfThresh: data.frConfThresh,
      cdrConfThresh: data.cdrConfThresh,
    };
  })
  // Spec R1 / R46. `buildDatasetOptions` surfaces anchor-marked PColumns
  // (`pl7.app/isAnchor: "true"`) from the result pool as datasets the UI
  // shows in `PlDatasetSelector`. We accept anchors whose name is
  // `pl7.app/structure/pdb` (the 3D Structure Prediction block emits this
  // since v1.0.11). Filter predicate identifies the Boolean/Int subset
  // columns the user can pick to narrow the clonotype set per R47
  // (predictionSuccessful, confident).
  .output("datasetOptions", (ctx): DatasetOption[] | undefined =>
    buildDatasetOptions(ctx, {
      primary: (spec: PObjectSpec): boolean =>
        isPColumnSpec(spec) &&
        spec.name === "pl7.app/structure/pdb" &&
        spec.annotations?.["pl7.app/isAnchor"] === "true",
      filter: (spec: PObjectSpec): boolean =>
        isPColumnSpec(spec) &&
        (spec.name === "pl7.app/structure/predictionSuccessful" ||
          spec.name === "pl7.app/structure/confident"),
    }),
  )
  // Spec R51 , per-clonotype scalar metrics table. PColumns come from the
  // `scoresData` PFrame (axes: [scClonotypeKey]); enriched with upstream
  // `cdrh3Length` (R5 sanity-check column), upstream `pl7.app/label` for
  // pretty row keys, and `pl7.app/clusterId` etc. when the 3D Structure
  // Clustering block is upstream. Joined on the shared scClonotypeKey
  // axis by the PFrame driver. `tableState` is passed as `undefined` so
  // AG-Grid state writes don't trigger model re-runs (avoids the
  // model→UI→model feedback loop via v-model).
  .outputWithStatus("scoresTable", (ctx) => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    // R5 sanity-check + R42 cluster enrichment + `pl7.app/label` for pretty
    // row keys. PlAgDataTable auto-joins on the shared scClonotypeKey axis;
    // missing matches simply stay as empty cells.
    const upstreamCdrh3 = findOnScClonotype(ctx, "pl7.app/structure/cdrh3Length", "Long");
    const upstreamLabel = findOnScClonotype(ctx, "pl7.app/label", "String");
    const clusterId = findOnScClonotype(ctx, "pl7.app/clusterId", "String");
    const isCentroid = findOnScClonotype(ctx, "pl7.app/structure/clustering/isCentroid", "Int");
    const tmDistance = findOnScClonotype(
      ctx,
      "pl7.app/structure/clustering/tmDistanceToCentroid",
      "Double",
    );
    const tmScore = findOnScClonotype(
      ctx,
      "pl7.app/structure/clustering/tmScoreToCentroid",
      "Double",
    );
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
  // metric, all built from `scoresData` via `findScoresCol` (declared at
  // module scope). `ctx.createPFrame([col])` is used over
  // `createPFrameForGraphs` because the latter pulls every column
  // sharing the scClonotypeKey axis, which would let graph-maker pick
  // an unrelated numeric column over the one bound by `defaultOptions`.
  .outputWithStatus("pshPf", (ctx) => pfFromScores(ctx, "pl7.app/liabilities/psh"))
  .output("pshSpec", (ctx) => specFromScores(ctx, "pl7.app/liabilities/psh"))
  .outputWithStatus("ppcPf", (ctx) => pfFromScores(ctx, "pl7.app/liabilities/ppc"))
  .output("ppcSpec", (ctx) => specFromScores(ctx, "pl7.app/liabilities/ppc"))
  .outputWithStatus("pncPf", (ctx) => pfFromScores(ctx, "pl7.app/liabilities/pnc"))
  .output("pncSpec", (ctx) => specFromScores(ctx, "pl7.app/liabilities/pnc"))
  .outputWithStatus("sfvcspPf", (ctx) => pfFromScores(ctx, "pl7.app/liabilities/sfvcsp"))
  .output("sfvcspSpec", (ctx) => specFromScores(ctx, "pl7.app/liabilities/sfvcsp"))
  .outputWithStatus("cdrh3CompactnessPf", (ctx) =>
    pfFromScores(ctx, "pl7.app/liabilities/cdrh3Compactness"),
  )
  .output("cdrh3CompactnessSpec", (ctx) =>
    specFromScores(ctx, "pl7.app/liabilities/cdrh3Compactness"),
  )
  .outputWithStatus("devScorePf", (ctx) =>
    pfFromScores(ctx, "pl7.app/liabilities/structuralDevelopabilityScore"),
  )
  .output("devScoreSpec", (ctx) =>
    specFromScores(ctx, "pl7.app/liabilities/structuralDevelopabilityScore"),
  )
  // Spec R52 , per-clonotype PDB ResourceMap exposed for the viewer modal.
  // Reads the upstream `pl7.app/structure/pdb` PColumn (axis:
  // scClonotypeKey, valueType File) and parses it into [{key, value}]
  // pairs; UI consumes via `entry.value.handle` (a RemoteBlobHandle) and
  // hands it to PlStructureViewer.
  .output("clonotypePdbsMap", (ctx) => {
    // Resolve through the user-picked PlRef inside the PrimaryRef envelope
    // (spec R1) rather than fuzzy-matching the result pool ,
    // `findDataWithCompatibleSpec` was returning empty here even with
    // name + valueType + axes + domain all aligned.
    const ref = resolvePrimaryRef(ctx);
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
    const ref = resolvePrimaryRef(ctx);
    if (!ref) return undefined;
    const pdbSpec = ctx.resultPool.getPColumnSpecByRef(ref);
    if (!pdbSpec) return undefined;
    // Match the clonotype axis by name in case the upstream PDB column
    // carries multiple axes (e.g. legacy [sampleId, scClonotypeKey] shape).
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
