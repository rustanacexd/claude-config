import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "claude"))
from orca_cookie_guard import wipes_cookies  # noqa: E402

CASES = {
    "orca cookie delete --name refreshToken --worktree all --json": True,
    'o(){ orca "$@" --json; }; o cookie delete --name $n': True,
    "orca-dev cookie clear": True,
    "X=1 orca cookie delete": True,
    "cd x && orca cookie delete": True,
    "orca cookie get --url https://x": False,
    'grep -n "orca cookie delete" AGENTS.md': False,
    'git commit -m "block orca cookie delete"': False,
    "node tools/test-session.mjs delete s.json t": False,
    "orca cookie \\\n  delete --name refreshToken": True,
    "git commit -m 'Document workaround; orca cookie delete --name x'": False,
    "grep -n 'example; orca cookie delete' README.md": False,
}

wrong = [command for command, blocked in CASES.items() if wipes_cookies(command) != blocked]
if wrong:
    sys.exit("orca_cookie_guard misjudged: " + "; ".join(wrong))
print(f"orca_cookie_guard: {len(CASES)} cases ok")
