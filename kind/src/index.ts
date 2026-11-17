import { assertParamsObject, defineBlockKind } from "@platforma-sdk/block-kind";
import type { DatasetSelection } from "@platforma-sdk/model";
import { isDatasetSelection } from "@platforma-sdk/model";
import { name, version } from "../package.json" with { type: "json" };

/**
 * This block's init-params contract — what a project template supplies to seed a
 * new instance.
 *
 * The dataset the block scores, and the two confidence gates: they decide which
 * residues are trusted enough to score, so they are real configuration.
 *
 * `dataset` is the selection the dataset picker made: a reference to the
 * predicted structures of an upstream block. A project template names its
 * blocks, and a block created from one receives the reference pointing at the
 * block made from the same entry, so a project made from a template scores the
 * structures the original one did. A template may leave it out and have the
 * dataset picked afterwards.
 *
 * `tableState` is view state, and `customBlockLabel` is a label the user types
 * over a derived default — neither is configuration, and both are absent.
 *
 * Every field is optional so a template can seed any of them alone; the model's
 * `init` keeps a default behind each gate.
 */
export type BlockParams = {
  /** The predicted structures to score, as the dataset picker emits them. */
  dataset?: DatasetSelection;
  /** Framework-region confidence gate, in ångström. */
  frConfThresh?: number;
  /** CDR confidence gate, in ångström. */
  cdrConfThresh?: number;
};

/**
 * Reject a value that is not a finite number.
 *
 * Both gates are plain numbers, so there is no SDK guard to reach for. The check
 * stops at "finite number" on purpose. The UI offers a bounded range, but
 * encoding that range here would make the kind refuse a file this block itself
 * exported the day the range changes. A range is meaning; the kind checks the
 * envelope.
 */
function finiteNumber(key: string, value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`'${key}' must be a finite number. Got: ${JSON.stringify(value)}`);
  }
  return value;
}

/**
 * The same contract at runtime, for params arriving from a template file rather
 * than from typed code — the only point that can catch a hand-written entry
 * being wrong.
 *
 * Each field is checked only when present, because all are optional. Keys the
 * contract does not name are dropped by not being read; refusing them would mean
 * holding a list of field names as strings that nothing keeps in step with the
 * type.
 */
function parseInitializationParams(value: unknown): BlockParams {
  assertParamsObject(value);

  const params: BlockParams = {};

  if (value.dataset !== undefined) {
    if (!isDatasetSelection(value.dataset)) {
      throw new Error("'dataset' must be a dataset selection, as the dataset picker emits it.");
    }
    params.dataset = value.dataset;
  }

  if (value.frConfThresh !== undefined) {
    params.frConfThresh = finiteNumber("frConfThresh", value.frConfThresh);
  }

  if (value.cdrConfThresh !== undefined) {
    params.cdrConfThresh = finiteNumber("cdrConfThresh", value.cdrConfThresh);
  }

  return params;
}

// Identity (`name`/`version`) comes from this package's own `package.json`, so
// the on-wire `{name}@{version}` reference can never drift from what npm
// publishes; the bundler inlines the JSON import.
export const kind = defineBlockKind<BlockParams>({
  name,
  version,
  parseInitializationParams,
});
