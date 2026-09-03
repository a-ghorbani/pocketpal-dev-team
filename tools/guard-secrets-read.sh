#!/bin/bash
# PreToolUse hook: blocks reads of secret files (.env, .env.*, *.keystore).
#
# Replaces Read(...) deny rules, whose presence makes the harness prompt on
# every `cd X && <read> relative/path` because it cannot resolve the path.
#
# Exit code 2 = block the operation
# Exit code 0 = allow the operation

INPUT=$(cat)
exec >&2

TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

SECRET_PATH='(^|/)(\.env(\.[A-Za-z0-9_.-]+)?|[^/]*\.keystore)$'
SECRET_IN_COMMAND='(^|[[:space:]/=:'"'"'"(])(\.env(\.[A-Za-z0-9_.-]+)?|[A-Za-z0-9_.-]*\.keystore)([[:space:]'"'"'");|&>]|$)'

block() {
    echo "BLOCKED: $1"
    echo ""
    echo "Secret files (.env, .env.*, *.keystore) are never read by agents."
    echo "Config reaches worktrees only through ./tools/sync-worktree-config.sh."
    exit 2
}

case "$TOOL" in
    Bash)
        if [[ -n "$COMMAND" ]] && echo "$COMMAND" | grep -qE "$SECRET_IN_COMMAND"; then
            block "Command references a secret file."
        fi
        ;;
    *)
        if [[ -n "$FILE_PATH" ]] && echo "$FILE_PATH" | grep -qE "$SECRET_PATH"; then
            block "Cannot read $FILE_PATH."
        fi
        ;;
esac

exit 0
