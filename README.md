# pstack for Codex

A downstream port of Lauren Tan’s pstack for project-local Codex skills. The preview supports the **Investigation** playbook. The generated package includes all 58 upstream skills and their bundled references so the shared entry point can resolve them. Other playbooks are available for inspection and still need compatibility testing.

## Try the preview

Generate the package with Node.js. From the port’s root, copy the generated directory to a disposable project that has an unused `.agents` path.

```bash
node scripts/generate-pstack-harness-trees.mjs
destination=/absolute/path/to/test-project
mkdir "$destination/.agents" && cp -R harness/pstack/codex/. "$destination/.agents/"
```

Open a fresh Codex session in that project and invoke `$poteto-mode` with a question about how a function works. On Codex CLI 0.155.1, opt in to the execution checklist for a single invocation with `-c tools.update_plan.enabled=true`. When the tool is unavailable, the adapter uses a checklist in the conversation. The [review results](REVIEW-RESULTS.md) record where checklist behavior still varies.

## Update upstream

`UPSTREAM.json` records the pstack version and exact Cursor repository commit. Update it with the matching `pstack/` snapshot under `upstream/`. Keep host-specific changes in `docs/harness/codex.md` and `scripts/generate-pstack-harness-trees.mjs`. The generator adds the adapter preamble and sets the Codex invocation policy for explicitly invoked upstream skills. Links to upstream files omitted from the package resolve at the pinned commit.

```bash
node scripts/generate-pstack-harness-trees.mjs
node scripts/generate-pstack-harness-trees.mjs --check
```

The generator checks Cursor term coverage and internal links before writing the package. The `--check` mode also compares the expected tree with the generated files and executable modes. Keep the generated tree and the upstream pin in the same version control update. Poteto Mode receives a distinct preamble because it owns playbook setup. The other wrapped skills receive the shared adapter link.

## Verify Investigation

`fixture/` has a caller and a renderer with a known relationship. With the Codex CLI signed in using a local `auth.json`, the review matrix runs the fixture in read-only sandboxes with disposable, per-process Codex homes. It disables machine-wide personal skills through session-scoped configuration and uses a Git baseline to check the fixture after every run. The matrix saves redacted summaries under `verification/`.

```bash
python3 scripts/run_review.py --jobs 4
```

Use `--case` to select cases and `--runs` to control repeats. The default is three runs per case plus one clean-environment discovery run. For one separately captured `codex exec --json` log, use `python3 scripts/check_verification.py --help`. The verifier records playbook selection, checklist order and wording, final statuses, citations, and fixture integrity. `python3 scripts/probe_tool_schema.py verification/tool-schema.json` checks CLI tool definitions against a loopback test endpoint using a dummy key.

See [the pinned source](UPSTREAM.json) and [attribution](NOTICE). The upstream material is distributed under [MIT](LICENSE).
