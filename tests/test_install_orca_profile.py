import importlib
import os
import sys
import tempfile
from pathlib import Path

home = Path(tempfile.mkdtemp())
profile = home / "orca-profile"
os.environ.update({"HOME": str(home), "USERPROFILE": str(home), "CLAUDE_CONFIG_DIR": str(profile),
                   "ORCA_CLAUDE_INJECTED_CONFIG_DIR": str(profile)})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import install  # noqa: E402


def child_env(module):
    seen = {}

    def fake_run(argv, env, **kwargs):
        seen.update(env)
        return type("Result", (), {"returncode": 0, "stdout": "[]", "stderr": ""})()

    module.shutil.which = lambda name: name
    module.subprocess.run = fake_run
    module.run("claude", "plugin", "list", "--json")
    return seen


checks = {
    "Orca's injected config dir is ignored": install.CLAUDE == home / ".claude",
    "claude runs without Orca's config dir": "CLAUDE_CONFIG_DIR" not in child_env(install),
}

del os.environ["ORCA_CLAUDE_INJECTED_CONFIG_DIR"]
install = importlib.reload(install)
checks["a user-set config dir is honored"] = install.CLAUDE == profile
checks["claude runs with a user-set config dir"] = child_env(install).get("CLAUDE_CONFIG_DIR") == str(profile)

os.environ["ORCA_CLAUDE_INJECTED_CONFIG_DIR"] = str(home / "other-profile")
install = importlib.reload(install)
checks["a config dir other than Orca's is honored"] = install.CLAUDE == profile

wrong = [name for name, ok in checks.items() if not ok]
if wrong:
    sys.exit("install Orca profile: " + "; ".join(wrong))
print(f"install Orca profile: {len(checks)} checks ok")
