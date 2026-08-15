#!/usr/bin/env bash
# Claude Code status line — mirrors Starship prompt structure from ~/.config/starship.toml
# Reads JSON from stdin and outputs a formatted status line.
#
# Renders on every turn, so it avoids forking: one jq for all fields, `printf -v`
# instead of $(printf ...), and no subprocess that isn't earning its keep.

IFS= read -rd '' input

# One jq, one field per line. Every field MUST use `// ""` and not `// empty`:
# empty emits no line at all, which silently shifts every later read up by one.
{
  IFS= read -r cwd
  IFS= read -r model
  IFS= read -r used_pct
  IFS= read -r ctx_size
  IFS= read -r used_tokens
  IFS= read -r vim_mode
  IFS= read -r session_name
  IFS= read -r effort
  IFS= read -r pr_number
  IFS= read -r pr_url
} <<<"$(jq -r '
  (.workspace.current_dir // .cwd // "."),
  (.model.display_name // "Claude"),
  (.context_window.used_percentage // ""),
  (.context_window.context_window_size // ""),
  (.context_window.total_input_tokens // ""),
  (.vim.mode // ""),
  (.session_name // ""),
  (.effort.level // ""),
  (.pr.number // ""),
  (.pr.url // "")
' <<<"$input")"

model=${model%% (*}   # drop the context-size note: "Opus 5 (1M context)" -> "Opus 5"

# Auto-compact fires at this window, so it is the real ceiling, not the model's
# full context. Only ever shrinks: the env var cannot raise the model's limit.
if [[ -n "$CLAUDE_CODE_AUTO_COMPACT_WINDOW" && -n "$ctx_size" \
      && "$CLAUDE_CODE_AUTO_COMPACT_WINDOW" -lt "$ctx_size" ]]; then
  ctx_size=$CLAUDE_CODE_AUTO_COMPACT_WINDOW
  used_pct=   # was a percentage of the full window; recompute below
fi

# --- Directory: shorten home to ~, keep last 3 components (starship truncation_length=3) ---
_tilde='~'   # via a variable: bash 3.2 leaves the backslash in a literal \~
short_cwd="${cwd/#$HOME/$_tilde}"
IFS='/' read -ra _parts <<< "$short_cwd"
_n=${#_parts[@]}
# Positive indices only: negative subscripts need bash 4.3 and macOS ships 3.2.
if (( _n > 3 )); then
  short_cwd=".../${_parts[_n-3]}/${_parts[_n-2]}/${_parts[_n-1]}"
fi

# --- Git branch (skip optional lock so it never blocks) ---
# No is-inside-work-tree gate: outside a repo both commands fail and this stays empty.
git_branch=$(git --no-optional-locks -C "$cwd" symbolic-ref --short HEAD 2>/dev/null \
  || git --no-optional-locks -C "$cwd" rev-parse --short HEAD 2>/dev/null)

# --- Assemble parts ---
parts=()

# Directory
printf -v _p '\033[34m%s\033[0m' "$short_cwd"
parts+=("$_p")

# Git branch
if [[ -n "$git_branch" ]]; then
  printf -v _p '\033[33m%s\033[0m' "$git_branch"
  parts+=("$_p")
fi

# Model, with reasoning effort beside it
printf -v _p '\033[35m%s\033[0m' "$model"
if [[ -n "$effort" ]]; then
  printf -v _e '\033[36m%s\033[0m' "$effort"
  _p="$_p $_e"
fi
parts+=("$_p")

# Context usage in tokens (color-coded: green < 50%, yellow < 80%, red >= 80%)
if [[ -n "$used_tokens" ]]; then
  # Percentage is only used to pick the color, not displayed
  if [[ -n "$used_pct" ]]; then
    used_int=${used_pct%.*}
  elif [[ -n "$ctx_size" && "$ctx_size" -gt 0 ]]; then
    used_int=$(( used_tokens * 100 / ctx_size ))
  else
    used_int=0
  fi
  if (( used_int >= 80 )); then
    ctx_color='\033[31m'
  elif (( used_int >= 50 )); then
    ctx_color='\033[33m'
  else
    ctx_color='\033[32m'
  fi

  # Humanize: 45200 -> 45.2k, 1200000 -> 1.2M
  humanize() {
    awk -v n="$1" 'BEGIN {
      if (n >= 1000000) { v = n/1000000; s = "M" }
      else if (n >= 1000) { v = n/1000; s = "k" }
      else { printf "%d", n; exit }
      out = sprintf("%.1f", v);
      sub(/\.0$/, "", out);
      printf "%s%s", out, s;
    }'
  }
  ctx_str="$(humanize "$used_tokens")"
  if [[ -n "$ctx_size" && "$ctx_size" -gt 0 ]]; then
    ctx_str="${ctx_str}/$(humanize "$ctx_size")"
  fi
  printf -v _p "${ctx_color}%s\033[0m" "$ctx_str"
  parts+=("$_p")
fi

# PR number as a clickable OSC 8 hyperlink
if [[ -n "$pr_number" && -n "$pr_url" ]]; then
  printf -v _link '\033]8;;%s\033\\PR #%s\033]8;;\033\\' "$pr_url" "$pr_number"
  printf -v _p '\033[96m%s\033[0m' "$_link"
  parts+=("$_p")
fi

# Session name
if [[ -n "$session_name" ]]; then
  printf -v _p '\033[90m[%s]\033[0m' "$session_name"
  parts+=("$_p")
fi

# Vim mode
if [[ -n "$vim_mode" ]]; then
  printf -v _p '\033[32m[%s]\033[0m' "$vim_mode"
  parts+=("$_p")
fi

IFS=' '
printf '%s' "${parts[*]}"
