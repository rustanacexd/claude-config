"""Read-only checks for setup changes that have not reached the repository."""

from pathlib import Path
import shlex
import subprocess


def upstream_skills(repo):
    names = {"claude": set(), "codex": set()}
    for line in (repo / "SKILLS.md").read_text().splitlines():
        if not line.startswith("npx skills add "):
            continue
        words = shlex.split(line)
        if "--skill" not in words or "-a" not in words:
            raise ValueError("SKILLS.md installs must name --skill and -a explicitly")

        def values(flag):
            result = []
            for word in words[words.index(flag) + 1:]:
                if word.startswith("-"):
                    break
                result.append(word)
            return result

        selected = values("--skill")
        agents = values("-a")
        if not selected or not agents:
            raise ValueError("SKILLS.md install has no skills or agents")
        for agent in agents:
            if agent not in ("claude-code", "codex"):
                raise ValueError(f"Unsupported skill agent: {agent}")
            names["claude" if agent == "claude-code" else agent].update(selected)
    return names


def managed_skills(repo, manifest, app):
    return {
        Path(asset["destination"]).name: repo / asset["source"]
        for asset in manifest["assets"]
        if app in asset["apps"] and asset["destination"].startswith("skills/")
        and (repo / asset["source"] / "SKILL.md").is_file()
    }


def skill_files(directory):
    return {p.relative_to(directory): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()}


def check_local(repo, manifest, plugins, homes, agents, inventory):
    issues = []
    upstream = upstream_skills(repo)
    for app, home in homes.items():
        managed = managed_skills(repo, manifest, app)
        roots = [home / "skills"] + ([agents] if app == "codex" else [])
        seen = set()
        for root in roots:
            for entry in sorted(root.glob("*/SKILL.md")):
                skill = entry.parent
                if skill.name.startswith(".") or skill.resolve() in seen:
                    continue
                seen.add(skill.resolve())
                if skill.name in managed:
                    source = managed[skill.name]
                    if skill_files(skill) != skill_files(source):
                        issues.append(f"{app}: skill {skill.name} differs from "
                                      f"{source.relative_to(repo).as_posix()}; "
                                      "copy the intended edits into the repository")
                elif skill.name not in upstream[app]:
                    issues.append(f"{app}: skill {skill.name} is not recorded; "
                                  "add it to SKILLS.md or portable.json")
        declared = {p["id"]: p for p in plugins if p["app"] == app}
        for identifier, observed in sorted(inventory[app].items()):
            if any(note.get("type") == "synced-plugin-shadowed"
                   for note in observed.get("noteDetails", [])):
                continue
            if identifier not in declared:
                issues.append(f"{app}: plugin {identifier} is not recorded in plugins.json")
                continue
    return issues


def check_repository(repo, manifest):
    upstream_skills(repo)
    sources = [repo / asset["source"] for asset in manifest["assets"]]
    issues = []
    for root in (repo / "skills", repo / "codex/skills"):
        for skill in sorted(root.rglob("SKILL.md")):
            if not any(skill == source or skill.is_relative_to(source) for source in sources):
                issues.append(f"{skill.relative_to(repo).as_posix()} is not covered by portable.json")
    return issues


def check_committed(repo):
    result = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"],
                            capture_output=True, text=True, check=True)
    return ["Shared setup has uncommitted changes; commit them before pushing"] if result.stdout else []


def check_push_target(repo, updates):
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    for line in updates.splitlines():
        parts = line.split()
        if len(parts) != 4:
            raise ValueError("Invalid pre-push ref update")
        local_sha = parts[1]
        if set(local_sha) != {"0"} and local_sha != head:
            return ["Push the checked-out setup commit so the sync check covers the revision being pushed"]
    return []
