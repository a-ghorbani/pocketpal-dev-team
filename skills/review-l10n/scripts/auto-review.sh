#!/usr/bin/env bash
# Deterministic pre-review for review-l10n --auto.
# Discovers the open Weblate PR (or uses an explicit one), fetches locale JSONs,
# runs the machine checks, and splits the diff per language for the semantic
# subagents. Does NOT decide, merge, or write — that is decide.mjs + apply-decision.sh.
#
# Usage: auto-review.sh [<pr-number>] [<repo>]
# Emits: ${SCRATCH} path on the last line (SCRATCH=...), plus pr.json, coverage.txt,
#        placeholders.txt, diff-report.txt, and per-language diff-<lang>.txt files.
set -euo pipefail

REPO="${2:-a-ghorbani/pocketpal-ai}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PR="${1:-}"
if [[ -z "${PR}" ]]; then
  # Discover the open Weblate auto-merge PR: author=weblate, head=weblate-translations.
  PR=$(gh pr list --repo "${REPO}" --state open --author weblate \
        --json number,headRefName \
        --jq '[.[] | select(.headRefName=="weblate-translations")][0].number // empty')
fi
if [[ -z "${PR}" ]]; then
  echo "NO_OPEN_WEBLATE_PR"
  exit 0
fi

TARGET_ID="PR-${PR}"
SCRATCH="/tmp/review-l10n-${TARGET_ID}"
rm -rf "${SCRATCH}"
mkdir -p "${SCRATCH}/head" "${SCRATCH}/base"

echo ">> target ${TARGET_ID} (repo ${REPO})"

# PR metadata (used by decide.mjs for scope + mergeability).
gh pr view "${PR}" --repo "${REPO}" \
  --json number,title,author,headRefName,baseRefName,mergeable,mergeStateStatus,state,isDraft,files \
  > "${SCRATCH}/pr.json"

# Fetch locale JSONs at head + base.
bash "${HERE}/fetch-pr.sh" "${PR}" "${SCRATCH}" "${REPO}"

# Machine checks.
node "${HERE}/coverage.mjs" "${SCRATCH}/head" > "${SCRATCH}/coverage.txt" || true
node "${HERE}/find-placeholder-issues.mjs" "${SCRATCH}/head" > "${SCRATCH}/placeholders.txt" || true

# Per-language diff for the semantic subagents.
node "${HERE}/diff-entries.mjs" "${SCRATCH}/head" "${SCRATCH}/base" "${SCRATCH}/diff-report.txt" || true
if [[ -s "${SCRATCH}/diff-report.txt" ]]; then
  awk -v scratch="${SCRATCH}" '
    /^## [A-Za-z_]+:/ { f=scratch "/diff-" $2 ".txt"; sub(":","",f) }
    f { print > f }
  ' "${SCRATCH}/diff-report.txt"
fi

echo ">> changed locale files:"
gh pr view "${PR}" --repo "${REPO}" --json files --jq '.files[].path' | sed 's/^/   /'

echo "SCRATCH=${SCRATCH}"
echo "PR=${PR}"
