#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./tools/remove-worktree.sh <name> --yes [--force]

Removes a single worktree under ./worktrees/. This is intentionally gated so
agents do not clean up unrelated worktrees by accident.
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

CONFIRMED="false"
FORCE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes)
      CONFIRMED="true"
      shift
      ;;
    --force)
      FORCE="true"
      shift
      ;;
    *)
      echo "Error: unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$CONFIRMED" != "true" ]]; then
  echo "Refusing to remove worktree without --yes." >&2
  usage >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_TEAM_ROOT="$(dirname "$SCRIPT_DIR")"
MAIN_REPO="${DEV_TEAM_ROOT}/repos/pocketpal-ai"
WORKTREE_PATH="${DEV_TEAM_ROOT}/worktrees/${NAME}"

if [[ ! -d "$WORKTREE_PATH" ]]; then
  echo "Error: worktree does not exist: ${WORKTREE_PATH}" >&2
  exit 1
fi

case "${WORKTREE_PATH}/" in
  "${DEV_TEAM_ROOT}/worktrees/"*) ;;
  *)
    echo "Error: target must live under ${DEV_TEAM_ROOT}/worktrees" >&2
    exit 1
    ;;
esac

cd "$MAIN_REPO"
if [[ "$FORCE" == "true" ]]; then
  git worktree remove --force "$WORKTREE_PATH"
else
  git worktree remove "$WORKTREE_PATH"
fi

echo "Removed worktree: ${WORKTREE_PATH}"
