import type {
  AxisId,
  BlockRenderCtx,
  DatasetOption,
  InferOutputsType,
  PColumn,
  PColumnDataUniversal,
  PColumnIdAndSpec,
  PFrameHandle,
  PObjectSpec,
  ValueType,
} from "@platforma-sdk/model";
import {
  ArrayColumnProvider,
  BlockModelV3,
  buildDatasetOptions,
  createPlDataTableV3,
  DataModelBuilder,
  getAxisId,
  isPColumnSpec,
  parseResourceMap,
} from "@platforma-sdk/model";
import type { BlockArgs, BlockData, DetectedMode } from "./types";

export type { NumberingScheme, DetectedMode, BlockData, BlockArgs } from "./types";

const dataModel = new DataModelBuilder().from<BlockData>("v1").init(() => ({
  dataset: undefined,
  // Upstream 3D Structure Prediction always emits IMGT-numbered PDBs, so
  // default to imgt and save the first-run user a dropdown click.
  numberingScheme: "imgt",
  heavyChainId: "",
  lightChainId: "",
  frConfThresh: 4.0,
  cdrConfThresh: 6.0,
  customBlockLabel: "",
}));

type ScoresCtx = BlockRenderCtx<unknown, unknown>;
type ScoresPColumn = PColumn<PColumnDataUniversal | undefined>;

/** Dataset-level mode emitted by the workflow as a scalar block output.
 *
 * `ctx.outputs` throws "Staging context not available" when called from
 * the middle layer's args-only context (used to render the block-overview
 * sidebar's subtitle), so guard the read. Optional chaining on
 * `ctx.outputs?` doesn't help , the throw happens inside the getter,
 * before the chain can short-circuit. */
function resolveMode(ctx: ScoresCtx): DetectedMode | undefined {
  let m: string | undefined;
  try {
    m = ctx.outputs?.resolve("detectedMode")?.getDataAsJson<string>();
  } catch {
    return undefined;
  }
  return m === "TAP" || m === "TNP" ? m : undefined;
}

/** Block label derived from mode + cutoffs when the user hasn't set one.
 * `data` is optional so this is safe to call from contexts where block
 * storage hasn't been parsed yet (the middle-layer args-only context
 * surfaces `ctx.data` as undefined during early renders; an unguarded
 * deref throws and the platform falls back to the literal string
 * "Invalid subtitle" in the block-overview sidebar). */
export function defaultBlockLabelFor(
  data: Partial<BlockData> | undefined,
  mode?: DetectedMode,
): string {
  const fmt = (v?: number) => (v === undefined ? "?" : Number.isInteger(v) ? `${v}` : v.toFixed(1));
  const fr = fmt(data?.frConfThresh);
  const cdr = fmt(data?.cdrConfThresh);
  const tail = `rSASA ≤ 0.075, gating FR ≥ ${fr} Å / CDR ≥ ${cdr} Å`;
  return mode ? `${mode}, ${tail}` : tail;
}

// Helpers for the per-metric histogram output pairs. Each resolves a single
// `scoresData` PColumn by name; `pfFromScores` wraps it in a single-column
// PFrame for graph-maker, `specFromScores` returns the {columnId, spec} pair
// the histogram pages bind to.
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
  }) as ScoresPColumn[];
}

export const platforma = BlockModelV3.create(dataModel)
  .args<BlockArgs>((data) => {
    if (!data.dataset?.primary?.column) {
      throw new Error("Pick a 3D structures dataset");
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
  // Surface anchor-marked `pl7.app/structure/pdb` PColumns as selectable
  // datasets; the filter predicate exposes the Boolean/Int columns the user
  // can pick to narrow the clonotype set.
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
  // Dataset-level mode, consumed by the mode-specific histogram page and the
  // default block label.
  .output("detectedMode", (ctx): DetectedMode | undefined => resolveMode(ctx))
  // Per-clonotype scalar metrics table. Score columns are primary; upstream
  // label / cdrh3Length / cluster columns join on the shared scClonotypeKey
  // axis. Mode-specific flag columns default-visible only in their mode.
  .outputWithStatus("scoresTable", (ctx) => {
    const scoreCols = ctx.outputs?.resolve("scoresData")?.getPColumns() as
      | ScoresPColumn[]
      | undefined;
    if (scoreCols === undefined) return undefined;

    const enrich = [
      findOnScClonotype(ctx, "pl7.app/structure/cdrh3Length", "Long"),
      findOnScClonotype(ctx, "pl7.app/label", "String"),
      findOnScClonotype(ctx, "pl7.app/clusterId", "String"),
      findOnScClonotype(ctx, "pl7.app/structure/clustering/isCentroid", "Int"),
      findOnScClonotype(ctx, "pl7.app/structure/clustering/tmDistanceToCentroid", "Double"),
      findOnScClonotype(ctx, "pl7.app/structure/clustering/tmScoreToCentroid", "Double"),
    ].flat();

    const variants = [
      ...new ArrayColumnProvider(scoreCols).getAllColumns().map((column) => ({
        column,
        isPrimary: true,
      })),
      ...new ArrayColumnProvider(enrich).getAllColumns().map((column) => ({ column })),
    ];

    const mode = resolveMode(ctx);
    return createPlDataTableV3(ctx, {
      columns: variants,
      displayOptions: mode
        ? {
            visibility: [
              {
                match: (s) => s.name === "pl7.app/liabilities/sfvcspFlag",
                visibility: mode === "TAP" ? "default" : "optional",
              },
              {
                match: (s) => s.name === "pl7.app/liabilities/cdrh3CompactnessFlag",
                visibility: mode === "TNP" ? "default" : "optional",
              },
            ],
          }
        : undefined,
    });
  })
  // Per-metric histograms. Each pair is a single-column PFrame + its spec.
  // `ctx.createPFrame([col])` over `createPFrameForGraphs` so graph-maker
  // binds the bound column rather than an unrelated sibling.
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
  // Per-clonotype PDB ResourceMap from the workflow's `pdbsMap` output;
  // parsed into [{key, value}] pairs the viewer modal consumes via
  // `entry.value.handle`.
  .output("clonotypePdbsMap", (ctx) => {
    const pCols = ctx.outputs?.resolve("pdbsMap")?.getPColumns();
    if (pCols === undefined || pCols.length === 0) return undefined;
    const parsed = parseResourceMap(pCols[0].data, (acc) => acc.getRemoteFileHandle(), false);
    if (!parsed.isComplete) return undefined;
    return parsed.data;
  })
  // Axis id of the scClonotypeKey axis, used to attach the viewer-trigger
  // button to that column in the table. Derive from the actual scoresData
  // column (which is what populates the table), so the AxisId matches the
  // table column's id byte-for-byte. Deriving from the PDB col's spec
  // produced false negatives when its axis carried a domain that the
  // table column did not.
  .output("clonotypeAxisId", (ctx): AxisId | undefined => {
    let cols: ScoresPColumn[] | undefined;
    try {
      cols = ctx.outputs?.resolve("scoresData")?.getPColumns() as ScoresPColumn[] | undefined;
    } catch {
      return undefined;
    }
    const first = cols?.[0];
    const found = first?.spec.axesSpec.find((a) => a.name === "pl7.app/vdj/scClonotypeKey");
    if (!found) return undefined;
    return getAxisId(found);
  })
  .sections((ctx) => {
    const mode = resolveMode(ctx);
    const modeSpecificLabel =
      mode === "TNP"
        ? "CDRH3 compactness"
        : mode === "TAP"
          ? "Fv charge symmetry"
          : "CDRH3 compactness / Fv charge symmetry";
    return [
      { type: "link", href: "/", label: "Main" },
      { type: "link", href: "/histogram-psh", label: "Hydrophobicity" },
      { type: "link", href: "/histogram-ppc", label: "Positive charge patches" },
      { type: "link", href: "/histogram-pnc", label: "Negative charge patches" },
      { type: "link", href: "/histogram-mode-specific", label: modeSpecificLabel },
      { type: "link", href: "/histogram-developability", label: "Developability cost" },
    ];
  })
  .title(() => "3D Structure-Based Liabilities")
  .subtitle(
    // Optional-chain `ctx.data`: the args-only context the middle layer
    // uses for sidebar rendering can surface `data` as undefined before
    // block storage is parsed. An unguarded deref throws and the
    // platform substitutes "Invalid subtitle" as the visible string.
    (ctx) => ctx.data?.customBlockLabel || defaultBlockLabelFor(ctx.data, resolveMode(ctx)),
  )
  .done();

export type BlockOutputs = InferOutputsType<typeof platforma>;
