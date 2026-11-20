# Codex adapter review results

The full generated package resolves references that the prototype omitted. Clean runs also showed that Poteto Mode needs its stronger preamble to open the checklist before source inspection. Exact checklist wording still varies, so the strict compatibility check remains open. The preview scope is Investigation.

The tests used Codex CLI 0.155.1 and the pstack 0.15.46 revision in [UPSTREAM.json](UPSTREAM.json). The matrix produced 37 per-run summaries. Three additional signed-in runs recorded the effective collaboration runtime. Two smoke runs checked the final generated package. The [loopback schema probe](verification/tool-schema.json) captured seven requests with a dummy provider key. Its results distinguish tool definitions from a model's self-reported inventory.

## A. Instruction and skill isolation

A pilot run with a new Codex home excluded user-level instructions. It still advertised personal skills from `~/.agents/skills`, which Codex discovers independently of its own home. The final matrix copied only `auth.json` into each disposable home and disabled the discovered personal skills through invocation-scoped `skills.config` entries. The clean probe found **zero user-level instructions and zero personal skills** after that filter. It checks the prompt against the fixture’s instructions and allows only the fixture and system skill roots. The project canary, the upstream `setup-pstack` skill, and the system skills `imagegen`, `openai-docs`, `plugin-creator`, `skill-creator`, and `skill-installer` were still visible. [Clean discovery receipt](verification/A-clean/1/verification-summary.json) · [Codex skill discovery](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)

## B. Checklist default and project config

All three stock runs used the conversation checklist. All three runs with the setting in a trusted project’s `.codex/config.toml` also used the conversation checklist. The loopback probe confirmed that `update_plan` appeared when enabled in user config or by flag, and stayed absent with only trusted project config. The least intrusive opt-in on this build is `codex exec -c tools.update_plan.enabled=true`. For repeated use, set `[tools.update_plan]` with `enabled = true` in user config. [Stock runs](verification/B-stock/) · [Project-config runs](verification/B-project-config/) · [Captured schemas](verification/tool-schema.json) · [Pinned CLI default](https://github.com/openai/codex/blob/rust-v0.155.1/codex-rs/core/src/config/mod.rs#L2672-L2678)

## C. Preamble comparison, original wording, and fallback status

Each row represents three clean runs. “Verbatim” means the initial checklist text matched the four numbered upstream steps after removing the list numbering and status fields.

| Preamble | Checklist path | Checklist before source | Four items | Verbatim wording | Four completed statuses at end |
| --- | --- | ---: | ---: | ---: | ---: |
| Generic | Native | 0/3 | 3/3 | 2/3 | 3/3 |
| Generic | Conversation | 1/3 | 3/3 | 1/3 | 1/3 |
| Ordered | Native | 3/3 | 3/3 | 2/3 | 3/3 |
| Ordered | Conversation | 3/3 | 3/3 | 2/3 | 3/3 |

The generator applies the ordered preamble only to `poteto-mode`. The other 21 wrapped skills use the shared line. The fallback preserved all four final statuses in the ordered comparison. It did so in only 1/3 stock runs and 2/3 trusted-project-config runs, so checklist completion in conversation remains variable even when ordering succeeds. [Comparison receipts](verification/) · [Generator override](scripts/generate-pstack-harness-trees.mjs)

## D. Playbook selection without a routing hint

All three runs asking how checkout computes the receipt total selected Investigation on their own and opened four checklist items before source inspection. All three finished with source citations. One of three preserved the exact step text. [Routing receipts](verification/D-routing/)

## E. Missing `why` helper

All three subset runs tried the `why` path, failed to load it, and continued with a source-based explanation. All three full-tree runs loaded it successfully. The fixture establishes how the fee is computed. Its local history contains a baseline commit and gives no evidence about the business reason for the policy. [Subset receipts](verification/E-subset-why/) · [Full-tree receipts](verification/E-full-why/)

## F. Explicit invocation

All three runs without `$poteto-mode` answered the question directly. The traces showed no read of Poteto Mode, the adapter, or a Poteto Mode playbook. The clean prompt inventory also omitted Poteto Mode from the list of automatically available skills. The generator writes 57 explicit-only metadata files for upstream skills marked that way. `setup-pstack` retains upstream’s implicit availability. [Implicit-invocation receipts](verification/F-implicit/)

The final package repeated the routing and implicit-invocation checks once each after the tool mapping clarifications. The explicit run selected Investigation and opened its four verbatim steps before reading source. The implicit run answered directly. [Final package receipts](verification/final-smoke/)

## G. Tool exposure in Default and Plan modes

| Tool | Observed exposure and mode |
| --- | --- |
| `exec_command` | Present in Default and Plan request schemas. The Investigation runs also used the shell to read the fixture. |
| `spawn_agent`, `wait_agent` | Present in the v1 and v2 schema captures. All signed-in inventory reports named both. |
| `send_input` | Present in the v1 captures. The signed-in default runs reported it unavailable. Their recorded active runtime was v2. |
| `followup_task` | Present when the mock CLI enabled `features.multi_agent_v2=true`. The signed-in default runs reported it available without a flag, and the recorded runtime was v2. Model and host settings can select v2. |
| `request_user_input` | Advertised in the schemas. The tool description and handler restrict calls to Plan Mode by default. With `features.default_mode_request_user_input=true`, the description permits calls in Default and Plan. All three live Plan Mode reports listed it as available. |

The signed-in default inventory responses were self-reports. We independently checked the request schemas and the actual default runtime recorded in temporary session metadata. Tool invocation for subagents and the structured question form was outside these exposure tests. [Default inventory](verification/G-default-tools/) · [Plan inventory](verification/G-plan-tools/) · [Recorded default runtime](verification/runtime-check/) · [Schema receipts](verification/tool-schema.json) · [Mode gate in Codex](https://github.com/openai/codex/blob/rust-v0.155.1/codex-rs/core/src/tools/handlers/request_user_input.rs#L75-L85)

## H. Read-only enforcement and transcript location

Git and a byte comparison confirmed that `checkout.py` and `receipt.py` stayed unchanged in all 42 signed-in runs. The machine's default local transcript location is `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`. An existing persisted file matched that pattern. An isolated home uses its own `sessions/` directory. The runtime probes read only the owner run’s mode fields from their temporary homes and discarded the rollouts afterward.

## Generator and checker

The generated tree contains all 58 skills, the upstream agent briefs, guides, and license, plus the shared Codex adapter and attribution. Coverage, link validation, and `--check` passed. Scratch negative tests verified that the generator rejects a removed mapping, an unresolved relative link, and a hand-edited generated file. Synthetic checker tests caught a late checklist, missing final statuses, and edited fixture bytes. [Generator](scripts/generate-pstack-harness-trees.mjs) · [JSONL checker](scripts/check_verification.py) · [Live runner](scripts/run_review.py)

## Review choices and remaining gaps

- **Generic preamble for Poteto Mode.** The comparison favored the stronger preamble across both checklist modes. It is a documented generator override scoped to the router.
- **Model fallback.** Omitting a non-Codex model ID follows Codex's configured subagent defaults, with parent inheritance as the fallback. The adapter preserves that precedence and applies an effort suffix only if the available model and tool accept it. [Codex subagent configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents#custom-agents)
- **Exact wording.** The verbatim-copy instruction and regression check are present. The live model still paraphrased some steps. Exact wording is a remaining compatibility gap.
- **Project-local checklist setting.** The tested build needs a session flag or user config for this setting. The branch keeps the user-level setting untouched and documents the one-run flag.
- **Scope.** Investigation has live verification. Other playbooks, subagent execution, and structured-question invocation need their own end-to-end tests before they can be claimed as supported.
