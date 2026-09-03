#!/bin/bash
# PreToolUse hook: blocks reads of secret files (.env, .env.*, *.keystore,
# *.pem, and the GitHub App token cache gh-app-token.json).
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

SECRET_PATH='(^|/)(\.env(\.[A-Za-z0-9_.-]+)?|[^/]*\.keystore|[^/]*\.pem|gh-app-token\.json)$'
SECRET_IN_COMMAND='(^|[[:space:]/=:'"'"'"(])(\.env(\.[A-Za-z0-9_.-]+)?|[A-Za-z0-9_.-]*\.keystore|[A-Za-z0-9_.*-]*\.pem|gh-app-token\.json)([[:space:]'"'"'");|&>]|$)'

block() {
    echo "BLOCKED: $1"
    echo ""
    echo "Secret files (.env, .env.*, *.keystore, *.pem, gh-app-token.json) are never read by agents."
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
        # A glob overrides ripgrep's ignore rules, so a glob that matches a
        # secret basename would surface gitignored files a plain search skips.
        GLOB=$(echo "$INPUT" | jq -r '.tool_input.glob // empty' 2>/dev/null)
        if [[ -n "$GLOB" ]]; then
            for name in .env .env.local x.keystore x.pem gh-app-token.json; do
                if [[ "$name" == $GLOB ]]; then
                    block "Glob '$GLOB' would match secret files."
                fi
            done
        fi
        ;;
esac

exit 0
