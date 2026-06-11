import type { DatasetSelection, PlDataTableStateV2 } from "@platforma-sdk/model";

/** Numbering schemes the runtime can interpret. The block is now hardcoded
 *  to IMGT at the workflow layer because every supported upstream emits
 *  IMGT-numbered structures; the type stays exported for downstream blocks
 *  that read the spec annotations. */
export type NumberingScheme = "imgt" | "chothia" | "kabat";

/** Dataset-level mode: paired Fv (TAP) or single-chain VHH (TNP). */
export type DetectedMode = "TAP" | "TNP";

/** Unified user-editable state persisted by the model. */
export type BlockData = {
  /** Predicted-structures dataset picked via `PlDatasetSelector`. */
  dataset?: DatasetSelection;
  /** Confidence-gating thresholds (Å) for framework and CDR regions. */
  frConfThresh: number;
  cdrConfThresh: number;
  /** User-set block label; empty falls back to the derived default. */
  customBlockLabel: string;
  /** Results-table sort / filter / column state. Persisted in the model and
   *  fed into `createPlDataTableV3` so sorting re-derives rows server-side
   *  instead of leaving AG-Grid with unsortable placeholder cells. */
  tableState: PlDataTableStateV2;
};

/** Pre-v2 shape: carried manual `heavyChainId`/`lightChainId` (now
 *  auto-detected, removed) and no persisted `tableState`. Kept so the v1 -> v2
 *  migration can map existing block instances onto the current shape. */
export type BlockDataV1 = {
  dataset?: DatasetSelection;
  heavyChainId: string;
  lightChainId: string;
  frConfThresh: number;
  cdrConfThresh: number;
  customBlockLabel: string;
};

/** Projection consumed by the workflow. */
export type BlockArgs = {
  primaryRef: NonNullable<DatasetSelection["primary"]>;
  frConfThresh: number;
  cdrConfThresh: number;
};
