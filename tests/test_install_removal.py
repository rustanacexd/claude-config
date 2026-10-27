import contextlib
import io
import os
import sys
import tempfile
import tomllib
from pathlib import Path

home = Path(tempfile.mkdtemp())
os.environ["CLAUDE_CONFIG_DIR"] = str(home / ".claude")
os.environ["CODEX_HOME"] = str(home / ".codex")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import install  # noqa: E402

install.REPO = home / "repo"
(install.REPO / "codex").mkdir(parents=True)
config_path = home / ".codex/config.toml"


def install_template(template):
    (install.REPO / "codex/config.template.toml").write_text(template)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        install.codex_config()
    return tomllib.loads(config_path.read_text()), out.getvalue()


config_path.parent.mkdir(parents=True)
config_path.write_text('user_key = "mine"\n\n[features]\nuser_feature = true\n')
install_template('''model = "gpt-5"
dropped = 1

[features]
kept = true
gone = true

[plugins."kept@mkt"]
enabled = true

[plugins."gone@oldmkt"]
enabled = true
''')
after = '''model = "gpt-5"

[features]
kept = true

[plugins."kept@mkt"]
enabled = true
'''
config, _ = install_template(after)
_, second = install_template(after)
checks = {
    "removed Codex key is gone": "dropped" not in config,
    "removed Codex nested key is gone": "gone" not in config["features"],
    "removed Codex plugin table is gone": "gone@oldmkt" not in config["plugins"],
    "kept Codex keys stay": config["model"] == "gpt-5" and config["features"]["kept"] is True
    and config["plugins"]["kept@mkt"] == {"enabled": True},
    "user Codex keys stay": config["user_key"] == "mine" and config["features"]["user_feature"] is True,
    "second Codex install writes nothing": "wrote" not in second,
}
wrong = [name for name, ok in checks.items() if not ok]
if wrong:
    sys.exit("install removal: " + "; ".join(wrong))
print(f"install removal: {len(checks)} checks ok")
