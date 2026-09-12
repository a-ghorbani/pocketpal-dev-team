#!/bin/bash
# PreToolUse hook: blocks pushing app code onto main/master from a worktree or
# the submodule, whatever refspec spells it (`main`, `HEAD:main`, `br:main`,
# `+refs/heads/main`, `--all`, `--mirror`).
#
# Pushes from the dev-team root are unaffected: this repo's own main is the
# control plane and is pushed normally.
#
# Exit 2 = block, exit 0 = allow.

INPUT=$(cat)
exec >&2
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

echo "$COMMAND" | grep -qE '(^|[;&|]|\s)git(\s+-C\s+[^[:space:]]+)?\s+push\b' || exit 0

# Where does the push run? An explicit `git -C <dir>` or `cd <dir>` wins.
TARGET_DIR=$(echo "$COMMAND" | sed -nE 's/.*git[[:space:]]+-C[[:space:]]+([^[:space:]]+).*/\1/p' | head -1)
[[ -z "$TARGET_DIR" ]] && TARGET_DIR=$(echo "$COMMAND" | sed -nE 's/.*(cd|pushd)[[:space:]]+([^[:space:];|&]+).*/\2/p' | head -1)
if [[ -n "$TARGET_DIR" ]]; then
    RESOLVED=$(cd "$CWD" 2>/dev/null && cd "$TARGET_DIR" 2>/dev/null && pwd)
    [[ -n "$RESOLVED" ]] && CWD="$RESOLVED"
fi

# Only app code is gated: worktrees and the submodule.
case "$CWD" in
    */worktrees/*|*/repos/pocketpal-ai*) ;;
    *) exit 0 ;;
esac

block() {
    echo "BLOCKED: $1"
    echo ""
    echo "App changes reach main through a reviewed PR, never a push."
    echo "Push the feature branch instead:  git push -u origin <feature-branch>"
    echo "The pipeline-reviewer opens the draft PR; a human merges it."
    exit 2
}

# Strip the command down to the push's arguments.
ARGS=$(echo "$COMMAND" | sed -nE 's/.*git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+push[[:space:]]*//p')

echo "$ARGS" | grep -qE '(^|[[:space:]])--(all|mirror)\b' && \
    block "'git push --all/--mirror' from app code can carry main."

# Destination of each refspec: the part after ':', or the whole token.
for token in $ARGS; do
    case "$token" in
        -*) continue ;;
    esac
    dest="${token##*:}"
    dest="${dest#+}"
    dest="${dest#refs/heads/}"
    case "$dest" in
        main|master) block "'$COMMAND' would push app code straight onto $dest." ;;
    esac
done

exit 0
