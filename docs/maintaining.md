# Maintaining pstack for Codex

## How we keep the plugin up to date

We keep a copy of the exact version of pstack we tested. To bring in changes from the original project, we download the latest pstack files, rebuild the Codex plugin, and test its skills in fresh Codex sessions. The tests check that Codex opens the Investigation checklist, finds the bundled helpers, and cites source lines while leaving the example files alone.

On macOS or Linux, run this from the root of this repo on a new branch. The updater uses Git, Node.js, Python 3.12 or newer, and a Codex CLI signed in with a local `auth.json` file.

```bash
python3 scripts/update_upstream.py
```

The script pulls the latest `main` from the original pstack repo and tests the bundled skills in a temporary directory. Each live check runs three times. All runs must finish without changing the example files, and at least two runs per check must show the expected behavior. If the checks pass, the script records the exact version and Git commit in `UPSTREAM.json` and replaces the saved copy and built plugin for review. Start with no pending edits to those files. The script prints where it saved the test summaries. Use `--output` to choose an empty directory.

For a new plugin release, update the version in `docs/harness/codex-plugin.json` and rebuild with `node scripts/generate-pstack-harness-trees.mjs`. Run it again with `--check` to confirm that the packaged files match the saved source and Codex adapter.

## Verify Investigation

In a new Codex session in a project with source files, try this prompt.

```text
$pstack:poteto-mode Explain what one function in this project does. Cite its file and line number. Use only local files and keep it read-only.
```

You should see an Investigation checklist and a cited explanation of a function in your project. This flow was verified with Codex CLI `0.155.1`. [Compatibility test results](../REVIEW-RESULTS.md)

`fixture/` has a caller and a renderer with a known relationship. With the Codex CLI signed in using a local `auth.json`, the review matrix runs the fixture in read-only sandboxes with disposable, per-process Codex homes. It disables machine-wide personal skills through session-scoped configuration and uses a Git baseline to check the fixture after every run. The matrix saves redacted summaries under `verification/`.

```bash
python3 scripts/run_review.py --jobs 4
```

Use `--case` to select cases and `--runs` to control repeats. The default is three runs per case plus one clean-environment discovery run. For one separately captured `codex exec --json` log, use `python3 scripts/check_verification.py --help`. The verifier records playbook selection, checklist order and wording, final statuses, citations, and fixture integrity. `python3 scripts/probe_tool_schema.py verification/tool-schema.json` checks CLI tool definitions against a loopback test endpoint using a dummy key.

See [the exact version we use](../UPSTREAM.json) and [attribution](../NOTICE). The original pstack files are distributed under [MIT](../LICENSE).
