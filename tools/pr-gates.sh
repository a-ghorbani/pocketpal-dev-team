#!/usr/bin/env bash
set -euo pipefail

# Mechanical gates for a PocketPal change, so no agent or reviewer spends a
# round finding them by hand. Prints one line per gate; exits 1 when any gate
# FAILs, 4 when none fails but CI is still PEND (wait, don't fix).
#
# Usage:
#   tools/pr-gates.sh <pr-number> [--repo owner/repo]
#   tools/pr-gates.sh --branch [<base-ref>]       # from inside a worktree, before the PR exists
#
# Gates:
#   ci        PR checks green (PEND: still running or not reported yet; not a pass)
#   hygiene   no internal tracker IDs, task IDs, story paths or story anchors in
#             the PR title, body, commit messages, or added source lines
#   evidence  an evidence section (a "## ...evidence..." heading) in the PR body or a comment;
#             UI changes need captures somewhere on the PR
#   native    native files changed -> native builds are required (WARN only)
#   gh-image  the gh image session token is valid when captures must be posted
#
# Exit codes: 0 all pass, 1 a gate FAILed, 4 none failed but CI PEND, 2 bad usage or gh error.

repo="a-ghorbani/pocketpal-ai"
mode="pr"
pr=""
base="origin/main"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) repo="$2"; shift 2 ;;
    --branch) mode="branch"; shift; if [[ $# -gt 0 && "$1" != --* ]]; then base="$1"; shift; fi ;;
    -h|--help) sed -n '4,21p' "$0"; exit 0 ;;
    *) if [[ -z "$pr" && "$1" =~ ^[0-9]+$ ]]; then pr="$1"; shift; else echo "unknown argument: $1" >&2; exit 2; fi ;;
  esac
done
[[ "$mode" == "pr" && -z "$pr" ]] && { echo "usage: tools/pr-gates.sh <pr-number> | --branch [<base>]" >&2; exit 2; }

# Tracker and task IDs are never legitimate anywhere public. Story anchors are
# only checked in PR text and commit messages: in source they collide with
# locale, legal, and e2e text.
internal_ids='\b(POC|FOU|PAL|REL|OPS|ADV)-[0-9]+\b|\bTASK-[0-9]{8}(-[0-9]{4})?\b|linear\.app|workflows/(stories|reviews)/'
story_anchors='\b(what|how|evidence|decisions|progress)\.md\b|§[0-9]|\bI_DS[0-9]|\bround-[0-9]+/'
ui_paths='^src/(screens|components|theme)/|^src/.*\.tsx$'
test_paths='/__tests__/|\.test\.tsx?$|^__mocks__/'
native_paths='^(package\.json|ios/|android/|.*Podfile|.*\.podspec$|.*build\.gradle)'

failed=0 pending=0
report() { printf '%-9s %-5s %s\n' "$1" "$2" "$3"; [[ "$2" == FAIL ]] && failed=1; [[ "$2" == PEND ]] && pending=1; return 0; }
die() { echo "pr-gates: $*" >&2; exit 2; }

# Merge commits never reach main under squash merges, so their subjects are skipped.
if [[ "$mode" == "pr" ]]; then
  files=$(gh pr diff "$pr" --repo "$repo" --name-only) || die "gh pr diff --name-only failed"
  pr_text=$(gh pr view "$pr" --repo "$repo" --json title,body --jq '.title, .body') || die "gh pr view failed"
  commit_text=$(gh pr view "$pr" --repo "$repo" --json commits \
    --jq '.commits[] | select(.messageHeadline | startswith("Merge ") | not) | .messageHeadline, .messageBody') || die "gh pr view commits failed"
  diff=$(gh pr diff "$pr" --repo "$repo") || die "gh pr diff failed (very large diffs return HTTP 406; run --branch from the worktree)"
  # The evidence may be a PR comment or a section of the PR body.
  comments=$(gh pr view "$pr" --repo "$repo" --json body,comments --jq '.body, .comments[].body') || die "gh pr view comments failed"
else
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "--branch must run inside a worktree"
  files=$(git diff --name-only "$base"...HEAD)
  pr_text=""
  commit_text=$(git log --no-merges --format='%s%n%b' "$base"..HEAD)
  diff=$(git diff "$base"...HEAD)
  comments=""
fi
public_text=$(printf '%s\n%s\n' "$pr_text" "$commit_text")
added=$(grep -E '^\+[^+]' <<<"$diff" || true)
ui_files=$(grep -E "$ui_paths" <<<"$files" | grep -vE "$test_paths" || true)

# ci
if [[ "$mode" == "pr" ]]; then
  if ! checks=$(gh pr checks "$pr" --repo "$repo" --json name,bucket --jq '.[] | "\(.bucket) \(.name)"' 2>&1); then
    grep -qi 'no checks' <<<"$checks" && report ci PEND "no checks reported yet" || die "gh pr checks failed: $checks"
  elif [[ -z "$checks" ]]; then
    report ci PEND "no checks reported yet"
  elif grep -qE '^(fail|cancel)' <<<"$checks"; then
    report ci FAIL "$(grep -E '^(fail|cancel)' <<<"$checks" | cut -d' ' -f2- | paste -sd, -)"
  elif grep -q '^pending' <<<"$checks"; then
    report ci PEND "pending: $(grep '^pending' <<<"$checks" | cut -d' ' -f2- | paste -sd, -)"
  else
    report ci PASS "$(wc -l <<<"$checks" | tr -d ' ') checks green"
  fi
else
  report ci SKIP "no PR yet"
fi

# hygiene
hits=$( { grep -oE "$internal_ids|$story_anchors" <<<"$public_text" | sed 's/^/pr-text:/'; grep -oE "$internal_ids" <<<"$added" | sed 's/^/source:/'; } | sort -u | head -5 || true)
if [[ -n "$hits" ]]; then
  report hygiene FAIL "$(paste -sd' ' <<<"$hits")"
else
  report hygiene PASS "no internal references in public text or added lines"
fi

# evidence
evidence_comments=$(awk 'BEGIN{RS="\n## "} /^[^\n]*[Ee]vidence/' <<<"$(printf '\n%s' "$comments")" || true)
if [[ "$mode" == "pr" ]]; then
  if [[ -z "$evidence_comments" ]]; then
    report evidence FAIL "no evidence section (a '## ... evidence' heading) in the PR body or comments"
  elif [[ -n "$ui_files" ]] && ! grep -qE '!\[|<img|user-attachments' <<<"$comments"; then
    report evidence FAIL "UI changed ($(head -2 <<<"$ui_files" | paste -sd, -)); no captures in the PR body or comments"
  else
    report evidence PASS "evidence present${ui_files:+, with captures}"
  fi
else
  report evidence WARN "post the evidence comment once the PR exists${ui_files:+ (UI changed: captures required)}"
fi
if [[ -n "$ui_files" ]]; then
  if gh image check-token >/dev/null 2>&1; then
    report gh-image PASS "session token valid"
  else
    report gh-image WARN "gh image session token missing or expired; capture upload will exit 3"
  fi
fi

# native
native=$(grep -E "$native_paths" <<<"$files" | head -3 | paste -sd, - || true)
if [[ -n "$native" ]]; then
  report native WARN "native files changed ($native): pod install, iOS and Android release builds required"
else
  report native PASS "no native files changed"
fi

(( failed )) && exit 1
(( pending )) && exit 4
exit 0
