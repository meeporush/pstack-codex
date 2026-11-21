"""Fetch pstack from upstream main, rebuild the Codex package, and verify it."""

import argparse
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory, mkdtemp


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "upstream/pstack"
BUNDLE = "harness/pstack/codex"
PIN = "UPSTREAM.json"
MANAGED = (SNAPSHOT, BUNDLE, PIN)
GENERATOR = ("node", "scripts/generate-pstack-harness-trees.mjs")
CASES = ("B-stock", "D-routing", "E-full-why", "F-implicit")
RUNS = 3


def require_clean_paths():
    changes = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all", "--ignored=matching", "--", *MANAGED],
        cwd=ROOT, text=True,
    )
    if changes:
        raise ValueError(f"Resolve changes to the pin, snapshot, or generated package first.\n{changes.rstrip()}")


def fetch_snapshot(repository, candidate):
    checkout = candidate / "source"
    checkout.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=checkout, check=True)
    subprocess.run(["git", "fetch", "--depth=1", "--no-tags", "--", repository, "refs/heads/main"],
                   cwd=checkout, check=True)
    commit = subprocess.check_output(["git", "rev-parse", "FETCH_HEAD"], cwd=checkout, text=True).strip()
    archive = checkout / "pstack.tar"
    subprocess.run(["git", "archive", f"--output={archive}", commit, "pstack/"], cwd=checkout, check=True)
    destination = candidate / "upstream"
    destination.mkdir()
    with tarfile.open(archive) as tar:
        for entry in tar.getmembers():
            if not (entry.isdir() or entry.isfile()):
                raise ValueError(f"Unsupported entry in upstream snapshot: {entry.name}")
        tar.extractall(destination, filter="data")
    plugin = json.loads((candidate / SNAPSHOT / "plugin.json").read_text())
    version = plugin.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Upstream pstack/plugin.json is missing a version")
    return commit, version


def investigation_passed(case, receipt):
    if case == "F-implicit":
        return (receipt["checklist_path"] == "none" and receipt["selected_playbook"] is None
                and not (receipt["poteto_mode_read"] or receipt["adapter_read"]))
    if receipt["selected_playbook"] != "investigation" or not receipt["adapter_read"]:
        return False
    if case == "E-full-why":
        return receipt["why_read"]
    if not (receipt["checklist_before_source"] and receipt["expected_item_count"] > 0
            and receipt["initial_item_count"] == receipt["expected_item_count"]
            and receipt["cites_source_lines"] and receipt["identifies_fee"]):
        return False
    if case == "D-routing":
        return receipt["checklist_path"] == "native" and receipt["all_items_completed"]
    return receipt["checklist_path"] in {"conversation", "native"} and receipt["identifies_direct_caller"]


def verify_candidate(candidate, output):
    command = [sys.executable, "scripts/run_review.py", "--runs", str(RUNS), "--output", str(output)]
    for case in CASES:
        command.extend(("--case", case))
    subprocess.run(command, cwd=candidate, check=True)
    failed = []
    for case in CASES:
        receipts = [json.loads((output / case / str(index) / "verification-summary.json").read_text())
                    for index in range(1, RUNS + 1)]
        if not all(receipt["completed_turn"] and receipt["fixture_unchanged"] for receipt in receipts):
            raise ValueError(f"{case} has incomplete runs or changed fixtures")
        passed = sum(investigation_passed(case, receipt) for receipt in receipts)
        print(f"{case}: {passed}/{RUNS} behavioral checks passed", flush=True)
        if passed <= RUNS // 2:
            failed.append(case)
    if failed:
        raise ValueError("Upstream candidate failed the Investigation checks for " + ", ".join(failed))


def install_candidate(candidate):
    require_clean_paths()
    backup = candidate / "previous"
    backup.mkdir()
    moved = []
    try:
        for name in MANAGED:
            previous = backup / name
            previous.parent.mkdir(parents=True, exist_ok=True)
            (ROOT / name).rename(previous)
            moved.append(name)
            (candidate / name).rename(ROOT / name)
        subprocess.run([*GENERATOR, "--check"], cwd=ROOT, check=True)
    except BaseException:
        for name in reversed(moved):
            if (ROOT / name).exists():
                (ROOT / name).rename(candidate / name)
            (backup / name).rename(ROOT / name)
        raise


def update(output):
    require_clean_paths()
    old_pin = json.loads((ROOT / PIN).read_text())
    # Stage on the same filesystem so verified directories can be renamed into place.
    with TemporaryDirectory(prefix=".pstack-update-", dir=ROOT) as directory:
        candidate = Path(directory)
        commit, version = fetch_snapshot(old_pin["repository"], candidate)
        new_pin = {**old_pin, "commit": commit, "version": version}
        print(f"Fetched pstack {version} at {commit}", flush=True)
        (candidate / PIN).write_text(json.dumps(new_pin, indent=2) + "\n")
        for name in ("docs", "fixture", "scripts"):
            shutil.copytree(ROOT / name, candidate / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(ROOT / "NOTICE", candidate)
        subprocess.run(GENERATOR, cwd=candidate, check=True)
        subprocess.run([*GENERATOR, "--check"], cwd=candidate, check=True)
        if output is None:
            output = Path(mkdtemp(prefix="pstack-update-verification-"))
        else:
            output.mkdir(parents=True, exist_ok=True)
            if any(output.iterdir()):
                raise ValueError(f"Choose an empty directory for verification receipts: {output}")
        print(f"Verification receipts: {output}", flush=True)
        (output / "update.json").write_text(json.dumps(new_pin, indent=2) + "\n")
        verify_candidate(candidate, output)
        install_candidate(candidate)
    print("Updated the working tree. Review the changes with git status and git diff.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Empty directory for live verification receipts")
    args = parser.parse_args()
    try:
        lock = subprocess.check_output(["git", "rev-parse", "--git-path", "pstack-updater"],
                                       cwd=ROOT, text=True).strip()
        with (ROOT / lock).open("a") as lock_file:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError("An upstream update is already running in this checkout") from error
            update(args.output.resolve() if args.output else None)
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"Update failed because {error.cmd[0]} exited with status {error.returncode}. See its output above.\n")
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        parser.exit(1, f"Update failed. {error}\n")


if __name__ == "__main__":
    main()
