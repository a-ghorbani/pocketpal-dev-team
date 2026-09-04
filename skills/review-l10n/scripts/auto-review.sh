#!/usr/bin/env bash
# Deterministic pre-review for review-l10n --auto.
# Discovers the open Weblate PR (or uses an explicit one), fetches locale JSONs,
# runs the machine checks, and splits the diff per language for the semantic
# subagents. Does NOT decide, merge, or write — that is decide.mjs + apply-decision.sh.
#
# Usage: auto-review.sh [<pr-number>] [<repo>]
# Emits: ${SCRATCH} path on the last line (SCRATCH=...), plus pr.json, coverage.txt,
#        placeholders.txt, diff-report.txt, per-language diff-<lang>.txt files, and
#        feedback.json + feedback/feedback-<lang>.md (translator comments/suggestions).
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

# Which languages actually ship, derived from src/locales/index.ts at the base
# commit — the tree this PR merges into. Never hardcode this list: it went stale
# once and three shipping languages silently fell out of the gate.
BASE_OID=$(gh pr view "${PR}" --repo "${REPO}" --json baseRefOid --jq .baseRefOid)
if ! WIRED=$(node "${HERE}/wired-langs.mjs" --ref="${BASE_OID}" --repo="${REPO}"); then
  echo "!! could not derive the wired-language list from ${REPO}@${BASE_OID}"
  echo "!! decide.mjs will gate EVERY changed locale rather than guess."
  WIRED=""
fi
echo "${WIRED}" > "${SCRATCH}/wired.txt"
echo ">> wired languages: ${WIRED:-UNKNOWN (gating all)}"

# Machine checks.
node "${HERE}/coverage.mjs" "${SCRATCH}/head" --wired="${WIRED}" > "${SCRATCH}/coverage.txt" || true
node "${HERE}/find-placeholder-issues.mjs" "${SCRATCH}/head" > "${SCRATCH}/placeholders.txt" || true

# Per-language diff for the semantic subagents, plus the chunk plan.
node "${HERE}/diff-entries.mjs" "${SCRATCH}/head" "${SCRATCH}/base" "${SCRATCH}/diff-report.txt" \
  --manifest="${SCRATCH}/review-manifest.json" || true
if [[ -s "${SCRATCH}/diff-report.txt" ]]; then
  awk -v scratch="${SCRATCH}" '
    /^## [A-Za-z_]+:/ { f=scratch "/diff-" $2 ".txt"; sub(":","",f) }
    f { print > f }
  ' "${SCRATCH}/diff-report.txt"
fi

# Translator feedback on Weblate: comments and pending suggestions, every language.
# decide.mjs holds those units (no overwrite) and the feedback reviewers answer the
# open threads. Failure here is loud: without feedback.json nothing is overwritten.
if node "${HERE}/fetch-feedback.mjs" --out="${SCRATCH}/feedback.json" --md-dir="${SCRATCH}/feedback" \
     > "${SCRATCH}/feedback.txt" 2> "${SCRATCH}/feedback.err"; then
  cat "${SCRATCH}/feedback.txt"
else
  echo "!! fetch-feedback.mjs FAILED (see ${SCRATCH}/feedback.err) — decide.mjs will downgrade every overwrite to a comment"
  rm -f "${SCRATCH}/feedback.json"
fi

echo ">> changed locale files:"
gh pr view "${PR}" --repo "${REPO}" --json files --jq '.files[].path' | sed 's/^/   /'

echo "SCRATCH=${SCRATCH}"
echo "PR=${PR}"
echo "WIRED=${WIRED}"
