import type { GraphMakerState } from "@milaboratories/graph-maker";
import type {
  AxisId,
  ImportFileHandle,
  InferOutputsType,
  PColumnIdAndSpec,
  PFrameHandle,
  PlDataTableStateV2,
  PlRef,
} from "@platforma-sdk/model";
import {
  BlockModelV3,
  createPFrameForGraphs,
  createPlDataTableStateV2,
  createPlDataTableV2,
  DataModelBuilder,
  parseResourceMap,
} from "@platforma-sdk/model";

export type SequenceRiskClass = "High" | "Medium" | "Low";
export type Fixability =
  | "easily_fixable"
  | "fixable"
  | "hard_to_fix"
  | "structural"
  | "disqualifying";

/** Spec R37 — entry in the unified motifs[] array. */
export type MotifHit = {
  type: string;
  chainId: string;
  resSeq: number;
  iCode: string;
  resName: string;
  region: string | null;
  rsasa: number;
  exposed: boolean;
  exposureFactor: number;
  /** Spec R34 — residue's mean B-factor (Å). Null when no atoms carry it. */
  confidence: number | null;
  /** Spec R35 — "yes"/"no". Gated motifs are kept for traceability but
   * excluded from `motifStructuralRiskScore`. */
  confidenceGated: "yes" | "no";
  weightedScore: number;
  sequenceRiskClass: SequenceRiskClass;
  fixability: Fixability;
};

export type ChainSummary = {
  id: string;
  residues: {
    resSeq: number;
    iCode: string;
    resName: string;
    rsasa?: number | null;
  }[];
};

/** Spec R23 — per-cysteine entry in the report's `cysteines[]` array. */
export type CysteineHit = {
  chainId: string;
  resSeq: number;
  iCode: string;
  cysClass: string;
  chainRole: string | null;
  bondingState: string;
  rsasa: number | null;
  sidechainRsasa: number | null;
  sasa: number | null;
  sidechainSasa: number | null;
  partnerChainId: string | null;
  partnerResSeq: number | null;
  partnerIcode: string | null;
};

/** Spec R37 — per-clonotype JSON report. The cysteines array is consumed via
 * the `cysTable` PColumn output, not from this JSON. `chains` is a transient
 * extra used by the UI residue map until per-residue PColumn outputs land. */
export type LiabilitiesReport = {
  numberingScheme: "imgt" | "chothia" | "kabat" | null;
  /** Spec R7 — auto-detected from chain count. "complex" for 3+ chains
   * (the spec rejects but we keep going for dev fixtures like 1N8Z). */
  mode?: "TAP" | "TNP" | "complex" | "empty";
  motifs: MotifHit[];
  /** Spec R23 — per-cysteine entries with structural state classification. */
  cysteines?: CysteineHit[];
  chains: ChainSummary[];
  /** Spec R39 per-metric flags. Three-band: "green" | "amber" | "red"
   * or "-" when the metric isn't applicable to the current mode. */
  thresholdFlags?: Record<string, string>;
  scores?: {
    /** R20 sum of non-gated motif weighted scores. */
    motifStructuralRiskScore: number;
    confidenceGatedMotifCount: number;
    surfacedMotifCount: number;
    /** R41 composite developability score (motif + flag bumps + cys contribs). */
    structuralDevelopabilityScore: number;
    /** R41a fixable-items category: None | Low | Medium | High. */
    structuralDevelopabilityRisk: "None" | "Low" | "Medium" | "High";
    /** R41a hard-to-fix items: Present | None. */
    structuralIntegrityRisk: "Present" | "None";
  };
  /** Spec R24–R33 surface developability metrics. Empty when no scheme +
   * chain mapping is set. Mode dispatches the field set: Fv has
   * `sfvcsp`; VHH has `cdrh3Compactness`. R36 adds a per-metric
   * `<metric>LowConfidenceResidueFraction` Double (null when the input
   * carries no B-factors). */
  surfaceMetrics?:
    | Record<string, never>
    | {
        mode: "TAP" | "TNP";
        totalCdrLength: number;
        psh: number;
        pshPatchCount: number;
        ppc: number;
        pnc: number;
        sfvcsp?: number;
        cdrh3Compactness?: number | null;
        totalCdrLengthLowConfidenceResidueFraction?: number | null;
        pshLowConfidenceResidueFraction?: number | null;
        ppcLowConfidenceResidueFraction?: number | null;
        pncLowConfidenceResidueFraction?: number | null;
        sfvcspLowConfidenceResidueFraction?: number | null;
        cdrh3CompactnessLowConfidenceResidueFraction?: number | null;
      };
};

/** Spec R14 / R10 — numbering schemes supported for region tagging. */
export type NumberingScheme = "imgt" | "chothia" | "kabat";

/** Spec R48 — hydrophobicity scale used by PSH. KD = Kyte-Doolittle (the
 * Raybould 2019 default), WW = Wimley-White interface, Hessa = Hessa
 * biological hydrophobicity, EM = Eisenberg-McLachlan consensus, BM =
 * Black-Mould normalized scale. */
export type HydrophobicityScale = "kd" | "ww" | "hessa" | "em" | "bm";

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

/** v4 — adds R49 advanced thresholds (FR/CDR confidence gating + R12
 * buried/exposed rSASA cutoff). Defaults match the spec's calibrated
 * values for ImmuneBuilder. */
type BlockDataV4 = BlockDataV3 & {
  rsasaBuriedCutoff: number;
  frConfThresh: number;
  cdrConfThresh: number;
};

/** v5 — adds `pdbRef`, a `PlRef` pointing at an upstream
 * `pl7.app/structure/pdb` PColumn (Spec R1–R6). When set, the workflow
 * resolves it into per-clonotype PDBs and runs the software once per
 * clonotype; output PColumns then key on `pl7.app/vdj/scClonotypeKey`
 * rather than the `structureId="static"` placeholder.
 *
 * `pdb` (the legacy `ImportFileHandle` upload) stays for the local
 * single-PDB dev path (e.g. 1N8Z). When both are set, `pdbRef` wins. */
type BlockDataV5 = BlockDataV4 & {
  pdbRef?: PlRef;
};

/** v6 — adds `scoresTableState` for the per-clonotype scalar metrics
 * table (Spec R51). Surfaces the existing `scoresData` PFrame the
 * workflow already emits. */
type BlockDataV6 = BlockDataV5 & {
  scoresTableState: PlDataTableStateV2;
};

/** v7 — adds GraphMaker state for the six Spec R54 distribution histograms:
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

/** v8 — adds R48 hydrophobicity scale selector. */
type BlockDataV8 = BlockDataV7 & {
  hydrophobicityScale: HydrophobicityScale;
};

/** Current shape (v9) — strips the legacy single-PDB path's `pdb`
 * field, the three persisted-but-unused PlAgDataTable v-model states
 * (`tableState` / `cysTableState` / `scoresTableState`), and the six
 * GraphMakerState fields left over from the GraphMaker→SVG histogram
 * migration. Tables now use UI-local state refs and the histograms are
 * hand-rolled SVG so none of these blobs need to round-trip through
 * persistence. */
export type BlockData = Omit<
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
  .migrate<BlockData>("v9", (v8) => {
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
  .init(() => ({
    pdbRef: undefined,
    numberingScheme: "",
    heavyChainId: "",
    lightChainId: "",
    rsasaBuriedCutoff: 0.075,
    frConfThresh: 4.0,
    cdrConfThresh: 6.0,
    hydrophobicityScale: "kd",
  }));

export const platforma = BlockModelV3.create(dataModel)
  .args((data) => {
    // Spec R1-R6 — the user picks a predicted-structures dataset from the
    // dropdown; the workflow's wf.prepare resolves it into per-clonotype
    // PDBs and iterates via `pframes.processColumn`.
    if (!data.pdbRef) {
      throw new Error("Pick a predicted structures dataset");
    }
    return {
      pdbRef: data.pdbRef,
      numberingScheme: data.numberingScheme,
      heavyChainId: data.heavyChainId,
      lightChainId: data.lightChainId,
      rsasaBuriedCutoff: data.rsasaBuriedCutoff,
      frConfThresh: data.frConfThresh,
      cdrConfThresh: data.cdrConfThresh,
      hydrophobicityScale: data.hydrophobicityScale,
    };
  })
  // Spec R1-R6 — surface `pl7.app/structure/pdb` PColumns from the result
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
  // grid state writes via the UI's v-model don't trigger model re-runs —
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
  // Spec R51 — per-clonotype scalar metrics table. PColumns come from the
  // PrimaryRef-path `scoresData` PFrame (axes: [scClonotypeKey]). Hidden
  // on the legacy single-PDB path (`scoresData` not emitted; resolve
  // returns undefined).
  //
  // Isolation test: pass `undefined` for tableState (instead of
  // ctx.data.scoresTableState) so AG-Grid state writes don't trigger model
  // re-runs. If this lets the table render rows, the bug is the
  // model→UI→model feedback loop via v-model on table state.
  //
  // Spec R5 — upstream `pl7.app/structure/cdrh3Length` is enriched in as
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
    // Spec R42 — surface the cluster axis when the 3D Structure Clustering
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
    const allCols = [
      ...pCols,
      ...(upstreamCdrh3 as typeof pCols),
      ...(upstreamLabel as typeof pCols),
      ...(clusterId as typeof pCols),
      ...(isCentroid as typeof pCols),
      ...(tmDistance as typeof pCols),
      ...(tmScore as typeof pCols),
    ];
    return createPlDataTableV2(ctx, allCols, undefined);
  })
  // Spec R54 — per-metric histograms. One PFrame + Spec output pair per
  // metric. Splitting avoids GraphMaker pre-filling extra slots
  // (color/facet) with sibling columns when given a multi-column source.
  // The helper below resolves a single scoresData column by its
  // `pl7.app/liabilities/*` name and wraps it for GraphMaker.
  .outputWithStatus("pshPf", (ctx): PFrameHandle | undefined => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const col = pCols.find((c) => c.spec.name === "pl7.app/liabilities/psh");
    if (!col) return undefined;
    return createPFrameForGraphs(ctx, [col]);
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
    return createPFrameForGraphs(ctx, [col]);
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
    return createPFrameForGraphs(ctx, [col]);
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
    return createPFrameForGraphs(ctx, [col]);
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
    return createPFrameForGraphs(ctx, [col]);
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
    return createPFrameForGraphs(ctx, [col]);
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
    const labelCols = ctx.resultPool.findDataWithCompatibleSpec({
      kind: "PColumn",
      name: "pl7.app/label",
      valueType: "String",
      axesSpec: [{ type: "String", name: "pl7.app/vdj/scClonotypeKey" }],
    });
    if (!labelCols || labelCols.length === 0) return undefined;
    // `findDataWithCompatibleSpec` returns the deprecated PObject shape;
    // `createPFrameForGraphs` is duck-typed to read `.spec` / `.data` so
    // the cast is safe at runtime.
    return createPFrameForGraphs(ctx, labelCols as never);
  })
  // Spec R52 — per-clonotype PDB ResourceMap exposed for the viewer modal.
  // Reads the upstream `pl7.app/structure/pdb` PColumn (axis:
  // scClonotypeKey, valueType File) and parses it into [{key, value}]
  // pairs; UI consumes via `entry.value.handle` (a RemoteBlobHandle) and
  // hands it to PlStructureViewer.
  .output("clonotypePdbsMap", (ctx) => {
    // Resolve through the user-picked PlRef rather than fuzzy-matching the
    // result pool. `findDataWithCompatibleSpec` was returning empty here
    // even with name + valueType + axes + domain all aligned, so we use
    // the canonical ref-based path — same as how the workflow accesses it.
    const ref = ctx.args?.pdbRef ?? ctx.data?.pdbRef;
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
  // Spec R53 — per-clonotype JSON report ResourceMap. Parsed from this
  // block's own `liabilitiesJsonsData` PFrame so the UI can fetch the
  // specific clonotype's report and render the detail panel alongside
  // the viewer modal. Keyed by scClonotypeKey, values carry a
  // RemoteBlobHandle pointing at the JSON file.
  .output("clonotypeJsonsMap", (ctx) => {
    const pCols = ctx.outputs?.resolve("liabilitiesJsonsData")?.getPColumns();
    if (pCols === undefined) return undefined;
    const jsonCol = pCols.find((c) => c.spec.name === "pl7.app/liabilities/perClonotypeReport");
    if (jsonCol === undefined) return undefined;
    const parsed = parseResourceMap(
      (jsonCol as unknown as { data: unknown }).data as never,
      (acc) => acc.getRemoteFileHandle(),
      false,
    );
    if (!parsed.isComplete) return undefined;
    return parsed.data;
  })
  // Spec R52 — axis identifier for the scClonotypeKey axis on the scoresTable.
  // UI uses this to attach PlAgDataTable's `show-cell-button-for-axis-id`
  // so the viewer-trigger button renders on the clonotype-key column.
  .output("clonotypeAxisId", (ctx): AxisId | undefined => {
    // Resolve through the user-picked PlRef, then read its spec.
    const ref = ctx.args?.pdbRef ?? ctx.data?.pdbRef;
    if (!ref) return undefined;
    const pdbSpec = ctx.resultPool.getPColumnSpecByRef(ref);
    if (!pdbSpec) return undefined;
    const spec = pdbSpec as unknown as { axesSpec: AxisId[] };
    // The upstream PDB column carries [sampleId, scClonotypeKey] — match
    // the clonotype axis by name rather than index, since `[0]` is
    // sampleId here and the cell button must hang off the clonotype axis.
    const found = spec.axesSpec.find(
      (a) => (a as unknown as { name: string }).name === "pl7.app/vdj/scClonotypeKey",
    );
    return found;
  })
  .sections(() => [
    { type: "link", href: "/", label: "Main" },
    { type: "link", href: "/motifs", label: "Motifs" },
    { type: "link", href: "/cysteines", label: "Cysteine state" },
    { type: "link", href: "/histogram-psh", label: "PSH distribution" },
    { type: "link", href: "/histogram-ppc", label: "PPC distribution" },
    { type: "link", href: "/histogram-pnc", label: "PNC distribution" },
    { type: "link", href: "/histogram-sfvcsp", label: "SFvCSP distribution (Fv)" },
    { type: "link", href: "/histogram-cdrh3-compactness", label: "CDRH3 compactness (VHH)" },
    { type: "link", href: "/histogram-developability", label: "Developability score" },
  ])
  .title(() => "3D Structure-Based Liabilities")
  // Spec R55 — active-parameter summary visible at the block header.
  .subtitle((ctx) => {
    if (!ctx.args) return "";
    const a = ctx.args;
    const scheme = a.numberingScheme || "scheme unset";
    const chains: string[] = [];
    if (a.heavyChainId) chains.push(`H=${a.heavyChainId}`);
    if (a.lightChainId) chains.push(`L=${a.lightChainId}`);
    const chainPart = chains.length ? chains.join("/") : "chains auto-detect";
    const scaleSuffix =
      a.hydrophobicityScale && a.hydrophobicityScale !== "kd"
        ? `, hScale=${a.hydrophobicityScale}`
        : "";
    return `${scheme}, ${chainPart}, rSASA<${a.rsasaBuriedCutoff}, conf-gated FR>${a.frConfThresh} Å / CDR>${a.cdrConfThresh} Å${scaleSuffix}`;
  })
  .done();

export type BlockOutputs = InferOutputsType<typeof platforma>;
