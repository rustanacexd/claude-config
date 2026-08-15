#!/bin/sh
# Sync ~/.claude with this repo. Run from anywhere. Safe to run twice.
set -e
REPO=$(cd "$(dirname "$0")" && pwd)
DEST=~/.claude
mkdir -p "$DEST/output-styles" "$DEST/skills"

link() { # $1 = path relative to repo root
  src="$REPO/$1"
  dst="$DEST/$1"
  [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ] && return
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    mv "$dst" "$src"          # real file in ~/.claude wins: adopt it
    echo "adopted $1"
  fi
  rm -f "$dst"
  ln -s "$src" "$dst"
  echo "linked  $1"
}

# Adopt any new output style Claude Code wrote into ~/.claude
for f in "$DEST"/output-styles/*.md; do
  [ -e "$f" ] || continue
  link "output-styles/$(basename "$f")"
done

# Skill folders: repo side only. Never sweep ~/.claude/skills for adoption --
# it holds plugin symlinks and local-only skills that must stay out of the repo.
for d in "$REPO"/skills/*/; do
  [ -d "$d" ] || continue
  link "skills/$(basename "$d")"
done

link settings.json
link CLAUDE.md
link statusline.sh
for f in "$REPO"/output-styles/*.md; do
  [ -e "$f" ] || continue
  link "output-styles/$(basename "$f")"
done

# Drop links into this repo whose target is gone. Scoped to $REPO targets so
# plugin symlinks and local-only skills in ~/.claude are never touched.
for l in "$DEST"/* "$DEST"/output-styles/* "$DEST"/skills/*; do
  if [ -L "$l" ] && [ ! -e "$l" ]; then
    case "$(readlink "$l")" in
      "$REPO"/*) rm "$l"; echo "pruned  ${l#$DEST/}" ;;
    esac
  fi
done

git -C "$REPO" status --short
