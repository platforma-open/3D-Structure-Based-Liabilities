---
'@platforma-open/milaboratories.3d-structure-based-liabilities': patch
---

Pass `--registry-serve-url` when publishing the block

`block-tools` made `--registry-serve-url` a required option for `publish`, and the facade's
`prepublishOnly` predates that. With block-tools moving from 2.11.0 to 2.14.3 on this branch, the
release would have failed the way 3d-structure-prediction's already did:

```
error: required option '--registry-serve-url <url>' not specified
```

The component packages publish to npm before the facade runs, so the failure leaves the block
itself unpublished at a version whose parts are already out. Fixed before that happens rather
than after.

The redundant `block-tools pack &&` prefix goes with it: `build` already runs
`shx rm -rf ./block-pack && block-tools pack`, and CI publishes with `build-script-name: 'build'`.
