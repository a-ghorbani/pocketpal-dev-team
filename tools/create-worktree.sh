#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./tools/create-worktree.sh <name> [options]

Creates a pocketpal-ai worktree under ./worktrees/ and syncs the allowlisted
gitignored config/env files into it.

Options:
  --branch <branch>   Branch name to create or check out (default: feature/<name>)
  --ref <ref>         Base ref/commit (default: origin/main)
  --detach            Create a detached worktree at <ref>
EOF
}

if [[ $# -lt 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 1
fi

NAME="$1"
shift

if [[ "$NAME" == */* || "$NAME" == "." || "$NAME" == ".." ]]; then
  echo "Error: worktree name must be a single path segment." >&2
  exit 1
fi

BRANCH="feature/${NAME}"
REF="origin/main"
DETACH="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --ref)
      REF="$2"
      shift 2
      ;;
    --detach)
      DETACH="true"
      shift
      ;;
    *)
      echo "Error: unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_TEAM_ROOT="$(dirname "$SCRIPT_DIR")"
MAIN_REPO="${DEV_TEAM_ROOT}/repos/pocketpal-ai"
WORKTREE_PATH="${DEV_TEAM_ROOT}/worktrees/${NAME}"

if [[ -e "$WORKTREE_PATH" ]]; then
  echo "Error: worktree already exists: ${WORKTREE_PATH}" >&2
  exit 1
fi

cd "$MAIN_REPO"
git fetch origin

if [[ "$DETACH" == "true" ]]; then
  git worktree add --detach "$WORKTREE_PATH" "$REF"
elif git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git worktree add "$WORKTREE_PATH" "$BRANCH"
else
  git worktree add "$WORKTREE_PATH" -b "$BRANCH" "$REF"
fi

"${SCRIPT_DIR}/sync-worktree-config.sh" "$WORKTREE_PATH"

echo ""
echo "Created worktree: ${WORKTREE_PATH}"
if [[ "$DETACH" == "true" ]]; then
  echo "Mode: detached"
else
  echo "Branch: ${BRANCH}"
fi
echo "Base ref: ${REF}"
