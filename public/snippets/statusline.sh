#!/bin/bash
# statusline.sh — Copilot CLI custom status line.
#
# Layout (segments joined by │):
#   📁 dir 🌿 branch │ ▰▰▱ ctx% │ tokens cache cost diff │ time │ Copilot v… │ effort yolo │ ✦ session
#
# Each section below owns one segment: it reads the already-extracted raw values
# and builds a formatted *_SEG string (sometimes empty). The final line just
# concatenates them. All payload fields are pulled up front in a single jq pass.

input=$(cat)

# ── Colors / styles ─────────────────────────────────────────────────────────
RST=$'\033[0m'; BLD=$'\033[1m'; DIM=$'\033[2m'
CYAN=$'\033[36m'; YEL=$'\033[33m'; GREEN=$'\033[32m'; RED=$'\033[31m'
DYEL=$'\033[2;33m'; LMAG=$'\033[2;95m'
LIBLUE=$'\033[38;5;39m'   # LinkedIn blue (~#0077B5)
SEP="${DIM}│${RST}"

# ── Extract every payload field in ONE jq pass ──────────────────────────────
# jq @sh shell-quotes each value so the eval is injection-safe; this replaces
# ~16 separate jq subprocesses. PCT is floored to an integer here (was a
# trailing `cut -d. -f1`). current_context_used_percentage tracks the live
# window; used_percentage is the last-call / max-window fallback.
eval "$(echo "$input" | jq -r '
  [ "CWD=\(.cwd // .workspace.current_dir // "" | @sh)",
    "SESSION=\(.session_name // "" | @sh)",
    "BRANCH=\(.worktree.branch // "" | @sh)",
    "VERSION=\(.version // "" | @sh)",
    "PCT=\((.context_window.current_context_used_percentage // .context_window.used_percentage // 0) | floor | tostring | @sh)",
    "IN=\(.context_window.total_input_tokens // 0 | tostring | @sh)",
    "OUT=\(.context_window.total_output_tokens // 0 | tostring | @sh)",
    "CACHE_READ=\(.context_window.total_cache_read_tokens // 0 | tostring | @sh)",
    "DUR_MS=\(.cost.total_duration_ms // 0 | tostring | @sh)",
    "API_MS=\(.cost.total_api_duration_ms // 0 | tostring | @sh)",
    "ADDED=\(.cost.total_lines_added // 0 | tostring | @sh)",
    "REMOVED=\(.cost.total_lines_removed // 0 | tostring | @sh)",
    "AIU=\(.ai_used.formatted // "0" | @sh)",
    "DISPLAY_NAME=\(.model.display_name // "" | @sh)"
  ] | .[]')"
DIR=$(basename "$CWD")

# ── Directory + git branch ──────────────────────────────────────────────────
# Branch comes from the payload when present; otherwise shell out to git. The
# dirty dot (●) needs git either way.
if [ -z "$BRANCH" ] && [ -n "$CWD" ]; then
  BRANCH=$(git -C "$CWD" rev-parse --abbrev-ref HEAD 2>/dev/null)
fi
GIT=""
if [ -n "$BRANCH" ]; then
  DIRTY=""
  [ -n "$(git -C "$CWD" status --porcelain 2>/dev/null)" ] && DIRTY=" ${YEL}●${RST}"
  GIT="  ${GREEN}🌿 ${BRANCH}${RST}${DIRTY}"
fi
DIR_SEG="${CYAN}📁 ${DIR}${RST}${GIT}"

# ── Context-window bar ──────────────────────────────────────────────────────
BAR_WIDTH=20
FILLED=$((PCT * BAR_WIDTH / 100))
EMPTY=$((BAR_WIDTH - FILLED))
BF='▰'; BE='▱'
BAR=$(printf "$BF%.0s" $(seq 1 $FILLED 2>/dev/null))$(printf "$BE%.0s" $(seq 1 $EMPTY 2>/dev/null))
if [ "$PCT" -ge 80 ]; then BC=$RED
elif [ "$PCT" -ge 50 ]; then BC=$YEL
else BC=$GREEN; fi
CONTEXT_SEG="  ${SEP}  ${BC}${BAR} ${PCT}%${RST}"

# ── Token / cache / cost / diff info ────────────────────────────────────────
TOKENS=$(awk "BEGIN{printf \"%.1fk\", ($IN+$OUT)/1000}")

# Cache hit %: cache reads as a share of total input. total_input_tokens already
# includes the cache-read and cache-write tokens (the API reports input as
# uncached + cache_read + cache_write), so the denominator is just IN — adding
# the cache fields again would double-count and roughly halve the real rate.
CACHE=""
if [ "$IN" -gt 0 ]; then
  HIT=$((CACHE_READ * 100 / IN))
  [ "$HIT" -gt 100 ] && HIT=100
  CACHE="  ${DYEL}cache:${HIT}%${RST}"
fi

# Cost slot: prefer AIU when nonzero, else fall back to API time (free/internal).
COST_PART=""
if [ "$AIU" != "0" ]; then
  COST_PART="  ${DYEL}aiu:${AIU}${RST}"
elif [ "$API_MS" -gt 0 ]; then
  API_S=$((API_MS / 1000))
  if [ "$API_S" -ge 60 ]; then API_FMT="$((API_S/60))m$((API_S%60))s"; else API_FMT="${API_S}s"; fi
  COST_PART="  ${DYEL}api:${API_FMT}${RST}"
fi

# Line-change badge, only when nonzero.
DIFF_PART=""
if [ "$ADDED" -gt 0 ] || [ "$REMOVED" -gt 0 ]; then
  DIFF_PART="  ${DIM}+${ADDED}/-${REMOVED}${RST}"
fi
INFO_SEG="  ${SEP}  ${DYEL}tokens:${TOKENS}${RST}${CACHE}${COST_PART}${DIFF_PART}"

# ── Elapsed session time ────────────────────────────────────────────────────
TOTAL_S=$((DUR_MS / 1000))
TIME=""
[ $((TOTAL_S / 604800)) -gt 0 ] && TIME+="$((TOTAL_S / 604800))w "
[ $(((TOTAL_S % 604800) / 86400)) -gt 0 ] && TIME+="$(((TOTAL_S % 604800) / 86400))d "
[ $(((TOTAL_S % 86400) / 3600)) -gt 0 ] && TIME+="$(((TOTAL_S % 86400) / 3600))h "
[ $(((TOTAL_S % 3600) / 60)) -gt 0 ] && TIME+="$(((TOTAL_S % 3600) / 60))m "
TIME+="$((TOTAL_S % 60))s"
TIME_SEG="  ${SEP}  ${DIM}${TIME}${RST}"

# ── Version ─────────────────────────────────────────────────────────────────
VERSION_SEG="  ${SEP}  ${DIM}Copilot v${VERSION:-?}${RST}"

# ── Reasoning effort + YOLO emoji ───────────────────────────────────────────
# Effort lives in model.display_name (e.g. "claude-opus-4.8 · xhigh · 1M
# context"), the same string the footer shows; take the "·"-delimited segment
# matching a known level and map it to a brainpower-ramp emoji. Absent token
# (non-reasoning model) → no icon.
EFFORT=$(echo "$DISPLAY_NAME" | tr '·' '\n' \
  | sed -E 's/^[[:space:]]+|[[:space:]]+$//g' \
  | grep -ixE 'none|low|medium|high|xhigh|max' | head -1 | tr 'A-Z' 'a-z')
case "$EFFORT" in
  none)   EFFORT_ICON="😴" ;;
  low)    EFFORT_ICON="☹️" ;;
  medium) EFFORT_ICON="😐" ;;
  high)   EFFORT_ICON="🙂" ;;
  xhigh)  EFFORT_ICON="😃" ;;
  max)    EFFORT_ICON="🤯" ;;
  *)      EFFORT_ICON="" ;;
esac
EFFORT_PART=""
[ -n "$EFFORT_ICON" ] && EFFORT_PART="${EFFORT_ICON} "

# YOLO / permission indicator — read from the parent copilot process's launch
# args (the payload carries no permission state) and the COPILOT_ALLOW_ALL env
# var. Full bypass → 💣; partial grants → a yellow ⚠️ listing which.
PARENT_ARGS=$(ps -o args= -p "$PPID" 2>/dev/null)
HAS_TOOLS=0; HAS_PATHS=0; HAS_URLS=0
[[ "$PARENT_ARGS" == *" --allow-all-tools"* || -n "$COPILOT_ALLOW_ALL" ]] && HAS_TOOLS=1
[[ "$PARENT_ARGS" == *" --allow-all-paths"* ]] && HAS_PATHS=1
[[ "$PARENT_ARGS" == *" --allow-all-urls"*  ]] && HAS_URLS=1
YOLO=""
if [[ "$PARENT_ARGS" == *" --yolo"* || "$PARENT_ARGS" == *" --allow-all"* ]] \
   || { [ "$HAS_TOOLS" = 1 ] && [ "$HAS_PATHS" = 1 ] && [ "$HAS_URLS" = 1 ]; }; then
  YOLO="💣 "
elif [ "$HAS_TOOLS" = 1 ] || [ "$HAS_PATHS" = 1 ] || [ "$HAS_URLS" = 1 ]; then
  parts=""
  [ "$HAS_TOOLS" = 1 ] && parts+="tools "
  [ "$HAS_PATHS" = 1 ] && parts+="paths "
  [ "$HAS_URLS" = 1 ]  && parts+="urls "
  YOLO="${YEL}⚠️ (${parts% })${RST} "
fi
EMOJI_SEG=""
[ -n "${EFFORT_PART}${YOLO}" ] && EMOJI_SEG="  ${SEP}  ${EFFORT_PART}${YOLO}"

# ── Session name ────────────────────────────────────────────────────────────
SESSION_SEG=""
[ -n "$SESSION" ] && SESSION_SEG="  ${SEP}  ${LIBLUE}✦ ${SESSION}${RST}"

# ── Terminal tab/window title (session name, else directory) ────────────────
# OSC 2 = window title, OSC 1 = tab/icon title — emit both for broad support.
TITLE="${SESSION:-$DIR}"
[ -n "$TITLE" ] && printf '\033]2;%s\007\033]1;%s\007' "$TITLE" "$TITLE" > /dev/tty 2>/dev/null

# ── Assemble ────────────────────────────────────────────────────────────────
echo "${DIR_SEG}${CONTEXT_SEG}${INFO_SEG}${TIME_SEG}${VERSION_SEG}${EMOJI_SEG}${SESSION_SEG}"
