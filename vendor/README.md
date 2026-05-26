# vendor/

Pinned pre-built tarballs for two in-flight visualizations PRs the block depends on. Resolved via `pnpm.overrides` in the root `package.json` so `pnpm install` picks them up transparently.

## Why these are here

The block's MainPage consumes APIs that have not yet landed in published versions of `@milaboratories/graph-maker`, `@milaboratories/miplots4`, or `@milaboratories/structure-viewer`:

- **graph-maker + miplots4** ([milaboratory/visualizations#87](https://github.com/milaboratory/visualizations/pull/87)) - histogram threshold lines (`pl7.app/graph/thresholds` annotation, hard-narrow bounds with off-range expansion, numeric labels via `numberFormat`, `significantLinesStyle` object form).
- **structure-viewer** ([milaboratory/visualizations#89](https://github.com/milaboratory/visualizations/pull/89), closes [#88](https://github.com/milaboratory/visualizations/issues/88)) - `initialColorScheme` prop so the slideover opens colored by uncertainty (= spec R52 `by-confidence`).

Tarballs were produced with `pnpm pack` from those branches and copied here so reviewers can `git checkout chore/update-sdk-deps && pnpm install` and reproduce the exact build the block is being reviewed against, without needing a clone of the visualizations repo.

## When to drop this folder

Once #87 and #89 merge and a tagged release of `@milaboratories/graph-maker` / `@milaboratories/miplots4` / `@milaboratories/structure-viewer` ships with those changes, bump the catalog versions in `pnpm-workspace.yaml`, delete this folder, and drop the `pnpm.overrides` block from the root `package.json`.

## Refreshing

If either PR moves while review is in flight, rebuild and replace the tarball locally:

```
# graph-maker / miplots4 (feat/histogram-thresholds branch)
cd <visualizations checkout on feat/histogram-thresholds>
pnpm --filter @milaboratories/graph-maker build && (cd packages/graph-maker && pnpm pack --pack-destination .)
cp packages/graph-maker/milaboratories-graph-maker-*.tgz <block>/vendor/graph-maker.tgz
# repeat for miplots4

# structure-viewer (feat/color-scheme-prop branch)
cd <visualizations checkout on feat/color-scheme-prop>
pnpm --filter @milaboratories/structure-viewer build && (cd packages/structure-viewer && pnpm pack --pack-destination .)
cp packages/structure-viewer/milaboratories-structure-viewer-*.tgz <block>/vendor/structure-viewer.tgz
```

Then run `pnpm install --force` in the block to refresh the lockfile.
