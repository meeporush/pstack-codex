# pstack for Codex

A community port of Lauren Tan’s pstack for Codex. The preview supports the **Investigation** playbook, which traces code and cites the relevant source lines.

## Quickstart

With a signed-in Codex CLI, paste this to add the pstack marketplace and install the plugin.

```bash
codex plugin marketplace add meeporush/pstack-codex && codex plugin add pstack@pstack-codex
```

In a new Codex session in a project with source files, paste this to verify the installation.

```text
$pstack:poteto-mode Explain what one function in this project does. Cite its file and line number. Use only local files and keep it read-only.
```

You should see an Investigation checklist and a cited explanation of a function in your project. This flow was verified with Codex CLI `0.155.1`. [Compatibility test results](REVIEW-RESULTS.md)

## Update upstream

Run the updater from the port’s root on a branch for the upstream update. It uses Git, Node.js, Python 3.12 or newer, and a signed-in Codex CLI on macOS or Linux.

```bash
python3 scripts/update_upstream.py
```

The updater fetches `main` from the repository in `UPSTREAM.json`, imports that commit’s `pstack/` snapshot, and reads the release version from the plugin manifest. It builds the Codex package in a temporary directory and runs the generator’s coverage, link, and drift checks. It then runs three live checks each for stock Investigation, native checklist routing, bundled `why` routing, and explicit invocation. Every run must finish with the fixture unchanged. Each case must meet its behavioral checks in at least two runs. The receipts also record checklist wording and fallback completion.

After those checks pass, the updater replaces `UPSTREAM.json`, `upstream/pstack/`, and `harness/pstack/codex/` together and leaves them ready for Git review. It requires those paths to be clean before replacing them. Set `--output` to keep the redacted receipts in a specific empty directory. The default creates a temporary directory and prints its path.

Keep Codex-specific changes in `docs/harness/codex.md` and `scripts/generate-pstack-harness-trees.mjs`. The generator adds the adapter preamble and Codex invocation policy. Poteto Mode receives a distinct preamble because it owns playbook setup. Links to upstream files outside the generated package resolve at the pinned commit. For a local rebuild of the existing pin, run the generator directly. Its `--check` option compares the expected tree with the generated files and executable modes. Update the version in `docs/harness/codex-plugin.json` before generating a new plugin release.

## Verify Investigation

`fixture/` has a caller and a renderer with a known relationship. With the Codex CLI signed in using a local `auth.json`, the review matrix runs the fixture in read-only sandboxes with disposable, per-process Codex homes. It disables machine-wide personal skills through session-scoped configuration and uses a Git baseline to check the fixture after every run. The matrix saves redacted summaries under `verification/`.

```bash
python3 scripts/run_review.py --jobs 4
```

Use `--case` to select cases and `--runs` to control repeats. The default is three runs per case plus one clean-environment discovery run. For one separately captured `codex exec --json` log, use `python3 scripts/check_verification.py --help`. The verifier records playbook selection, checklist order and wording, final statuses, citations, and fixture integrity. `python3 scripts/probe_tool_schema.py verification/tool-schema.json` checks CLI tool definitions against a loopback test endpoint using a dummy key.

See [the pinned source](UPSTREAM.json) and [attribution](NOTICE). The upstream material is distributed under [MIT](LICENSE).
