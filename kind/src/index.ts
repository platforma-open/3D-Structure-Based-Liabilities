import { assertParamsObject, defineBlockKind } from "@platforma-sdk/block-kind";
import { name, version } from "../package.json" with { type: "json" };

/**
 * This block's init-params contract — what a project template supplies to seed a
 * new instance.
 *
 * The two confidence gates are the only settings that change what the block
 * computes: they decide which residues are trusted enough to score, so they are
 * real configuration. Everything else in `BlockData` is deliberately absent.
 * `dataset` is a `DatasetSelection`, an anchor-bound reference whose meaning
 * depends on the anchor map of the project that made it, so it cannot travel in
 * a template. `tableState` is view state, and `customBlockLabel` is a label the
 * user types over a derived default — neither is configuration.
 *
 * Both fields are optional so a template can seed either one alone; the model's
 * `init` keeps a default behind each.
 */
export type BlockParams = {
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
 * Each field is checked only when present, because both are optional. Keys the
 * contract does not name are dropped by not being read; refusing them would mean
 * holding a list of field names as strings that nothing keeps in step with the
 * type.
 */
function parseInitializationParams(value: unknown): BlockParams {
  assertParamsObject(value);

  const params: BlockParams = {};

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
