"""Summarize a Codex Investigation run without exporting the raw transcript."""

import argparse
import json
import re
import subprocess
from pathlib import Path


SOURCE_FILES = ("checkout.py", "receipt.py")
STATUS = r"in[ _-]progress|pending|completed?|done|skipped|blocked"
ITEM = re.compile(rf"(?m)^\s*\d+[.)]\s+(.+?)\s+\(({STATUS})\)[.!]?\s*$", re.I)


def numbered_steps(playbook):
    return re.findall(r"(?m)^\d+\.\s+(.+)$", playbook.read_text())


def conversation_checklist(text):
    heading = re.search(r"\bchecklist\b\s*:?[ \t]*", text, re.I)
    if not heading:
        return []
    body = text[heading.end():]
    if items := ITEM.findall(body):
        return items
    # Accept inline numbering since CLI progress messages can collapse newlines.
    return re.findall(rf"\b\d+[.)]\s+(.+?)\s+\(({STATUS})\)", body, re.I)


def shell_command(row):
    item = row.get("item", {})
    if row.get("type") == "item.started" and item.get("type") == "command_execution":
        return item.get("command", "")
    return ""


def inspects_fixture(command):
    if not command or re.search(r"\brg\s+--files\b|\bgit\s+status\b", command):
        return False
    if re.search(r"\b(?:checkout\.py|receipt\.py|render_receipt)\b", command):
        return True
    return bool(re.search(r"\b(?:rg|grep)\b", command) and re.search(r"\s\.['\"\s]*$", command))


def fixture_unchanged(fixture, baseline):
    git = subprocess.run(
        ["git", "diff", "--exit-code", "HEAD", "--", *SOURCE_FILES],
        cwd=fixture, capture_output=True, check=False,
    )
    return git.returncode == 0 and all((fixture / name).read_bytes() == (baseline / name).read_bytes()
                                        for name in SOURCE_FILES)


def summarize(events, playbook, fixture, baseline):
    steps = numbered_steps(playbook)
    if not steps:
        raise ValueError(f"No numbered steps in {playbook}")
    indexed = list(enumerate(events))
    messages = [(i, row["item"]["text"]) for i, row in indexed
                if row.get("type") == "item.completed" and row.get("item", {}).get("type") == "agent_message"]
    commands = [(i, command) for i, row in indexed if (command := shell_command(row))]
    native = [(i, row["item"]["items"]) for i, row in indexed if row.get("item", {}).get("type") == "todo_list"]
    chat = [(i, items) for i, text in messages if (items := conversation_checklist(text))]
    first_source = next((i for i, command in commands if inspects_fixture(command)), None)
    answer = messages[-1][1] if messages else ""
    final_chat = conversation_checklist(answer)
    if native:
        path = "native"
        checklist_index, first = native[0]
        first_steps = [item["text"] for item in first]
        end = native[-1][1]
        finals = ["completed" if item["completed"] else "unfinished" for item in end]
    elif chat:
        path = "conversation"
        checklist_index, first = chat[0]
        first_steps = [text for text, _ in first]
        finals = [status.lower() for _, status in final_chat]
    else:
        path = "none"
        checklist_index, first_steps, finals = None, [], []

    return {
        "completed_turn": any(row.get("type") == "turn.completed" for row in events),
        "selected_playbook": next((match.group(1) for _, cmd in commands
                                    if (match := re.search(r"poteto-mode/playbooks/([a-z-]+)\.md", cmd))), None),
        "poteto_mode_read": any("poteto-mode/SKILL.md" in cmd for _, cmd in commands),
        "adapter_read": any("docs/harness/codex.md" in cmd for _, cmd in commands),
        "why_path_attempted": any("skills/why/SKILL.md" in cmd for _, cmd in commands),
        "why_read": any("skills/why/SKILL.md" in row.get("item", {}).get("command", "")
                        and row.get("type") == "item.completed" and row["item"].get("exit_code") == 0 for row in events),
        "checklist_path": path,
        "first_source_event": first_source,
        "first_checklist_event": checklist_index,
        "checklist_before_source": checklist_index is not None and first_source is not None and checklist_index < first_source,
        "expected_item_count": len(steps),
        "initial_item_count": len(first_steps),
        "original_step_wording": first_steps == steps,
        "final_item_statuses": finals,
        "all_items_completed": len(finals) == len(steps) and all(x in {"complete", "completed", "done"} for x in finals),
        "cites_source_lines": all(re.search(rf"{re.escape(name)}:\d+\b", answer) for name in SOURCE_FILES),
        "identifies_direct_caller": bool(re.search(r"\bcheckout\b", answer) and re.search(r"\b(?:call(?:s|er|ed)?|invok\w+)\b", answer, re.I)),
        "identifies_fee": bool(re.search(r"\b175\s+cents\b|\$1\.75", answer)),
        "fixture_unchanged": fixture_unchanged(fixture, baseline),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--playbook", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    events = [json.loads(line) for line in args.events.read_text().splitlines() if line.strip()]
    result = summarize(events, args.playbook, args.fixture, args.baseline)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    checks = ("completed_turn", "checklist_before_source", "original_step_wording", "all_items_completed",
              "cites_source_lines", "identifies_direct_caller", "identifies_fee", "fixture_unchanged")
    if not all(result[check] for check in checks):
        parser.exit(1)


if __name__ == "__main__":
    main()
