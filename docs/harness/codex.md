# pstack in Codex

The pstack skills use Cursor tool names. Use these mappings when a playbook names a tool, role, or path. `<pstack>` is the directory containing `skills/` and `docs/`, two levels above this file. For a project-local installation, `<pstack>` is `.agents/`.

The skills-only prototype exercises the read-only Investigation playbook. Other mappings are references for porting additional playbooks.

## Tools

| Cursor | Codex |
| --- | --- |
| `Task` | Use `spawn_agent` when the playbook calls for a delegate and the session exposes and permits it. Collect the result with `wait_agent` when available. |
| `AskQuestion` | Use `request_user_input` when the current mode permits the call. Codex CLI 0.155.1 permits it in Plan Mode by default. In Default mode, ask in the conversation unless `features.default_mode_request_user_input` enables the tool. |
| Open a todolist, or copy steps into the todolist tool | Use `update_plan`. If unavailable, post the checklist under a `Checklist` heading in the conversation and track progress there. End the final reply with that checklist. Use one numbered line per step and put each item's final status in parentheses. |
| Run another pstack skill | Read `<pstack>/skills/<name>/SKILL.md` from this bundle. The user invokes it with `$pstack:<name>` in a plugin install or `$<name>` in a project-local skills install. |
| `Read` | Use `exec_command` with `sed -n` to read a range or `nl -ba` for source line numbers. |
| `Grep` | Use `exec_command` with `rg -n`, scoped to the relevant files or directory. |
| `Glob` | Use `exec_command` with `rg --files -g '<pattern>'` in the relevant directory. Include `--hidden` when searching a hidden directory such as `.agents/`. |

Codex CLI 0.155.1 defaults the checklist tool to off. Enable it for one invocation with `-c tools.update_plan.enabled=true`, or set `[tools.update_plan]` with `enabled = true` in the user config.

Apply the tool mappings in this order:

1. Match the task to a playbook using Poteto Mode. Read the selected playbook before searching or reading project source.
2. Make the checklist your next action. Copy each numbered step verbatim as one item, in order. Start the first item as `in_progress` and the rest as `pending`. With the conversation fallback, post the list with those statuses before source inspection.
3. Follow the playbook and update the checklist as each step finishes. Cite file paths and line numbers for the [Investigation playbook](../../skills/poteto-mode/playbooks/investigation.md). Resolve bundled helpers such as [Unslop](../../skills/unslop/SKILL.md), [Prove It Works](../../skills/principle-prove-it-works/SKILL.md), and [Why](../../skills/why/SKILL.md) from this adapter’s directory.

## Subagent fields

| Cursor | Codex |
| --- | --- |
| `subagent_type: generalPurpose` | Use the default agent role. |
| `poteto-agent` or `comment-sicko` | Set `spawn_agent`’s `agent_type` to the matching configured role when exposed. Otherwise, if the definition is installed, include `<pstack>/agents/<name>.md` in the brief. |
| `readonly: true` | Use `agent_type: "explorer"` when exposed and specify a read-only task in the brief. Enforce read-only permissions on the parent session when required. |
| `readonly: false` | Delegate only the authorized writes, with a specific file or worktree scope. |
| `environment: "cloud"` or `"local"` | Use the current Codex environment. Give concurrent writing delegates separate worktrees when available. |
| `cloud_base_branch` | Give the delegate the exact base ref and the worktree that contains it. |
| `run_in_background: true` | `spawn_agent` starts the delegate asynchronously. |
| `resume` | Use `send_input` for an existing accessible agent on the v1 runtime. Use `followup_task` only if the session exposes it on v2. A fresh agent needs the prior result and a self-contained brief. |
| `file_attachments` | Include accessible file paths in the delegate brief. |

## Models

| Cursor | Codex |
| --- | --- |
| `claude-`, `grok-`, or `gemini-` model slugs, such as `claude-opus-5-5-xhigh-fast` | Omit `model` to use Codex's configured worker or parent default. Report the substitution. Map an effort suffix such as `-xhigh-fast` to `reasoning_effort: "xhigh"` when the session exposes that field and the model accepts it. |
| `gpt-` model slugs | Pass `model` only when the session supports the exact Codex identifier. Separate a Cursor effort suffix from the model ID when applicable. Use the default and explain if the requested model is unavailable. |
| `auto` or `inherit-parent` | Omit the model override. Codex applies configured defaults before falling back to the parent. |
| `pstack-models.mdc` | The preview uses Codex configuration for defaults. Per-role pstack model-rule setup is outside the preview. |

If a playbook requires distinct models, report the models Codex actually used.

## setup-pstack

Where supported, Codex stores subagent defaults in the `[agents]` section of `.codex/config.toml` using `default_subagent_model` and `default_subagent_reasoning_effort`. Project custom roles live under `.codex/agents/<role>.toml`. The Investigation prototype uses the current session model.

## Paths

| Cursor | Codex |
| --- | --- |
| `.cursor/skills/` or `~/.cursor/skills/` | Project `.agents/skills/` or user `~/.agents/skills/`. |
| `~/.cursor/plugins/` or `.cursor-plugin/plugin.json` | The skills-only install resolves files from `<pstack>`. Marketplace installs resolve from their Codex plugin root. |
| `.cursor/rules/*.mdc` or always-applied rules | `AGENTS.md` for durable project instructions. Use Codex configuration for runtime settings. |
| A bundled guide, playbook, or skill | Resolve from `<pstack>` and keep its relative path. |
| Cursor `agent-transcripts` | Persisted local Codex sessions normally live at `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`, under the active Codex home. Match the project and thread before reading a transcript. Ephemeral sessions are outside this layout. |

## Cursor-only features

Map an authorized PR action to the available forge tool. For Cursor-specific Automations, Bugbot, or cloud-agent steps, use an equivalent only when the session actually exposes one and it preserves the step's intent. If the capability is absent, state which step is unavailable and flag any dependent step that remains pending.
