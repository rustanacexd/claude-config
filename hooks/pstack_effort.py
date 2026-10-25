#!/usr/bin/env python3
"""Keep agent dispatch effort equal to the calling session's current effort."""

import json
from pathlib import Path
import sys


LEVELS = {"low", "medium", "high", "xhigh", "max", "ultra"}
CODEX_TOOLS = {"spawn_agent", "collaborationspawn_agent"}


def current_effort(event):
    if event["tool_name"] not in CODEX_TOOLS:
        return event["effort"]["level"]

    turn_id = event["turn_id"]
    level = None
    with Path(event["transcript_path"]).open(encoding="utf-8") as transcript:
        for line in transcript:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or row.get("type") != "turn_context":
                continue
            context = row["payload"]
            if context.get("turn_id") == turn_id:
                level = context["effort"]
    if level is None:
        raise ValueError("the current Codex turn is missing from its transcript")
    return level


def rewrite(event):
    tool = event.get("tool_name")
    if tool not in {"Agent", "Task"} | CODEX_TOOLS:
        return None
    level = current_effort(event)
    if level not in LEVELS:
        raise ValueError(f"unsupported session effort: {level!r}")
    args = dict(event["tool_input"])
    args["reasoning_effort" if tool in CODEX_TOOLS else "effort"] = level
    output = {"hookEventName": "PreToolUse", "updatedInput": args}
    if tool in CODEX_TOOLS:
        output["permissionDecision"] = "allow"
    return {"hookSpecificOutput": output}


def main():
    try:
        result = rewrite(json.load(sys.stdin))
    except (AttributeError, KeyError, TypeError, ValueError, OSError) as error:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Cannot inherit the current session effort: {error}",
        }}))
        return
    if result is not None:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
