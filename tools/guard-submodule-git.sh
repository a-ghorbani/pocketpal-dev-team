#!/bin/bash
# PreToolUse hook: blocks mutating git commands in repos/pocketpal-ai/
# This directory is the shared reference for all worktrees and MUST be read-only.
#
# Runs on every Bash command — fast-exits for irrelevant commands.
#
# Exit code 2 = block the operation
# Exit code 0 = allow the operation

INPUT=$(cat)
exec >&2

# Quick exit: if the input doesn't mention repos/pocketpal-ai at all, allow immediately.
# This makes the 99% case (commands unrelated to the submodule) cost nearly zero.
case "$INPUT" in
    *repos/pocketpal-ai*) ;;
    *) exit 0 ;;
esac

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

if [[ -z "$COMMAND" ]]; then
    exit 0
fi

# --- Allowlist: always permit these git subcommands in repos/pocketpal-ai ---
# git worktree (orchestrator MUST run this from repos/pocketpal-ai)
# git log, diff, status, show, remote, fetch, rev-parse, describe, tag, blame, shortlog
# git branch (without -d/-D/-m/-M — listing is fine)
# git config --get/--list

# --- Helper: check if a command string contains a mutating git subcommand ---
contains_mutating_git() {
    echo "$1" | grep -qE 'git\s+(commit|checkout|switch|merge|pull|push|add|reset|rebase|cherry-pick|revert|clean|stash|rm|mv)\b'
}

contains_branch_delete() {
    echo "$1" | grep -qE 'git\s+branch\s+.*-[dDmM]\b'
}

block_with_message() {
    echo "BLOCKED: Cannot run mutating git commands in repos/pocketpal-ai/"
    echo ""
    echo "This directory is the shared reference for all worktrees."
    echo "Multiple agents depend on it being untouched."
    echo ""
    echo "Work in a worktree instead: ./worktrees/TASK-YYYYMMDD-HHMM"
    echo "Use pocketpal-orchestrator to create one automatically."
    echo ""
    echo "Blocked command: $1"
    exit 2
}

# Check 1: CWD is inside repos/pocketpal-ai
if [[ "$CWD" == *"/repos/pocketpal-ai"* ]]; then
    if contains_mutating_git "$COMMAND" || contains_branch_delete "$COMMAND"; then
        block_with_message "$COMMAND"
    fi
fi

# Check 2: Command explicitly cd's into repos/pocketpal-ai and runs git mutations
if echo "$COMMAND" | grep -qE '(cd|pushd)\s+[^\s;|&]*repos/pocketpal-ai'; then
    if contains_mutating_git "$COMMAND" || contains_branch_delete "$COMMAND"; then
        block_with_message "$COMMAND"
    fi
fi

# Check 3: Command uses git -C to target repos/pocketpal-ai
if echo "$COMMAND" | grep -qE 'git\s+-C\s+[^\s]*repos/pocketpal-ai'; then
    if contains_mutating_git "$COMMAND" || contains_branch_delete "$COMMAND"; then
        block_with_message "$COMMAND"
    fi
fi

exit 0
