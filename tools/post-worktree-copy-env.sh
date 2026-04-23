#!/bin/bash
# PostToolUse hook: copies gitignored env/config files into newly created worktrees
#
# Triggers after any Bash call containing "git worktree add"
# Idempotent — safe to run multiple times
#
# Exit code 0 = success (post hooks don't block)

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Only act on git worktree add commands
if ! echo "$COMMAND" | grep -qE 'git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+worktree[[:space:]]+add\b'; then
    exit 0
fi

# Extract the worktree path from the command.
# Handles both:
#   git worktree add <path> ...
#   git worktree add --detach <path> ...
WORKTREE_REL=""
GIT_C_DIR=""
read -r -a TOKENS <<< "$COMMAND"
for ((i = 0; i < ${#TOKENS[@]}; i++)); do
    if [ "${TOKENS[$i]}" != "git" ]; then
        continue
    fi

    IDX=$((i + 1))
    if [ "${TOKENS[$IDX]:-}" = "-C" ]; then
        GIT_C_DIR="${TOKENS[$((IDX + 1))]:-}"
        IDX=$((IDX + 2))
    fi

    if [ "${TOKENS[$IDX]:-}" != "worktree" ] || [ "${TOKENS[$((IDX + 1))]:-}" != "add" ]; then
        continue
    fi

    IDX=$((IDX + 2))
    if [ "${TOKENS[$IDX]:-}" = "--detach" ]; then
        IDX=$((IDX + 1))
    fi

    WORKTREE_REL="${TOKENS[$IDX]:-}"
    break
done

if [ -z "$WORKTREE_REL" ]; then
    exit 0
fi

# Resolve to absolute path
# The command runs from repos/pocketpal-ai, so resolve relative to that
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_TEAM_ROOT="$(dirname "$SCRIPT_DIR")"
MAIN_REPO="${DEV_TEAM_ROOT}/repos/pocketpal-ai"

# Resolve worktree path (could be relative like ../../worktrees/TASK-xxx)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)

# If the command has a "cd <dir> &&" prefix, adjust CWD accordingly
CD_PREFIX=$(echo "$COMMAND" | sed -n 's/^cd  *\([^ ]*\)  *&&.*/\1/p')
if [ -n "$CD_PREFIX" ] && [ -n "$CWD" ]; then
    EFFECTIVE_CWD=$(cd "$CWD" && cd "$CD_PREFIX" 2>/dev/null && pwd)
    if [ -n "$EFFECTIVE_CWD" ]; then
        CWD="$EFFECTIVE_CWD"
    fi
fi

if [ -n "$GIT_C_DIR" ] && [ -n "$CWD" ]; then
    EFFECTIVE_CWD=$(cd "$CWD" && cd "$GIT_C_DIR" 2>/dev/null && pwd)
    if [ -n "$EFFECTIVE_CWD" ]; then
        CWD="$EFFECTIVE_CWD"
    fi
fi

if [ -n "$CWD" ]; then
    WORKTREE_ABS=$(cd "$CWD" && realpath "$WORKTREE_REL" 2>/dev/null)
else
    WORKTREE_ABS=$(cd "$MAIN_REPO" && realpath "$WORKTREE_REL" 2>/dev/null)
fi

if [ -z "$WORKTREE_ABS" ] || [ ! -d "$WORKTREE_ABS" ]; then
    exit 0
fi

echo ""
echo "Syncing allowlisted env/config files to worktree..."
"${SCRIPT_DIR}/sync-worktree-config.sh" "${WORKTREE_ABS}"
