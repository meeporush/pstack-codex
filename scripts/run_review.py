"""Run the pstack adapter review in fresh local Codex homes."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
from tempfile import TemporaryDirectory
import time

from check_verification import fixture_unchanged, summarize


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "harness/pstack/codex"
PLAYBOOK = BUNDLE / "skills/poteto-mode/playbooks/investigation.md"
AUTH = Path.home() / ".codex/auth.json"
PREAMBLE = ("In Codex, read [the Codex adapter](../../docs/harness/codex.md) once per session before you follow this skill. "
            "It maps the Cursor names in pstack skills to Codex.")
ORDERED = ("In Codex, read [the Codex adapter](../../docs/harness/codex.md) first. Then read the selected playbook "
           "and open its checklist before inspecting project files.")
TRACE = ("Explain what render_receipt does and identify its direct caller. Cite the relevant source files "
         "and line numbers. This is a read-only walkthrough of this directory using local files only.")
MOTIVATION = ("Why does render_receipt add the fee only when item_count is nonzero? Use only local "
              "project evidence and keep the investigation read-only.")
TOOLS = ("exec_command", "spawn_agent", "wait_agent", "send_input", "followup_task", "request_user_input")
PROBE = ("For this diagnostic, report the availability of these exact tool names in your current session. "
         "For each, say available, unavailable, or uncertain, and include a namespace if present. "
         "Do not call or delegate with these tools for the inventory. Names: " + ", ".join(TOOLS) + ".")
CASES = {
    "A-clean": ("List each project instruction file and skill directory loaded in this session. "
                "Use the supplied context. Do not open any additional files.", None),
    "B-stock": ("$poteto-mode " + TRACE, None),
    "C-generic-on": ("$poteto-mode " + TRACE, True),
    "C-generic-off": ("$poteto-mode " + TRACE, False),
    "C-ordered-on": ("$poteto-mode " + TRACE, True),
    "C-ordered-off": ("$poteto-mode " + TRACE, False),
    "D-routing": ("$poteto-mode How does checkout compute the receipt total?", True),
    "E-subset-why": ("$poteto-mode " + MOTIVATION, True),
    "E-full-why": ("$poteto-mode " + MOTIVATION, True),
    "F-implicit": (TRACE, None),
    "G-default-tools": (PROBE, None),
    "G-plan-tools": (PROBE, None),
    "B-project-config": ("$poteto-mode " + TRACE, None),
}
SUBSET = ("poteto-mode", "unslop", "principle-prove-it-works")


def exec_events(prompt, cwd, env, extra, *, keep_trial_rollout=False):
    session = [] if keep_trial_rollout else ["--ephemeral"]
    result = subprocess.run(
        ["codex", "exec", "--disable", "hooks", "--disable", "plugins", "--sandbox", "read-only",
         *session, "--json", *extra, prompt], cwd=cwd, env=env, capture_output=True,
        text=True, timeout=160, check=False,
    )
    rows = []
    for line in result.stdout.splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows, result.returncode


def plan_probe(cwd, env, skill_flags):
    # Use the app server so the actual turn enters Plan mode.
    with subprocess.Popen(
        ["codex", "app-server", "--disable", "hooks", "--disable", "plugins", *skill_flags], cwd=cwd, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
    ) as process, selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        def send(message):
            process.stdin.write(json.dumps(message).encode() + b"\n")
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "pstack-review", "version": "0.1"},
                                                           "capabilities": {"experimentalApi": True}}})
        buffered = b""
        deadline = time.monotonic() + 130
        answer = []
        try:
            while time.monotonic() < deadline:
                if not selector.select(timeout=max(0, deadline - time.monotonic())):
                    break
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    break
                buffered += data
                while b"\n" in buffered:
                    line, buffered = buffered.split(b"\n", 1)
                    reply = json.loads(line)
                    request_id = reply.get("id")
                    if "error" in reply:
                        return {"completed_turn": False, "rpc_error": str(reply["error"].get("message", ""))[:160]}
                    if request_id == 1:
                        send({"method": "initialized"})
                        send({"id": 2, "method": "thread/start", "params": {
                            "cwd": str(cwd), "ephemeral": True, "sandbox": "read-only", "approvalPolicy": "never"}})
                    elif request_id == 2:
                        started = reply["result"]
                        send({"id": 3, "method": "turn/start", "params": {
                            "threadId": started["thread"]["id"], "input": [{"type": "text", "text": PROBE}],
                            "collaborationMode": {"mode": "plan", "settings": {
                                "model": started["model"], "developer_instructions": None}}}})
                    elif reply.get("method") == "item/completed" and reply.get("params", {}).get("item", {}).get("type") == "agentMessage":
                        answer.append(reply["params"]["item"]["text"])
                    elif reply.get("method") == "turn/completed":
                        return {"completed_turn": reply["params"]["turn"]["status"] == "completed",
                                "requested_mode": "plan", "tool_inventory_report": "\n".join(answer)}
            return {"completed_turn": False, "failure": "App server ended or timed out"}
        finally:
            if process.poll() is None:
                process.kill()


def setup_fixture(work, case):
    shutil.copytree(ROOT / "fixture", work)
    if case == "E-subset-why":
        for name in SUBSET:
            shutil.copytree(BUNDLE / "skills" / name, work / ".agents/skills" / name)
        (work / ".agents/docs/harness").mkdir(parents=True)
        shutil.copy2(BUNDLE / "docs/harness/codex.md", work / ".agents/docs/harness/codex.md")
    else:
        shutil.copytree(BUNDLE, work / ".agents")
    if case.startswith("C-"):
        entry = work / ".agents/skills/poteto-mode/SKILL.md"
        source = entry.read_text()
        known = [preamble for preamble in (PREAMBLE, ORDERED) if source.count(preamble) == 1]
        if len(known) != 1:
            raise ValueError("Cannot locate the Codex preamble")
        desired = ORDERED if case.startswith("C-ordered") else PREAMBLE
        entry.write_text(source.replace(known[0], desired, 1))
    if case == "A-clean":
        (work / "AGENTS.md").write_text("# Review fixture instructions\n\npstack-review-project-instructions-canary\n")
    if case == "B-project-config":
        (work / ".codex").mkdir()
        (work / ".codex/config.toml").write_text("[tools.update_plan]\nenabled = true\n")
    subprocess.run(["git", "init", "-q"], cwd=work, check=True, capture_output=True)
    subprocess.run(["git", "add", "checkout.py", "receipt.py"], cwd=work, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=Pstack review", "-c", "user.email=pstack-review@example.invalid",
                    "-c", "core.hooksPath=/dev/null", "commit", "-qm", "Fixture baseline"],
                   cwd=work, check=True, capture_output=True)


def personal_skill_flags():
    paths = set()
    visited = set()
    for directory, children, files in os.walk(Path.home() / ".agents/skills", followlinks=True):
        path = Path(directory)
        target = path.resolve()
        if target in visited:
            children.clear()
            continue
        visited.add(target)
        if "SKILL.md" in files:
            paths.update((path / "SKILL.md", target / "SKILL.md"))
            children.clear()
    if not paths:
        return []
    entries = ", ".join(f'{{path={json.dumps(str(path))},enabled=false}}' for path in sorted(paths))
    return ["-c", f"skills.config=[{entries}]"]


def effective_agent_runtime(codex_home):
    # The home belongs to one run. Keep public mode names and discard the rollout.
    for rollout in (codex_home / "sessions").rglob("rollout-*.jsonl"):
        for line in rollout.read_text().splitlines():
            row = json.loads(line)
            if row.get("type") == "turn_context":
                payload = row["payload"]
                return {"effective_multi_agent_version": payload.get("multi_agent_version"),
                        "effective_collaboration_mode": (payload.get("collaboration_mode") or {}).get("mode")}
    return {}


def inspect_clean_prompt(work, codex_home, env, skill_flags):
    result = subprocess.run(["codex", "debug", "prompt-input", *skill_flags], cwd=work, env=env,
                            capture_output=True, text=True, check=True, timeout=30)
    messages = json.loads(result.stdout)
    instructions = []
    skills = []
    for message in messages:
        for part in message.get("content", []):
            text = part.get("text", "")
            if text.startswith("# AGENTS.md instructions for "):
                instructions.append(text)
            elif text.startswith("<skills_instructions>"):
                skills.append(text)
    project_instructions = (work / "AGENTS.md").read_text().strip()
    expected_instructions = (
        f"# AGENTS.md instructions for {work}\n\n<INSTRUCTIONS>\n{project_instructions}\n\n</INSTRUCTIONS>"
    )
    skill_inventory = "\n".join(skills)
    skill_roots = re.findall(r"(?m)^- `r\d+` = `([^`]+)`$", skill_inventory)
    allowed_roots = {(work / ".agents/skills").resolve(), (codex_home / "skills/.system").resolve()}
    return {
        "copied_user_files": sorted(child.name for child in codex_home.iterdir() if child.name == "auth.json"),
        "project_instruction_present": any(project_instructions in text for text in instructions),
        "original_user_instruction_present": any(text.strip() != expected_instructions for text in instructions),
        "original_user_skills_present": any(Path(root).resolve() not in allowed_roots for root in skill_roots),
        "poteto_mode_in_implicit_skill_list": bool(re.search(r"(?m)^- poteto-mode:", skill_inventory)),
    }


def run_case(case, index, output, skill_flags):
    with TemporaryDirectory(prefix="pstack-review-") as directory:
        temp = Path(directory).resolve()
        work = temp / "fixture"
        codex_home = temp / "codex-home"
        codex_home.mkdir(mode=0o700)
        shutil.copyfile(AUTH, codex_home / "auth.json")
        (codex_home / "auth.json").chmod(0o600)
        # Scope the documented Codex home override to this child process.
        env = {name: value for name, value in os.environ.items() if name not in {"OPENAI_API_KEY", "CODEX_API_KEY"}}
        env["CODEX_HOME"] = str(codex_home)
        setup_fixture(work, case)
        prompt, checklist = CASES[case]
        if prompt.startswith("$poteto-mode "):
            # Include the path so Codex loads the explicit skill before inspecting the fixture.
            skill_path = work / ".agents/skills/poteto-mode/SKILL.md"
            prompt = prompt.replace("$poteto-mode", f"[$poteto-mode]({skill_path})", 1)
        flags = list(skill_flags)
        if checklist is not None:
            flags += ["-c", f"tools.update_plan.enabled={str(checklist).lower()}"]
        if case == "B-project-config":
            flags += ["-c", f"projects.{json.dumps(str(work))}.trust_level=\"trusted\""]

        if case == "G-plan-tools":
            result = plan_probe(work, env, skill_flags)
            result["fixture_unchanged"] = fixture_unchanged(work, ROOT / "fixture")
        else:
            context = inspect_clean_prompt(work, codex_home, env, skill_flags) if case == "A-clean" else {}
            keep_trial_rollout = case == "G-default-tools"
            rows, exit_code = exec_events(prompt, work, env, flags, keep_trial_rollout=keep_trial_rollout)
            result = summarize(rows, PLAYBOOK, work, ROOT / "fixture")
            result.update(context)
            if keep_trial_rollout:
                result.update(effective_agent_runtime(codex_home))
            result["cli_exit_code"] = exit_code
            if case in ("A-clean", "G-default-tools", "E-subset-why", "E-full-why", "D-routing", "F-implicit"):
                tail = next((row["item"]["text"] for row in reversed(rows) if row.get("type") == "item.completed"
                             and row.get("item", {}).get("type") == "agent_message"), "")
                result["answer_excerpt"] = tail.replace(str(work), "<fixture>").replace(str(codex_home), "<isolated-home>")[:2400]
            if not result["completed_turn"]:
                result["failure_events"] = [row["type"] for row in rows if row["type"] in {"error", "turn.failed"}]

    result.update(case=case, run=index)
    folder = output / case / str(index)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "verification-summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "verification")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--case", action="append", choices=CASES)
    args = parser.parse_args()
    if not AUTH.is_file():
        parser.error("Sign in to Codex before running the matrix")
    cases = args.case or CASES
    skill_flags = personal_skill_flags()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        jobs = {pool.submit(run_case, case, i, args.output, skill_flags): (case, i) for case in cases
                for i in range(1, (1 if case == "A-clean" else args.runs) + 1)}
        failed = 0
        for job in as_completed(jobs):
            case, index = jobs[job]
            try:
                result = job.result()
                completed = result["completed_turn"] and result["fixture_unchanged"]
                print(f"{case} {index}: {'completed' if completed else 'incomplete'}", flush=True)
                failed += not completed
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                print(f"{case} {index}: {type(error).__name__}", flush=True)
                folder = args.output / case / str(index)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "verification-summary.json").write_text(json.dumps({
                    "case": case, "run": index, "completed_turn": False, "failure": type(error).__name__,
                }, indent=2) + "\n")
                failed += 1
    raise SystemExit(bool(failed))


if __name__ == "__main__":
    main()
