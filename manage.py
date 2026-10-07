#!/usr/bin/env python3
"""Portable Claude/Codex setup. Requires Python 3.11 or newer."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
from portable.manage import load, refresh, relative
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
        choices=["bootstrap", "refresh", "doctor", "inventory", "skills-update"],
    )
    parser.add_argument("name", nargs="?")
    parser.add_argument("--app", choices=["claude", "codex", "all"], default="all")
    parser.add_argument(
        "--home",
        type=Path,
        help="Isolated root containing claude and codex homes; selected single app uses this path directly",
    )
    parser.add_argument("--install-tools", action="store_true")
    parser.add_argument(
        "--ref", help="Full upstream commit SHA for reviewed skill update"
    )
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
    if args.operation == "skills-update":
        if (
            not args.name
            or not args.ref
            or len(args.ref) != 40
            or any(c not in "0123456789abcdef" for c in args.ref)
        ):
            raise ValueError(
                "skills-update requires NAME and --ref full lowercase commit SHA"
            )
        sources_path = REPO / "skills/vendor/sources.json"
        sources = json.loads(sources_path.read_text())
        entry = next((x for x in sources if x["name"] == args.name), None)
        if entry is None or not entry.get("source", {}).get("sourceUrl"):
            raise ValueError(
                "Skill lacks known upstream; supply reviewed provenance before updating"
            )
        source = entry["source"]
        url = source["sourceUrl"]
        path = relative(str(Path(source["skillPath"]).parent).replace("\\", "/"))
        if not url.startswith("https://github.com/") or "@" in url:
            raise ValueError("Unsupported skill source")
        with tempfile.TemporaryDirectory() as temporary:
            checkout = Path(temporary) / "checkout"
            for argv in (
                ["git", "clone", "--no-checkout", url, str(checkout)],
                ["git", "-C", str(checkout), "checkout", "--detach", args.ref],
            ):
                result = subprocess.run(argv, capture_output=True)
                if result.returncode:
                    raise ValueError("Upstream checkout failed; no snapshot changed")
            snapshot = checkout / path
            if not (snapshot / "SKILL.md").is_file() or any(
                p.is_symlink() for p in snapshot.rglob("*")
            ):
                raise ValueError("Invalid upstream snapshot")
            target = REPO / "skills/vendor" / args.name
            candidate = Path(temporary) / "candidate"
            shutil.copytree(snapshot, candidate)
            for notice in ("LICENSE", "LICENSE.md", "LICENSE.txt", "NOTICE"):
                if (checkout / notice).is_file():
                    shutil.copy2(checkout / notice, candidate / notice)
            entry["revision"] = args.ref
            import hashlib

            digest = hashlib.sha256()
            for p in sorted(candidate.rglob("*")):
                if p.is_file():
                    digest.update(
                        p.relative_to(candidate).as_posix().encode()
                        + b"\0"
                        + p.read_bytes()
                    )
            entry["snapshot_sha256"] = digest.hexdigest()
            entry["files"] = sum(p.is_file() for p in candidate.rglob("*"))
            previous = target.with_name(target.name + ".previous")
            if previous.exists():
                raise ValueError(
                    "Previous skill update backup exists; reconcile before retrying"
                )
            staged = target.with_name(target.name + ".staged")
            if staged.exists():
                raise ValueError(
                    "Skill staging directory exists; reconcile before retrying"
                )
            shutil.copytree(candidate, staged)
            target.rename(previous)
            try:
                staged.rename(target)
                from portable.install import atomic

                atomic(sources_path, (json.dumps(sources, indent=2) + "\n").encode())
            except BaseException:
                if target.exists():
                    shutil.rmtree(target)
                previous.rename(target)
                raise
            shutil.rmtree(previous)
        print("Updated reviewed snapshot; inspect git diff before committing")
        return 0
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
                    print(
                        f"{app}: {asset['destination']} "
                        + (
                            "available"
                            if (
                                homes[app] / asset["destination"] / "SKILL.md"
                            ).is_file()
                            else "missing"
                        )
                    )
        for name in ("EXA_API_KEY", "SENTRY_ACCESS_TOKEN"):
            print(f"{name}: " + ("present" if os.environ.get(name) else "missing"))
            if not os.environ.get(name):
                issues.append(f"{name} missing; configure per-machine authentication")
        if not shutil.which("npx"):
            issues.append("npx missing; Sentry MCP needs Node/npm")
    if args.operation in ("bootstrap", "doctor", "inventory"):
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
