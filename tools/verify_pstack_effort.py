#!/usr/bin/env python3
"""Run paid, one-message agent probes and check their persisted runtime metadata."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install


def records(path):
    with path.open(encoding="utf-8") as file:
        for line in file:
            yield json.loads(line)


def panel(home):
    for line in (home / "pstack-models.md").read_text().splitlines():
        if line.startswith("arena runners: "):
            return line.split(": ", 1)[1].split(", ")
    raise ValueError(f"No arena panel in {home}")


def run_probe(runtime, effort, directory):
    output = directory / f"{runtime}-{effort}.jsonl"
    child_effort = "low" if effort != "low" else "high"
    models = panel(install.CLAUDE if runtime == "claude" else install.CODEX)
    prompt = (
        "User-authorized fault-injection test of the installed pstack effort hook. "
        "Do no repository work and do not edit files. "
        f"Launch exactly one child on each model: {', '.join(models)}. "
        f"Deliberately request child effort {child_effort}; the hook must replace it with parent effort {effort}. "
        "Each child must reply only PROBE_OK, without tools or further agents. "
        "Wait for all children, then reply ALL_PROBES_COMPLETE. "
    )
    if runtime == "claude":
        prompt += "Use only Agent, subagent_type pstack:poteto-agent, and run_in_background false."
        command = [
            "claude", "-p", "--effort", effort, "--verbose", "--output-format", "stream-json",
            "--permission-mode", "dontAsk", "--tools", "Agent", "--max-budget-usd", "3",
        ]
    else:
        prompt += "Use only spawn_agent and wait_agent, with fork_turns none and explicit reasoning_effort."
        config = tomllib.loads((install.CODEX / "config.toml").read_text())
        hooks = config["hooks"]["PreToolUse"]
        hooks = [group for group in hooks if any("pstack_effort.py" in h["command"] for h in group["hooks"])]
        if len(hooks) != 1:
            raise ValueError("Expected one installed pstack effort hook")
        encoded = install.toml({"probe_hooks": hooks}).decode().strip().split(" = ", 1)[1]
        command = [
            "codex", "--no-daemon", "exec", "--ignore-user-config",
            "--dangerously-bypass-hook-trust", "--json", "-s", "read-only",
            "-m", "gpt-6.1-sol", "-c", "features.hooks=true",
            "-c", f'model_reasoning_effort="{effort}"', "-c", f"hooks.PreToolUse={encoded}", "-",
        ]
    with output.open("w") as stdout, output.with_suffix(".stderr").open("w") as stderr:
        subprocess.run(command, input=prompt, text=True, stdout=stdout, stderr=stderr, check=True, timeout=240)
    return collect(runtime, effort, output)


def collect(runtime, effort, output):
    events = list(records(output))
    rows = []
    if runtime == "claude":
        session_id = next(e["session_id"] for e in events if e.get("subtype") == "init")
        result = next(e for e in reversed(events) if e.get("type") == "result")
        if result.get("is_error"):
            raise ValueError(result)
        parent = next((install.CLAUDE / "projects").glob(f"*/{session_id}.jsonl"))
        settings = json.loads((install.CLAUDE / "settings.json").read_text())
        expected = {settings["env"][f"ANTHROPIC_DEFAULT_{m.upper()}_MODEL"] for m in panel(install.CLAUDE)}
        children = list((parent.parent / session_id / "subagents").glob("*.jsonl"))
        for path in [parent, *children]:
            values = [r for r in records(path) if r.get("type") == "assistant" and "effort" in r]
            if not values:
                raise ValueError(f"No recorded effort in {path}")
            for value in values:
                if value["effort"] != effort:
                    raise AssertionError(f"{path}: {value['effort']} != parent {effort}")
            if path != parent:
                models = {v["message"]["model"] for v in values}
                if len(models) != 1:
                    raise AssertionError(f"Unexpected model fallback in {path}: {models}")
                rows.append({"runtime": runtime, "parent_effort": effort, "model": models.pop(), "child_effort": effort})
    else:
        session_id = next(e["thread_id"] for e in events if e.get("type") == "thread.started")
        expected = set(panel(install.CODEX))
        parent = next((install.CODEX / "sessions").rglob(f"*{session_id}.jsonl"))
        parent_rows = list(records(parent))
        if not any(r.get("type") == "turn_context" and r["payload"].get("effort") == effort for r in parent_rows):
            raise AssertionError("Parent effort was not recorded")
        for path in parent.parent.glob("*.jsonl"):
            with path.open(encoding="utf-8") as file:
                first = json.loads(file.readline())
            source = first.get("payload", {}).get("source")
            spawn = source.get("subagent", {}).get("thread_spawn", {}) if isinstance(source, dict) else {}
            if spawn.get("parent_thread_id") != session_id:
                continue
            contexts = [r["payload"] for r in records(path) if r.get("type") == "turn_context"]
            if not contexts or any(c["effort"] != effort for c in contexts):
                raise AssertionError(f"Child effort mismatch in {path}")
            rows.append({"runtime": runtime, "parent_effort": effort, "model": contexts[-1]["model"], "child_effort": contexts[-1]["effort"]})
    if len(rows) != len(expected) or {r["model"] for r in rows} != expected:
        raise AssertionError(f"Expected {expected}, observed {rows}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", choices=("claude", "codex", "both"), default="both")
    parser.add_argument("--efforts", nargs="+", choices=("low", "medium", "high", "xhigh", "max"), default=["medium", "high"])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--collect-only", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for runtime in ("claude", "codex") if args.runtime == "both" else (args.runtime,):
        for effort in args.efforts:
            if args.collect_only:
                rows.extend(collect(runtime, effort, args.output_dir / f"{runtime}-{effort}.jsonl"))
            else:
                rows.extend(run_probe(runtime, effort, args.output_dir))
    report = args.output_dir / "verified.json"
    report.write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps(rows, indent=2))
    print(f"Verified runtime metadata saved to {report}")


if __name__ == "__main__":
    main()
