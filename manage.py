#!/usr/bin/env python3
"""Portable Claude/Codex setup. Requires Python 3.11 or newer."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil

if sys.version_info < (3, 11):
    sys.exit("Python 3.11 or newer is required")

from portable.manage import load, refresh
from portable.apps import (
    installed,
    restore_preserving_flags,
    install_tools,
    ensure_sentry,
)

REPO = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=["bootstrap", "refresh", "doctor", "inventory"],
    )
    parser.add_argument("--app", choices=["claude", "codex", "all"], default="all")
    parser.add_argument(
        "--home",
        type=Path,
        help="Isolated root containing claude and codex homes; selected single app uses this path directly",
    )
    parser.add_argument("--install-tools", action="store_true")
    args = parser.parse_args()
    apps = ["claude", "codex"] if args.app == "all" else [args.app]
    homes = {
        app: Path(
            os.environ.get(
                "CLAUDE_CONFIG_DIR" if app == "claude" else "CODEX_HOME",
                str(Path.home() / ("." + app)),
            )
        )
        .expanduser()
        .absolute()
        for app in apps
    }
    if args.home:
        homes = {
            app: args.home.absolute() / app
            if args.app == "all"
            else args.home.absolute()
            for app in apps
        }
    manifest, plugins = load(REPO)
    issues = []
    if args.operation in ("bootstrap", "refresh"):
        if args.install_tools:
            if args.operation != "bootstrap":
                raise ValueError("--install-tools is only supported with bootstrap")
            install_tools(apps)
        changed, issues = refresh(REPO, homes, apps)
        print(f"Applied {len(changed)} file changes")
        if args.operation == "bootstrap":
            for app in apps:
                issues.extend(
                    restore_preserving_flags(
                        app, homes[app], [p for p in plugins if p["app"] == app]
                    )
                )
            if "claude" in apps:
                try:
                    ensure_sentry(homes["claude"], sys.executable)
                except (ValueError, OSError, subprocess.TimeoutExpired) as error:
                    issues.append(str(error))

    else:
        for app in apps:
            print(f"{app}: home {homes[app]}")
            if not (
                homes[app] / ("settings.json" if app == "claude" else "config.toml")
            ).is_file():
                issues.append(f"{app}: config missing; run refresh")
            try:
                found = installed(app, homes[app])
            except (ValueError, OSError, subprocess.TimeoutExpired) as error:
                issues.append(str(error))
                found = {}
            for p in plugins:
                if p["app"] == app:
                    status = "installed" if p["id"] in found else "missing"
                    print(
                        f"{app}: {p['id']} {status}, {p['kind']}, desired enabled={p['enabled']}, observed snapshot version={p['observed_version']}"
                    )
                    if status == "installed":
                        observed = found[p["id"]]
                        print(
                            f"{app}: {p['id']} observed enabled={observed.get('enabled')}, version={observed.get('version')}"
                        )
                        if observed.get("enabled") != p["enabled"]:
                            issues.append(
                                f"{app}: {p['id']} enablement differs; local settings retained"
                            )
                        if observed.get("version") != p["observed_version"]:
                            print(
                                f"{app}: {p['id']} version differs from snapshot; native versions are not pinned"
                            )
                    if status == "missing":
                        issues.append(
                            f"{app}: {p['id']} missing; "
                            + (
                                "run bootstrap"
                                if p["kind"] == "native"
                                else "open app and connect account or enable app-provided plugin"
                            )
                        )
            for asset in manifest["assets"]:
                if app in asset["apps"] and asset["destination"].startswith("skills/"):
                    available = (
                        homes[app] / asset["destination"] / "SKILL.md"
                    ).is_file()
                    print(
                        f"{app}: {asset['destination']} "
                        + ("available" if available else "missing")
                    )
                    if not available:
                        issues.append(
                            f"{app}: {asset['destination']} missing; run refresh or reconcile a local deletion"
                        )
        for name in ("EXA_API_KEY", "SENTRY_ACCESS_TOKEN"):
            print(f"{name}: " + ("present" if os.environ.get(name) else "missing"))
            if not os.environ.get(name):
                issues.append(f"{name} missing; configure per-machine authentication")
        if not shutil.which("npx"):
            issues.append("npx missing; Sentry MCP needs Node/npm")
    if args.operation in ("bootstrap", "doctor", "inventory"):
        print(
            "Third-party skills: follow SKILLS.md with npx skills; "
            "configuration refresh does not install or verify them"
        )
        for asset in manifest["assets"]:
            if not any(app in asset["apps"] for app in apps):
                continue
            for tool in asset.get("requires", []):
                if not shutil.which(tool):
                    issues.append(
                        f"{asset['destination']}: optional skill runtime missing {tool}; install it before using this skill"
                    )
        if args.operation == "bootstrap":
            for name in ("EXA_API_KEY", "SENTRY_ACCESS_TOKEN"):
                if not os.environ.get(name):
                    issues.append(
                        f"{name} missing; configure per-machine authentication"
                    )
            if not shutil.which("npx"):
                issues.append("npx missing; install Node/npm for Sentry MCP")
    for issue in issues:
        print(issue, file=sys.stderr)
    return 1 if issues and args.operation != "refresh" else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (
        ValueError,
        OSError,
        TypeError,
        KeyError,
        subprocess.TimeoutExpired,
    ) as error:
        print(
            "Setup failed: "
            + (
                str(error)
                if isinstance(error, ValueError)
                and not isinstance(error, json.JSONDecodeError)
                else type(error).__name__
            ),
            file=sys.stderr,
        )
        sys.exit(1)
