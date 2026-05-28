# vendor/

Pinned pre-built tarballs for one in-flight visualizations PR the block depends on. Resolved via `pnpm.overrides` in the root `package.json` so `pnpm install` picks them up transparently.

## Why These Are Here

The block's distribution histograms consume APIs that have not yet landed in published versions of `@milaboratories/graph-maker` / `@milaboratories/miplots4`:

- **graph-maker + miplots4** ([milaboratory/visualizations#87](https://github.com/milaboratory/visualizations/pull/87)) , histogram threshold lines (`pl7.app/graph/thresholds` annotation, hard-narrow bounds with off-range expansion, numeric labels via `numberFormat`, `significantLinesStyle` object form).

Tarballs were produced with `pnpm pack` from the visualizations PR branch and copied here so reviewers can `git checkout chore/update-sdk-deps && pnpm install` and reproduce the exact build the block is being reviewed against, without needing a clone of the visualizations repo.

## When To Drop This Folder

Once #87 merges and a tagged release of `@milaboratories/graph-maker` + `@milaboratories/miplots4` ships, bump the catalog versions in `pnpm-workspace.yaml`, delete this folder, and drop the remaining `pnpm.overrides` entries from the root `package.json`.

## Refreshing

If the PR moves while review is in flight, rebuild and replace the tarballs locally:

```
cd <visualizations checkout on feat/histogram-thresholds>
pnpm --filter @milaboratories/graph-maker build && (cd packages/graph-maker && pnpm pack --pack-destination .)
cp packages/graph-maker/milaboratories-graph-maker-*.tgz <block>/vendor/graph-maker.tgz
# repeat for miplots4
```

Then run `pnpm install --force` in the block to refresh the lockfile.
