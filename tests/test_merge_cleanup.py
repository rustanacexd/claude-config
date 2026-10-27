import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "claude" / "merge_cleanup.py"
sys.path.insert(0, str(HOOK.parent))
from merge_cleanup import merged  # noqa: E402

CASES = {
    "gh pr merge 69 --repo o/r --squash": True,
    "GH_REPO=o/r gh pr merge 69 --rebase": True,
    "gh stack merge": True,
    "gh pr merge 69 --disable-auto": False,
    "gh pr view 69": False,
    'git commit -m "gh pr merge 69"': False,
    "grep -n 'gh stack merge' CLAUDE.md": False,
}

wrong = [command for command, expected in CASES.items() if merged(command) != expected]
if wrong:
    sys.exit("merge_cleanup misjudged: " + "; ".join(wrong))


def run(command):
    event = json.dumps({"tool_input": {"command": command}})
    return subprocess.run([sys.executable, str(HOOK)], input=event, capture_output=True,
                          text=True, check=True).stdout


context = json.loads(run("gh pr merge 69 --repo o/r --squash"))["hookSpecificOutput"]
if context["hookEventName"] != "PostToolUse" or "Clean up branches" not in context["additionalContext"]:
    sys.exit(f"merge_cleanup printed the wrong output: {context}")
if run("gh pr view 69"):
    sys.exit("merge_cleanup printed output for a command that is not a merge")
print(f"merge_cleanup: {len(CASES) + 2} cases ok")
