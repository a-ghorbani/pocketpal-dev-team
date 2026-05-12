#!/usr/bin/env bash
# Fetch all locale JSONs from a Weblate-style PR into ${SCRATCH}/head and ${SCRATCH}/base.
# Usage: fetch-pr.sh <pr-number> <scratch-dir> [<repo>]
set -euo pipefail

PR="${1:?pr number required}"
SCRATCH="${2:?scratch dir required}"
REPO="${3:-a-ghorbani/pocketpal-ai}"

mkdir -p "${SCRATCH}/head" "${SCRATCH}/base"

HEAD_OID=$(gh pr view "${PR}" --repo "${REPO}" --json headRefOid --jq .headRefOid)
BASE_OID=$(gh pr view "${PR}" --repo "${REPO}" --json baseRefOid --jq .baseRefOid)

# Discover all locale files at HEAD (so we can compute coverage for languages not changed in this PR too).
mapfile -t HEAD_FILES < <(gh api "repos/${REPO}/contents/src/locales?ref=${HEAD_OID}" --jq '.[] | select(.name | endswith(".json")) | .name')

# Changed files only — used as the candidate list for `base/` (skip download if base is identical to head).
mapfile -t CHANGED < <(gh pr view "${PR}" --repo "${REPO}" --json files --jq '.files[].path' | grep '^src/locales/.*\.json$' | sed 's|^src/locales/||' || true)

echo "PR=${PR} repo=${REPO} head=${HEAD_OID:0:10} base=${BASE_OID:0:10}"
echo "head locales: ${#HEAD_FILES[@]} | changed: ${#CHANGED[@]}"

for f in "${HEAD_FILES[@]}"; do
  gh api "repos/${REPO}/contents/src/locales/${f}?ref=${HEAD_OID}" --jq '.content' \
    | base64 -d > "${SCRATCH}/head/${f}"
done

for f in "${CHANGED[@]}"; do
  # Some files might be newly added in the PR — try base, skip if 404.
  if gh api "repos/${REPO}/contents/src/locales/${f}?ref=${BASE_OID}" --jq '.content' 2>/dev/null \
       | base64 -d > "${SCRATCH}/base/${f}.tmp"; then
    mv "${SCRATCH}/base/${f}.tmp" "${SCRATCH}/base/${f}"
  else
    rm -f "${SCRATCH}/base/${f}.tmp"
    echo "  (new file in PR, no base): ${f}"
  fi
done

echo "head files written to ${SCRATCH}/head"
echo "base files written to ${SCRATCH}/base"
