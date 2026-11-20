"""Capture selected Codex tool names through a loopback model endpoint."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread

from run_review import TOOLS, plan_probe


class CaptureHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(200, {"object": "list", "data": [{"id": "gpt-6.2-sol", "object": "model"}]})

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if isinstance(request.get("tools"), list):
            self.server.captured.append(request["tools"])
        self.reply(400, {"error": {"message": "Local tool schema capture complete"}})


def tool_specs(value):
    if isinstance(value, list):
        for entry in value:
            yield from tool_specs(entry)
    if isinstance(value, dict):
        name = value.get("name", value.get("type"))
        if isinstance(name, str) and name in {*TOOLS, "update_plan", "tool_search"}:
            yield name, value.get("description", "")
        for entry in value.values():
            yield from tool_specs(entry)


def probe(mode, settings):
    with TemporaryDirectory(prefix="pstack-tool-schema-") as temp, ThreadingHTTPServer(("127.0.0.1", 0), CaptureHandler) as server:
        root = Path(temp).resolve()
        codex_home = root / "codex-home"
        codex_home.mkdir()
        env = {key: value for key, value in os.environ.items() if key not in {"OPENAI_API_KEY", "CODEX_API_KEY"}}
        env["CODEX_HOME"] = str(codex_home)
        env["PSTACK_TOOL_PROBE_KEY"] = "fixture-key"
        server.captured = []
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        provider = (f'{{name="Local schema capture",base_url="http://127.0.0.1:{server.server_port}/v1",'
                    'env_key="PSTACK_TOOL_PROBE_KEY",wire_api="responses",request_max_retries=0,stream_max_retries=0}')
        flags = ["-c", 'model_provider="review_probe"', "-c", f"model_providers.review_probe={provider}",
                 "-c", 'model="gpt-6.2-sol"', *settings]
        if mode == "trusted_project_checklist":
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text("[tools.update_plan]\nenabled = true\n")
            flags += ["-c", f"projects.{json.dumps(str(root))}.trust_level=\"trusted\""]
        if mode == "user_config_checklist":
            (codex_home / "config.toml").write_text("[tools.update_plan]\nenabled = true\n")
        try:
            if mode == "plan":
                plan_probe(root, env, flags)
            else:
                subprocess.run(["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only",
                                "--ephemeral", "--json", *flags, "Reply with OK."],
                               cwd=root, env=env, capture_output=True, timeout=30, check=False)
        finally:
            server.shutdown()
            worker.join()
        specs = dict(tool_specs(server.captured))
        return {"requests_captured": len(server.captured), "tool_names": sorted(specs),
                "request_user_input_description": specs.get("request_user_input")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    modes = {
        "default": [],
        "default_with_requested_input_flag": ["-c", "features.default_mode_request_user_input=true"],
        "default_with_multi_agent_v2": ["-c", "features.multi_agent_v2=true"],
        "default_with_checklist_flag": ["-c", "tools.update_plan.enabled=true"],
        "trusted_project_checklist": [],
        "user_config_checklist": [],
        "plan": [],
    }
    result = {mode: probe(mode, flags) for mode, flags in modes.items()}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(not all(case["requests_captured"] for case in result.values()))


if __name__ == "__main__":
    main()
