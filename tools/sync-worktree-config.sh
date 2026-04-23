#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: ./tools/sync-worktree-config.sh <worktree-path>

Copies the allowlisted gitignored config/env files from repos/pocketpal-ai into
an existing worktree under ./worktrees/.
EOF
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_TEAM_ROOT="$(dirname "$SCRIPT_DIR")"
MAIN_REPO="${DEV_TEAM_ROOT}/repos/pocketpal-ai"
WORKTREES_ROOT="${DEV_TEAM_ROOT}/worktrees"

TARGET_INPUT="$1"
if [[ "$TARGET_INPUT" = /* ]]; then
  TARGET_WORKTREE="$TARGET_INPUT"
else
  TARGET_WORKTREE="$(cd "$DEV_TEAM_ROOT" && cd "$TARGET_INPUT" 2>/dev/null && pwd)"
fi

if [[ -z "${TARGET_WORKTREE:-}" || ! -d "$TARGET_WORKTREE" ]]; then
  echo "Error: worktree does not exist: $1" >&2
  exit 1
fi

case "${TARGET_WORKTREE}/" in
  "${WORKTREES_ROOT}/"*) ;;
  *)
    echo "Error: target must live under ${WORKTREES_ROOT}" >&2
    exit 1
    ;;
esac

if [[ ! -e "${TARGET_WORKTREE}/.git" ]]; then
  echo "Error: target is not a git worktree: ${TARGET_WORKTREE}" >&2
  exit 1
fi

ALLOWLIST=(
  ".env"
  "e2e/.env"
  "e2e/devices.json"
  "ios/.xcode.env.local"
  "ios/GoogleService-Info.plist"
  "ios/Config/Env.xcconfig"
  "android/local.properties"
  "android/app/google-services.json"
  "android/app/pocketpal-release-key.keystore"
)

copy_if_exists() {
  local rel="$1"
  local src="${MAIN_REPO}/${rel}"
  local dst="${TARGET_WORKTREE}/${rel}"

  if [[ -f "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    echo "Copied ${rel}"
  fi
}

echo "Syncing allowlisted config into ${TARGET_WORKTREE}"
for rel in "${ALLOWLIST[@]}"; do
  copy_if_exists "$rel"
done
