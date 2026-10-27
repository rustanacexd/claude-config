import contextlib
import io
import json
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

installed = ["kept@mkt", "gone@oldmkt", "shared@sharedmkt", "other@sharedmkt", "off@offmkt", "mine@usermkt",
             "gone@pstack-claude"]
marketplaces = ["pstack-claude", "mkt", "oldmkt", "oldmkt2", "sharedmkt", "offmkt", "usermkt"]
before = {"kept@mkt": True, "gone@oldmkt": True, "gonetoo@oldmkt2": True, "shared@sharedmkt": True,
          "off@offmkt": False, "gone@pstack-claude": True, "ghost@removedmkt": True}
listings = {
    "claude": ([{"id": p} for p in installed], [{"name": m} for m in marketplaces]),
    "codex": ({"installed": [{"pluginId": p} for p in installed]},
              {"marketplaces": [{"name": m} for m in marketplaces]}),
}
calls = []


def fake_run(*argv):
    plugins, known = listings[argv[0]]
    if argv[2:] == ("list", "--json"):
        return json.dumps(plugins)
    if argv[2:] == ("marketplace", "list", "--json"):
        return json.dumps(known)
    calls.append(argv)
    return ""


install.run = fake_run
install.INSTALLED_SETTINGS.parent.mkdir(parents=True)
install.INSTALLED_SETTINGS.write_text(json.dumps({"enabledPlugins": before}))
install.INSTALLED_CONFIG.write_text("".join(f'[plugins."{p}"]\nenabled = {str(on).lower()}\n' for p, on in before.items()))
removals = {}
for app in listings:
    calls.clear()
    install.install_plugins(app, {"kept@mkt": True})
    removals[app] = set(calls)
expected = {
    "claude": {("claude", "plugin", "uninstall", "gone@oldmkt", "--scope", "user"),
               ("claude", "plugin", "uninstall", "shared@sharedmkt", "--scope", "user"),
               ("claude", "plugin", "uninstall", "gone@pstack-claude", "--scope", "user"),
               ("claude", "plugin", "marketplace", "remove", "oldmkt"),
               ("claude", "plugin", "marketplace", "remove", "oldmkt2")},
    "codex": {("codex", "plugin", "remove", "gone@oldmkt"),
              ("codex", "plugin", "remove", "shared@sharedmkt"),
              ("codex", "plugin", "remove", "gone@pstack-claude"),
              ("codex", "plugin", "marketplace", "remove", "oldmkt"),
              ("codex", "plugin", "marketplace", "remove", "oldmkt2")},
}
for app in listings:
    got = removals[app]
    checks[f"{app}: dropped installed plugins are uninstalled"] = {
        c for c in expected[app] if "marketplace" not in c} <= got
    checks[f"{app}: marketplaces only dropped plugins used are removed"] = {
        c for c in expected[app] if "marketplace" in c} <= got
    checks[f"{app}: kept, disabled, user-installed, already removed, and still-used are left alone"] = got <= expected[app]

install.INSTALLED_SETTINGS.unlink()
install.INSTALLED_CONFIG.unlink()
calls.clear()
for app in listings:
    install.install_plugins(app, {"kept@mkt": True})
checks["no snapshot means nothing is removed"] = calls == []

install.INSTALLED_CONFIG.write_text('[plugins."gone@oldmkt"]\nenabled = true\n')
install.FAILED.append(("codex", "plugin", "list", "--json"))
install_template(after)
install.FAILED.clear()
calls.clear()
install.install_plugins("codex", {"kept@mkt": True})
checks["a failed plugin step keeps the removal for the next run"] = (
    ("codex", "plugin", "remove", "gone@oldmkt") in calls)

listings["codex"][0]["installed"].append({"pluginId": "new@mkt"})
install.FAILED.append(("codex", "plugin", "list", "--json"))
install_template('added_while_failing = 1\n' + after + '\n[plugins."new@mkt"]\nenabled = true\n')
install.FAILED.clear()
calls.clear()
install.install_plugins("codex", {"kept@mkt": True})
config, _ = install_template(after)
checks["a Codex key added during a failed run is removed once the repo drops it"] = (
    "added_while_failing" not in config)
checks["a Codex plugin added during a failed run is removed once the repo drops it"] = (
    ("codex", "plugin", "remove", "new@mkt") in calls)

(install.REPO / "claude").mkdir()
install.INSTALLED_SETTINGS.unlink(missing_ok=True)
with contextlib.redirect_stdout(io.StringIO()):
    (install.REPO / "claude/settings.json").write_text(json.dumps({"effortLevel": "high", "addedWhileFailing": 1}))
    install.FAILED.append(("claude", "plugin", "list", "--json"))
    install.claude_settings()
    install.FAILED.clear()
    (install.REPO / "claude/settings.json").write_text(json.dumps({"effortLevel": "high"}))
    install.claude_settings()
checks["a Claude key added during a failed run is removed once the repo drops it"] = (
    "addedWhileFailing" not in json.loads((home / ".claude/settings.json").read_text()))

install.INSTALLED_SETTINGS.write_text("{}")
install.INSTALLED_CONFIG.write_text('model = "gpt-5"\n\n[plugins."gone@oldmkt"]\n')
calls.clear()
for app in listings:
    install.install_plugins(app, {"kept@mkt": True})
checks["a Codex plugin table without enabled counts as enabled"] = ("codex", "plugin", "remove", "gone@oldmkt") in calls

wrong = [name for name, ok in checks.items() if not ok]
if wrong:
    sys.exit("install removal: " + "; ".join(wrong))
print(f"install removal: {len(checks)} checks ok")
