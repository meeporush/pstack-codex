# pstack for Codex

A community port of [pstack](https://github.com/cursor/plugins/tree/main/pstack) for Codex.

## Installation

```bash
codex plugin marketplace add meeporush/pstack-codex && codex plugin add pstack@pstack-codex
```

## Upgrade

```bash
codex plugin marketplace upgrade pstack-codex && codex plugin add pstack@pstack-codex
```

## Verify the installation

```bash
codex plugin list --marketplace pstack-codex
```

The `pstack@pstack-codex` row should show `installed, enabled` and the version number.

## Usage

In Codex, type `$` to open the skill picker, select `pstack:poteto-mode`, and add your task.

```text
$pstack:poteto-mode Explain what one function in this project does. Cite its file and line number. Use only local files and keep it read-only.
```
