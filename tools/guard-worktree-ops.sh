#!/usr/bin/env bash

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)

if [[ -z "$COMMAND" ]]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_TEAM_ROOT="$(dirname "$SCRIPT_DIR")"
SUBMODULE_ROOT="${DEV_TEAM_ROOT}/repos/pocketpal-ai"
WORKTREES_ROOT="${DEV_TEAM_ROOT}/worktrees"

block() {
  echo "BLOCKED: $1"
  exit 2
}

if echo "$COMMAND" | grep -qE 'git[[:space:]]+worktree[[:space:]]+(remove|prune)\b'; then
  block "Do not use raw git worktree remove/prune. Use ./tools/remove-worktree.sh <name> --yes."
fi

if echo "$COMMAND" | grep -qE '(^|[;&|][[:space:]]*)(rm|rmdir)\b[^[:cntrl:]]*worktrees/'; then
  block "Do not delete worktree directories directly. Use ./tools/remove-worktree.sh <name> --yes."
fi

if ! echo "$COMMAND" | grep -qE 'git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+worktree[[:space:]]+add\b'; then
  exit 0
fi

WORKTREE_REL=""
GIT_C_DIR=""
read -r -a TOKENS <<< "$COMMAND"
for ((i = 0; i < ${#TOKENS[@]}; i++)); do
  if [[ "${TOKENS[$i]}" != "git" ]]; then
    continue
  fi

  j=$((i + 1))
  if [[ "${TOKENS[$j]:-}" == "-C" ]]; then
    GIT_C_DIR="${TOKENS[$((j + 1))]:-}"
    j=$((j + 2))
  fi

  if [[ "${TOKENS[$j]:-}" != "worktree" || "${TOKENS[$((j + 1))]:-}" != "add" ]]; then
    continue
  fi

  k=$((j + 2))
  if [[ "${TOKENS[$k]:-}" == "--detach" ]]; then
    k=$((k + 1))
  fi

  WORKTREE_REL="${TOKENS[$k]:-}"
  break
done

if [[ -z "$WORKTREE_REL" ]]; then
  block "Could not validate git worktree add target. Use ./tools/create-worktree.sh."
fi

BASE_DIR="$CWD"
CD_PREFIX="$(echo "$COMMAND" | sed -n 's/^cd[[:space:]]\+\([^[:space:]]\+\)[[:space:]]*&&.*/\1/p')"
if [[ -n "$CD_PREFIX" && -n "$BASE_DIR" ]]; then
  BASE_DIR="$(cd "$BASE_DIR" && cd "$CD_PREFIX" 2>/dev/null && pwd)"
fi

if [[ -n "$GIT_C_DIR" && -n "$BASE_DIR" ]]; then
  BASE_DIR="$(cd "$BASE_DIR" && cd "$GIT_C_DIR" 2>/dev/null && pwd)"
fi

if [[ -z "$BASE_DIR" ]]; then
  block "Could not resolve git worktree add base directory. Use ./tools/create-worktree.sh."
fi

case "${BASE_DIR}/" in
  "${SUBMODULE_ROOT}/"*) ;;
  *)
    block "git worktree add must run against repos/pocketpal-ai, not the dev-team repo."
    ;;
esac

WORKTREE_DIR="$(dirname "$WORKTREE_REL")"
WORKTREE_NAME="$(basename "$WORKTREE_REL")"
WORKTREE_PARENT="$(cd "$BASE_DIR" && cd "$WORKTREE_DIR" 2>/dev/null && pwd)"

if [[ -z "$WORKTREE_PARENT" || -z "$WORKTREE_NAME" ]]; then
  block "Could not resolve worktree target path. Use ./tools/create-worktree.sh."
fi

WORKTREE_ABS="${WORKTREE_PARENT}/${WORKTREE_NAME}"
case "${WORKTREE_ABS}/" in
  "${WORKTREES_ROOT}/"*) ;;
  *)
    block "git worktree add targets must live under ${WORKTREES_ROOT}."
    ;;
esac

exit 0
