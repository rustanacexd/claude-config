# Recover an installation

Use this guide when refresh refuses to continue, or when upgrading an installation that used symlinks or vendored skills. Keep the app idle while reconciling interrupted writes.

## Keep runtime state private

Each app home owns `.claude-config/baseline.json`, `journal.json`, `lock` and `backups/`. Baselines, backups and journals can contain private local settings; keep the app home private. Python applies private file modes on POSIX. Windows inherits the app-home ACL; choose a private user directory. Runtime state is never stored beside the tracked templates.

## Preserve local files

Each custom skill owns its listed child files, not its entire directory. Unknown files and edited managed files remain local. Refresh retains local file deletions. When an upstream file disappears, refresh removes the installed file only if its recorded content still matches. Source directories include referenced scripts, examples and nested resources. Third-party skills installed by `npx skills` are outside this installer's ownership. If you installed an earlier version of this branch, refresh removes unchanged files from the former vendored skills and preserves edited or untracked files. Follow [SKILLS.md](../SKILLS.md) after that refresh to restore those skills through the upstream CLI.

## Resume interrupted publication

Publication uses an OS-backed lock, same-directory temporary files, atomic replacements, durable file writes, backups and a versioned journal. POSIX also syncs directories. Windows uses native byte-range locking and inherits filesystem durability guarantees for directory entries. Interrupted work resumes only if every file still matches its prior observation or intended output. If an app edited a file after interruption, refresh refuses to overwrite it. Preserve the journal and backups, compare its proposed output with the edited files, and reconcile while the app is idle before retrying. There is no automatic rollback over new app edits.

## Migrate legacy installations

Old configuration and instruction symlinks become regular local files without changing their targets. An old Codex baseline is imported only when its config link proves ownership by this clone. A legacy repo-side `.refresh.journal.json` causes refusal. Recover it with the previous installer before upgrading. A directory symlink at a listed asset root becomes an ordinary directory only when its target resolves to that asset in this clone. Refresh copies every source file and preserves empty subdirectories without writing through the link. It backs up the raw link target and journals the conversion before removing the link. Interrupted conversion resumes from the original link, an absent root, or a partial directory containing only the planned files and directories. Retargeted links, unexpected entries and edited files cause refusal. Other linked parents, foreign or broken directory links, and Windows junctions or other reparse-point directories below the app home are rejected.

After resolving the conflict, rerun refresh and [inspect the result](updating.md#inspect-the-result). Do not delete baselines, journals, or backups to force an overwrite.
