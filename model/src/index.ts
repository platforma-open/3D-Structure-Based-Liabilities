import type { ImportFileHandle, InferOutputsType, PlDataTableStateV2 } from "@platforma-sdk/model";
import {
  BlockModelV3,
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

/** Current shape (v3) — adds numbering scheme + heavy/light chain mapping so
 * motif scoring can apply R19 region weights and cysteines can be classified
 * against canonical positions (R21). All three are optional ("" / undefined
 * means "unknown" and motif scoring falls back to neutral weights). */
export type BlockData = BlockDataV2 & {
  numberingScheme: NumberingScheme | "";
  heavyChainId: string;
  lightChainId: string;
};

const dataModel = new DataModelBuilder()
  .from<BlockDataV1>("v1")
  .migrate<BlockDataV2>("v2", (v1) => ({
    ...v1,
    cysTableState: createPlDataTableStateV2(),
  }))
  .migrate<BlockData>("v3", (v2) => ({
    ...v2,
    numberingScheme: "",
    heavyChainId: "",
    lightChainId: "",
  }))
  .init(() => ({
    pdb: undefined,
    tableState: createPlDataTableStateV2(),
    cysTableState: createPlDataTableStateV2(),
    numberingScheme: "",
    heavyChainId: "",
    lightChainId: "",
  }));

export const platforma = BlockModelV3.create(dataModel)
  .args((data) => {
    if (!data.pdb) throw new Error("PDB file is required");
    return {
      pdb: data.pdb,
      numberingScheme: data.numberingScheme,
      heavyChainId: data.heavyChainId,
      lightChainId: data.lightChainId,
    };
  })
  .output("liabilitiesJson", (ctx) =>
    ctx.outputs?.resolve("liabilitiesJson")?.getFileContentAsString(),
  )
  .outputWithStatus("motifsTable", (ctx) => {
    const pCols = ctx.outputs?.resolve("motifsData")?.getPColumns();
    if (pCols === undefined) return undefined;
    return createPlDataTableV2(ctx, pCols, ctx.data.tableState);
  })
  .outputWithStatus("cysTable", (ctx) => {
    const pCols = ctx.outputs?.resolve("cysData")?.getPColumns();
    if (pCols === undefined) return undefined;
    return createPlDataTableV2(ctx, pCols, ctx.data.cysTableState);
  })
  .sections(() => [{ type: "link", href: "/", label: "Main" }])
  .title(() => "3D Structure-Based Liabilities")
  .done();

export type BlockOutputs = InferOutputsType<typeof platforma>;
