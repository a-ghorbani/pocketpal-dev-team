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
if ! echo "$COMMAND" | grep -q 'git worktree add'; then
    exit 0
fi

# Extract the worktree path from the command
# Handles: git worktree add <path> ...
WORKTREE_REL=$(echo "$COMMAND" | sed -n 's/.*git worktree add  *\([^ ]*\).*/\1/p')
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
if [ -n "$CWD" ]; then
    WORKTREE_ABS=$(cd "$CWD" && realpath "$WORKTREE_REL" 2>/dev/null)
else
    WORKTREE_ABS=$(cd "$MAIN_REPO" && realpath "$WORKTREE_REL" 2>/dev/null)
fi

if [ -z "$WORKTREE_ABS" ] || [ ! -d "$WORKTREE_ABS" ]; then
    exit 0
fi

# Copy helper — silent, no error if source missing
copy_if_exists() {
    local src="$1" dst="$2"
    if [ -f "$src" ]; then
        mkdir -p "$(dirname "$dst")"
        cp "$src" "$dst"
        echo "  Copied $(basename "$src")"
    fi
}

echo ""
echo "Copying gitignored env/config files to worktree..."

# Root-level
copy_if_exists "${MAIN_REPO}/.env" "${WORKTREE_ABS}/.env"

# E2E
copy_if_exists "${MAIN_REPO}/e2e/.env" "${WORKTREE_ABS}/e2e/.env"
copy_if_exists "${MAIN_REPO}/e2e/devices.json" "${WORKTREE_ABS}/e2e/devices.json"

# iOS
copy_if_exists "${MAIN_REPO}/ios/.xcode.env.local" "${WORKTREE_ABS}/ios/.xcode.env.local"
copy_if_exists "${MAIN_REPO}/ios/GoogleService-Info.plist" "${WORKTREE_ABS}/ios/GoogleService-Info.plist"
copy_if_exists "${MAIN_REPO}/ios/Config/Env.xcconfig" "${WORKTREE_ABS}/ios/Config/Env.xcconfig"

# Android
copy_if_exists "${MAIN_REPO}/android/local.properties" "${WORKTREE_ABS}/android/local.properties"
copy_if_exists "${MAIN_REPO}/android/app/google-services.json" "${WORKTREE_ABS}/android/app/google-services.json"
copy_if_exists "${MAIN_REPO}/android/app/pocketpal-release-key.keystore" "${WORKTREE_ABS}/android/app/pocketpal-release-key.keystore"

echo "Done."
exit 0
