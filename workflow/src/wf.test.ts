// Workflow test stub — placeholder.
//
// The previous test was inherited from the new-block template (asserting
// hello-from-python / hello-from-tengo round-trip strings); both outputs
// have been gone since this block was bootstrapped and the test has been
// passing only because Vitest skipped it. Removed to avoid the false-
// positive signal.
//
// A real workflow integration test would exercise the PrimaryRef path
// against a fixture upstream PColumn (or the legacy path against
// 1N8Z.pdb) and verify the emitted PFrames match the spec's R37/R38
// PColumn shapes. Punted to a separate slice — the block is currently
// validated end-to-end via the desktop app + pl MCP, not unit tests.
