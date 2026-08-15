#!/usr/bin/env bash
# Claude Code status line — mirrors Starship prompt structure from ~/.config/starship.toml
# Reads JSON from stdin and outputs a formatted status line.

input=$(cat)

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // "."')
model=$(echo "$input" | jq -r '.model.display_name // "Claude"')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
ctx_size=$(echo "$input" | jq -r '.context_window.context_window_size // empty')
used_tokens=$(echo "$input" | jq -r '.context_window.total_input_tokens // empty')

# Auto-compact fires at this window, so it is the real ceiling, not the model's
# full context. Only ever shrinks: the env var cannot raise the model's limit.
if [[ -n "$CLAUDE_CODE_AUTO_COMPACT_WINDOW" && -n "$ctx_size" \
      && "$CLAUDE_CODE_AUTO_COMPACT_WINDOW" -lt "$ctx_size" ]]; then
  ctx_size=$CLAUDE_CODE_AUTO_COMPACT_WINDOW
  used_pct=   # was a percentage of the full window; recompute below
fi
vim_mode=$(echo "$input" | jq -r '.vim.mode // empty')
session_name=$(echo "$input" | jq -r '.session_name // empty')
effort=$(echo "$input" | jq -r '.effort.level // empty')
pr_number=$(echo "$input" | jq -r '.pr.number // empty')
pr_url=$(echo "$input" | jq -r '.pr.url // empty')

# --- Directory: shorten home to ~, truncate to last 3 components (starship truncation_length=3) ---
short_cwd="${cwd/#$HOME/\~}"
# Split on / and keep last 3 parts
IFS='/' read -ra _parts <<< "$short_cwd"
if (( ${#_parts[@]} > 3 )); then
  short_cwd=".../${_parts[-3]}/${_parts[-2]}/${_parts[-1]}"
fi

# --- Git info (skip optional lock so it never blocks) ---
git_branch=""
git_status_str=""
if git -C "$cwd" rev-parse --is-inside-work-tree --no-optional-locks >/dev/null 2>&1; then
  git_branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null \
    || git -C "$cwd" rev-parse --short HEAD 2>/dev/null)

  # Compute status markers matching starship.toml [git_status] symbols
  _ahead=$(git -C "$cwd" rev-list --no-optional-locks --count @{u}..HEAD 2>/dev/null || echo 0)
  _behind=$(git -C "$cwd" rev-list --no-optional-locks --count HEAD..@{u} 2>/dev/null || echo 0)
  _gs=""
  if git -C "$cwd" diff --no-optional-locks --quiet --cached 2>/dev/null; then :; else _gs="${_gs}+"; fi
  if git -C "$cwd" diff --no-optional-locks --quiet 2>/dev/null; then :; else _gs="${_gs}!"; fi
  if [[ -n $(git -C "$cwd" ls-files --others --exclude-standard 2>/dev/null) ]]; then _gs="${_gs}?"; fi
  if (( _ahead > 0 && _behind > 0 )); then _gs="${_gs}<>"; elif (( _ahead > 0 )); then _gs="${_gs}>"; elif (( _behind > 0 )); then _gs="${_gs}<"; fi
  [[ -n "$_gs" ]] && git_status_str="[$_gs]"
fi

# --- Assemble parts ---
parts=()

# Directory
parts+=("$(printf '\033[34m%s\033[0m' "$short_cwd")")

# Git branch + status (starship $git_branch + $git_status)
if [[ -n "$git_branch" ]]; then
  branch_str="git ${git_branch}"
  [[ -n "$git_status_str" ]] && branch_str="${branch_str} ${git_status_str}"
  parts+=("$(printf '\033[33m%s\033[0m' "$branch_str")")
fi

# Model, with reasoning effort beside it
model_str=$(printf '\033[35m%s\033[0m' "$model")
if [[ -n "$effort" ]]; then
  model_str="$model_str $(printf '\033[36m%s\033[0m' "$effort")"
fi
parts+=("$model_str")

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
  ctx_str="ctx $(humanize "$used_tokens")"
  if [[ -n "$ctx_size" && "$ctx_size" -gt 0 ]]; then
    ctx_str="${ctx_str}/$(humanize "$ctx_size")"
  fi
  parts+=("$(printf "${ctx_color}%s\033[0m" "$ctx_str")")
fi

# PR number as a clickable OSC 8 hyperlink
if [[ -n "$pr_number" && -n "$pr_url" ]]; then
  pr_link=$(printf '\033]8;;%s\033\\PR #%s\033]8;;\033\\' "$pr_url" "$pr_number")
  parts+=("$(printf '\033[96m%s\033[0m' "$pr_link")")
fi

# Session name
if [[ -n "$session_name" ]]; then
  parts+=("$(printf '\033[36m[%s]\033[0m' "$session_name")")
fi

# Vim mode
if [[ -n "$vim_mode" ]]; then
  parts+=("$(printf '\033[32m[%s]\033[0m' "$vim_mode")")
fi

printf '%s' "$(IFS=' | '; echo "${parts[*]}")"
