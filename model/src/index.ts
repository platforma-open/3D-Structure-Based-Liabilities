import type { GraphMakerState } from "@milaboratories/graph-maker";
import type {
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

/** Spec R37 — per-clonotype JSON report. The cysteines array is consumed via
 * the `cysTable` PColumn output, not from this JSON. `chains` is a transient
 * extra used by the UI residue map until per-residue PColumn outputs land. */
export type LiabilitiesReport = {
  numberingScheme: "imgt" | "chothia" | "kabat" | null;
  /** Spec R7 — auto-detected from chain count. "complex" for 3+ chains
   * (the spec rejects but we keep going for dev fixtures like 1N8Z). */
  mode?: "TAP" | "TNP" | "complex" | "empty";
  motifs: MotifHit[];
  chains: ChainSummary[];
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

/** Current shape (v7) — adds GraphMaker state for the five Spec R54
 * distribution histograms: PSH, PPC, PNC, the mode-specific metric
 * (SFvCSP for Fv / CDRH3 compactness for VHH), and the composite
 * developability score. Each histogram has its own state field so its
 * GraphMaker configuration (bin count, axis scale, layer colors, etc.)
 * persists independently. */
export type BlockData = BlockDataV6 & {
  graphStatePshV2: GraphMakerState;
  graphStatePpcV2: GraphMakerState;
  graphStatePncV2: GraphMakerState;
  graphStateSfvcspV2: GraphMakerState;
  graphStateCdrh3CompactnessV2: GraphMakerState;
  graphStateDevScoreV2: GraphMakerState;
};

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
  .migrate<BlockData>("v7", (v6) => ({
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
  .init(() => ({
    pdb: undefined,
    pdbRef: undefined,
    tableState: createPlDataTableStateV2(),
    cysTableState: createPlDataTableStateV2(),
    scoresTableState: createPlDataTableStateV2(),
    numberingScheme: "",
    heavyChainId: "",
    lightChainId: "",
    rsasaBuriedCutoff: 0.075,
    frConfThresh: 4.0,
    cdrConfThresh: 6.0,
    graphStatePshV2: initialGraphState("PSH distribution", "#7da3d1"),
    graphStatePpcV2: initialGraphState("PPC distribution", "#e5a06f"),
    graphStatePncV2: initialGraphState("PNC distribution", "#82c79c"),
    graphStateSfvcspV2: initialGraphState("SFvCSP distribution (Fv)", "#bb86d6"),
    graphStateCdrh3CompactnessV2: initialGraphState(
      "CDRH3 compactness distribution (VHH)",
      "#d6b06b",
    ),
    graphStateDevScoreV2: initialGraphState("Developability score distribution", "#cf6e83"),
  }));

export const platforma = BlockModelV3.create(dataModel)
  .args((data) => {
    // Spec R1-R6 — when a predicted-structures dataset is selected, pdbRef
    // takes priority and the workflow's wf.prepare hook resolves the upstream
    // `pl7.app/structure/pdb` PColumn, then iterates per clonotype via
    // `pframes.processColumn`. The legacy single-PDB upload (data.pdb) is
    // kept for local dev fixtures (e.g. 1N8Z) and used when no ref is set.
    if (!data.pdbRef && !data.pdb) {
      throw new Error("Pick a predicted structures dataset (preferred) or upload a PDB file");
    }
    return {
      pdb: data.pdb,
      pdbRef: data.pdbRef,
      numberingScheme: data.numberingScheme,
      heavyChainId: data.heavyChainId,
      lightChainId: data.lightChainId,
      rsasaBuriedCutoff: data.rsasaBuriedCutoff,
      frConfThresh: data.frConfThresh,
      cdrConfThresh: data.cdrConfThresh,
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
  // `liabilitiesJson` and `pdbImportHandle` are only emitted on the legacy
  // single-PDB upload path. On the PrimaryRef path the workflow exposes a
  // per-clonotype File ResourceMap instead, and these field lookups would
  // raise "field not found". try/catch keeps the model surface clean and
  // lets the UI fall back to the table-only view.
  .output("liabilitiesJson", (ctx) => {
    try {
      return ctx.outputs?.resolve("liabilitiesJson")?.getFileContentAsString();
    } catch {
      return undefined;
    }
  })
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
  .outputWithStatus("scoresTable", (ctx) => {
    const pCols = ctx.outputs?.resolve("scoresData")?.getPColumns();
    if (pCols === undefined) return undefined;
    return createPlDataTableV2(ctx, pCols, undefined);
  })
  .output(
    "pdbImportProgress",
    (ctx) => {
      try {
        return ctx.outputs?.resolve("pdbImportHandle")?.getImportProgress();
      } catch {
        return undefined;
      }
    },
    { isActive: true },
  )
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
    const chainPart = chains.length ? chains.join("/") : "chains unset";
    return `${scheme}, ${chainPart}, rSASA<${a.rsasaBuriedCutoff}, conf-gated FR>${a.frConfThresh} Å / CDR>${a.cdrConfThresh} Å`;
  })
  .done();

export type BlockOutputs = InferOutputsType<typeof platforma>;
