import json
import os
import sys
import tempfile
from pathlib import Path

home = Path(tempfile.mkdtemp())
os.environ["CLAUDE_CONFIG_DIR"] = str(home / ".claude")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import install  # noqa: E402

install.REPO = home / "repo"
(install.REPO / "claude").mkdir(parents=True)
live_path = home / ".claude/settings.json"


def install_repo(settings):
    (install.REPO / "claude/settings.json").write_text(json.dumps(settings))
    install.claude_settings()
    return json.loads(live_path.read_text())


before = {
    "effortLevel": "medium",
    "skipWorkflowUsageWarning": True,
    "modelSettings": {"claude-opus-5-5": {"effortLevel": "medium"}, "claude-fable-5-1": {"effortLevel": "high"}},
    "permissions": {"deny": ["Artifact", "DesignSync"]},
    "env": {"KEEP": "1", "DROP": "1"},
}
live_path.parent.mkdir(parents=True)
live_path.write_text(json.dumps({
    "permissions": {"allow": ["Bash(ls)"]},
    "modelSettings": {"claude-opus-5-5": {"autoCompactWindow": 400000}},
    "env": {"USER_ADDED": "1", "DROP": "1"},
}))
install_repo(before)

after = {
    "effortLevel": "medium",
    "modelSettings": {"claude-fable-5-1": {"effortLevel": "high"}},
    "permissions": {"deny": ["DesignSync"]},
    "env": {"KEEP": "1"},
}
live = install_repo(after)
checks = {
    "removed top-level key is gone": "skipWorkflowUsageWarning" not in live,
    "removed nested key is gone": "DROP" not in live["env"],
    "removed model effort is gone": "effortLevel" not in live["modelSettings"]["claude-opus-5-5"],
    "kept repo keys stay": live["env"]["KEEP"] == "1" and live["effortLevel"] == "medium",
    "user env var stays": live["env"]["USER_ADDED"] == "1",
    "Claude-written model field stays": live["modelSettings"]["claude-opus-5-5"] == {"autoCompactWindow": 400000},
    "user allow rule stays": live["permissions"]["allow"] == ["Bash(ls)"],
    "repo list replaces live list": live["permissions"]["deny"] == ["DesignSync"],
    "installer hooks stay": "merge_guard.py" in json.dumps(live["hooks"]),
    "second install is a no-op": install_repo(after) == live,
}
wrong = [name for name, ok in checks.items() if not ok]
if wrong:
    sys.exit("install settings: " + "; ".join(wrong))
print(f"install settings: {len(checks)} checks ok")
