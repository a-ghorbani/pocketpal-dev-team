#!/bin/bash
# PreToolUse hook: blocks git commits to main/master AND inside repos/pocketpal-ai
#
# Exit code 2 = block the operation
# Exit code 0 = allow the operation

# Read hook input from stdin
INPUT=$(cat)
exec >&2
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Only git commit invocations are subject to the checks below
if ! echo "$COMMAND" | grep -qE 'git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+commit\b'; then
    exit 0
fi

GIT_C_DIR=$(echo "$COMMAND" | sed -nE 's/.*git[[:space:]]+-C[[:space:]]+([^[:space:]]+)[[:space:]]+commit([[:space:]].*)?$/\1/p')
if [[ -n "$GIT_C_DIR" ]]; then
    CWD=$(cd "$CWD" 2>/dev/null && cd "$GIT_C_DIR" 2>/dev/null && pwd)
fi

# Check 1: Block commits when CWD is inside repos/pocketpal-ai
if [[ "$CWD" == *"/repos/pocketpal-ai"* ]]; then
    echo "BLOCKED: Cannot commit inside repos/pocketpal-ai/"
    echo ""
    echo "This directory is the shared reference for all worktrees."
    echo "Multiple agents depend on it being untouched."
    echo ""
    echo "Work in a worktree instead: ./worktrees/TASK-YYYYMMDD-HHMM"
    exit 2
fi

# Check 2: Block commits to main/master branch — only inside worktrees
# The dev-team root legitimately commits to main (story updates, settings, etc.)
# But worktrees should always be on a feature branch.
if [[ "$CWD" == *"/worktrees/"* ]]; then
    CURRENT_BRANCH=$(git -C "$CWD" branch --show-current 2>/dev/null)
    if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
        echo "BLOCKED: Cannot commit directly to '$CURRENT_BRANCH' branch."
        echo "Please work on a feature branch in a worktree."
        exit 2
    fi
fi

# Check 3: Also check the command itself for cd-into-submodule patterns
if echo "$COMMAND" | grep -qE '(cd|pushd)\s+[^\s;|&]*repos/pocketpal-ai'; then
    echo "BLOCKED: Cannot commit inside repos/pocketpal-ai/"
    echo ""
    echo "This directory is the shared reference for all worktrees."
    echo "Work in a worktree instead: ./worktrees/TASK-YYYYMMDD-HHMM"
    exit 2
fi

# Check 4: Block commits with Co-Authored-By trailer
# PocketPal Dev Team uses its own signature, not individual AI model attribution
if echo "$COMMAND" | grep -qi 'Co-Authored-By'; then
    echo "BLOCKED: Do not add 'Co-Authored-By' trailer to commits."
    echo ""
    echo "PocketPal Dev Team does not use individual AI model attribution."
    echo "Remove the Co-Authored-By line from your commit message."
    exit 2
fi

# Allow the commit
exit 0
