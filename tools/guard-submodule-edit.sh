#!/bin/bash
# PreToolUse hook: blocks Edit/Write operations targeting repos/pocketpal-ai/
# This directory is the shared reference for all worktrees and MUST be read-only.
#
# Exit code 2 = block the operation
# Exit code 0 = allow the operation

INPUT=$(cat)
exec >&2
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Block if file path is inside repos/pocketpal-ai
if [[ "$FILE_PATH" == *"/repos/pocketpal-ai/"* ]] || [[ "$FILE_PATH" == *"/repos/pocketpal-ai" ]]; then
    echo "BLOCKED: Cannot modify files in repos/pocketpal-ai/ directly."
    echo ""
    echo "This directory is the shared reference for all worktrees."
    echo "Multiple agents depend on it being untouched."
    echo ""
    echo "Work in a worktree instead: ./worktrees/TASK-YYYYMMDD-HHMM"
    echo "Use pocketpal-orchestrator to create one automatically."
    exit 2
fi

exit 0
