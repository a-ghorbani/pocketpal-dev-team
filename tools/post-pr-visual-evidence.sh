#!/usr/bin/env bash
set -euo pipefail

# Upload local screenshots to GitHub's user-attachments CDN via the `gh image`
# extension (drogers0/gh-image) and post them as one PR comment. The uploaded
# URLs are public github.com/user-attachments/assets/... links, so they render
# inline on the PR — no binaries committed to the app repo.
#
# Usage:
#   tools/post-pr-visual-evidence.sh <pr-number> [--repo owner/repo] \
#       [--title "Visual evidence"] [--before-after] <caption=image-path> ...
#
# Every image carries a caption and lands in a table, never a bare stack:
#   default         | What it shows | Screenshot |, one row per image
#   --before-after  | Case | Before | After |, images taken in before/after
#                   pairs; the caption comes from the before image
#
# Run from inside the task worktree so `gh` infers the pocketpal-ai repo and the
# image paths resolve. Requires the `gh image` extension and a GitHub session
# token (GH_SESSION_TOKEN env var, or a logged-in browser session it extracts)
# for the upload; the comment itself is posted as the bot via tools/ghb.
#
#   success            -> posts the comment, prints the comment URL, exits 0
#   missing/bad token  -> prints MANUAL_POST_REQUIRED + the exact hand-run
#                         command, exits 3 (caller records a pending condition
#                         instead of claiming the evidence was posted)
#   bad args / no tool -> exits 2

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

title="Visual evidence"
repo_args=()
pr=""
pairs=0
shots=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)         repo_args=(--repo "$2"); shift 2 ;;
    --title)        title="$2"; shift 2 ;;
    --before-after) pairs=1; shift ;;
    --)             shift; while [[ $# -gt 0 ]]; do shots+=("$1"); shift; done ;;
    -*)             echo "Unknown flag: $1" >&2; exit 2 ;;
    *)              if [[ -z "$pr" ]]; then pr="$1"; else shots+=("$1"); fi; shift ;;
  esac
done

usage="usage: $0 <pr-number> [--repo owner/repo] [--title <t>] [--before-after] <caption=image> ..."
if [[ -z "$pr" || ${#shots[@]} -eq 0 ]]; then
  echo "$usage" >&2
  exit 2
fi
if [[ $pairs -eq 1 && $(( ${#shots[@]} % 2 )) -ne 0 ]]; then
  echo "FATAL: --before-after takes images in before/after pairs" >&2
  exit 2
fi

images=()
captions=()
for i in "${!shots[@]}"; do
  shot="${shots[$i]}"
  if [[ "$shot" == *=* ]]; then
    captions+=("${shot%=*}")
    images+=("${shot##*=}")
  elif [[ $pairs -eq 1 && $(( i % 2 )) -eq 1 ]]; then
    captions+=("")
    images+=("$shot")
  else
    echo "FATAL: missing caption for $shot (use caption=path)" >&2
    exit 2
  fi
done

if ! gh image --version >/dev/null 2>&1; then
  echo "FATAL: gh image extension not installed (gh extension install drogers0/gh-image)" >&2
  exit 2
fi

missing=0
for img in "${images[@]}"; do
  [[ -f "$img" ]] || { echo "FATAL: image not found: $img" >&2; missing=1; }
done
[[ $missing -eq 0 ]] || exit 2

manual_cmd="gh image ${repo_args[*]} ${images[*]}   # then paste the markdown into: $here/ghb pr comment $pr ${repo_args[*]} --body-file -"

# Honest degrade: verify a token works before uploading, so a tokenless headless
# run reports a pending manual post rather than a half-finished comment.
#
# check-token takes NO --repo: passing one makes it exit non-zero with "--repo
# cannot be combined with check-token", which this gate used to read as "no
# token" and report as MANUAL_POST_REQUIRED on a perfectly valid session. The
# stderr it printed said exactly that, and this line discarded it.
probe_err="$(gh image check-token 2>&1 >/dev/null)" || {
  {
    echo "MANUAL_POST_REQUIRED: no valid GitHub session token for image upload."
    echo "  gh image check-token said: ${probe_err:-(no output)}"
    echo "  Captures (local, NOT yet on PR #$pr):"
    printf '    - %s\n' "${images[@]}"
    echo "  Post manually once a token is available (GH_SESSION_TOKEN or a logged-in browser):"
    echo "    $manual_cmd"
  } >&2
  exit 3
}

refs="$(gh image ${repo_args[@]+"${repo_args[@]}"} "${images[@]}")" || {
  echo "MANUAL_POST_REQUIRED: gh image upload failed. Retry: $manual_cmd" >&2
  exit 3
}

harness="${PPDT_HARNESS:-}"
if [ -z "$harness" ]; then
  if [ -n "${CLAUDECODE:-}" ]; then harness="Claude Code"
  elif env | grep -q '^CODEX_'; then harness="Codex"
  fi
fi

mapfile -t urls < <(grep -o 'https://[^)" ]*' <<<"$refs")
if [[ ${#urls[@]} -ne ${#images[@]} ]]; then
  echo "MANUAL_POST_REQUIRED: expected ${#images[@]} upload URLs, got ${#urls[@]}:" >&2
  echo "$refs" >&2
  exit 3
fi

cell() { printf '<img src="%s" width="300">' "$1"; }
if [[ $pairs -eq 1 ]]; then
  table="| Case | Before | After |
| --- | --- | --- |"
  for (( i = 0; i < ${#urls[@]}; i += 2 )); do
    table+=$'\n'"| ${captions[$i]} | $(cell "${urls[$i]}") | $(cell "${urls[$((i + 1))]}") |"
  done
else
  table="| What it shows | Screenshot |
| --- | --- |"
  for i in "${!urls[@]}"; do
    table+=$'\n'"| ${captions[$i]} | $(cell "${urls[$i]}") |"
  done
fi

body="## ${title}

${table}

Generated by [PocketPal Dev Team](https://github.com/a-ghorbani/pocketpal-dev-team)${harness:+ · $harness}"

"$here/ghb" pr comment "$pr" ${repo_args[@]+"${repo_args[@]}"} --body "$body" || {
  echo "MANUAL_POST_REQUIRED: PR comment failed (images are uploaded). Post by hand:" >&2
  echo "    $here/ghb pr comment $pr ${repo_args[*]} --body-file <file containing the markdown above>" >&2
  exit 3
}
echo "Posted ${#images[@]} image(s) to PR #$pr as the bot"
