"""Exercise the updater using a local Git upstream and recorded Codex runs."""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
TEST_CASES = ("B-stock", "D-routing", "E-full-why", "F-implicit")


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def init_repo(repo):
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Updater Test")
    git(repo, "config", "user.email", "updater@example.invalid")


def commit(repo):
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Test snapshot")
    return git(repo, "rev-parse", "HEAD")


class UpdateUpstreamTest(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name).resolve()
        self.source = root / "source"
        self.port = root / "port"
        self.report = root / "report"
        for path in (self.source, self.port):
            path.mkdir()
            init_repo(path)

        shutil.copytree(ROOT / "upstream/pstack", self.source / "pstack")
        old_guide = self.source / "pstack/docs/guide/replaced-guide.md"
        old_guide.write_text("# Old guide\n")
        old_commit = commit(self.source)
        shutil.copytree(self.source / "pstack", self.port / "upstream/pstack")
        for path in ("docs", "fixture"):
            shutil.copytree(ROOT / path, self.port / path)
        for path in ("NOTICE", "LICENSE"):
            shutil.copy2(ROOT / path, self.port / path)
        scripts = self.port / "scripts"
        scripts.mkdir()
        for name in ("generate-pstack-harness-trees.mjs", "update_upstream.py"):
            if (ROOT / "scripts" / name).exists():
                shutil.copy2(ROOT / "scripts" / name, scripts / name)
        # Replay known runner receipts. Generator checks and Git operations are real.
        self.receipts = root / "receipts"
        for case in TEST_CASES:
            shutil.copytree(ROOT / "verification" / case, self.receipts / case)
        (scripts / "run_review.py").write_text(
            "import shutil, sys\n"
            f"shutil.copytree({str(self.receipts)!r}, sys.argv[sys.argv.index('--output') + 1], dirs_exist_ok=True)\n"
        )
        self.pin = self.port / "UPSTREAM.json"
        old_version = json.loads((self.source / "pstack/plugin.json").read_text())["version"]
        self.pin.write_text(json.dumps({"repository": str(self.source), "commit": old_commit, "version": old_version}))
        self.old_pin = self.pin.read_bytes()
        subprocess.run(["node", "scripts/generate-pstack-harness-trees.mjs"], cwd=self.port, check=True, capture_output=True)
        commit(self.port)

        manifest = self.source / "pstack/plugin.json"
        plugin = json.loads(manifest.read_text())
        plugin["version"] = "9.0.0"
        manifest.write_text(json.dumps(plugin))
        self.source_readme = self.source / "pstack/README.md"
        with self.source_readme.open("a") as readme:
            readme.write("\nUpdated upstream README.\n")
        old_guide.unlink()
        (self.source / "pstack/docs/guide/new-guide.md").write_text("# New guide\n")
        self.new_commit = commit(self.source)

    def update(self):
        return subprocess.run(
            [sys.executable, "scripts/update_upstream.py", "--output", str(self.report)],
            cwd=self.port, text=True, capture_output=True,
        )

    def test_updates_pin_snapshot_and_package_from_main(self):
        result = self.update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        pin = json.loads(self.pin.read_text())
        self.assertEqual((pin["commit"], pin["version"]), (self.new_commit, "9.0.0"))
        self.assertIn("Updated upstream README.", (self.port / "harness/pstack/codex/README.md").read_text())
        self.assertTrue((self.port / "harness/pstack/codex/docs/guide/new-guide.md").is_file())
        self.assertFalse((self.port / "harness/pstack/codex/docs/guide/replaced-guide.md").exists())
        self.assertTrue((self.report / "D-routing/1/verification-summary.json").is_file())

    def test_broken_generated_links_leave_the_port_clean(self):
        with self.source_readme.open("a") as readme:
            readme.write("\n[Missing link](missing-file.md)\n")
        commit(self.source)
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing-file.md", result.stdout + result.stderr)
        self.assertEqual(self.pin.read_bytes(), self.old_pin)
        self.assertEqual(git(self.port, "status", "--porcelain"), "")

    def test_completed_runs_with_bad_routing_leave_the_port_clean(self):
        for path in (self.receipts / "D-routing").glob("*/verification-summary.json"):
            receipt = json.loads(path.read_text())
            receipt["selected_playbook"] = None
            path.write_text(json.dumps(receipt))
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("D-routing", result.stdout + result.stderr)
        self.assertEqual(self.pin.read_bytes(), self.old_pin)
        self.assertEqual(git(self.port, "status", "--porcelain"), "")

    def test_preserves_edits_to_generated_files(self):
        path = self.port / "harness/pstack/codex/README.md"
        path.write_text("Local edit")
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("harness/pstack/codex/README.md", result.stdout + result.stderr)
        self.assertEqual(path.read_text(), "Local edit")
        self.assertEqual(self.pin.read_bytes(), self.old_pin)


if __name__ == "__main__":
    unittest.main()
