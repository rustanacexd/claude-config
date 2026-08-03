#!/bin/sh
# Sync ~/.claude with this repo. Run from anywhere. Safe to run twice.
set -e
REPO=$(cd "$(dirname "$0")" && pwd)
DEST=~/.claude
mkdir -p "$DEST/output-styles"

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

link settings.json
link CLAUDE.md
link statusline-command.sh
for f in "$REPO"/output-styles/*.md; do
  [ -e "$f" ] || continue
  link "output-styles/$(basename "$f")"
done

git -C "$REPO" status --short
