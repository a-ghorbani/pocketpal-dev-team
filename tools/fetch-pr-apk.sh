#!/usr/bin/env bash
# Fetches a built Android APK artifact from CI for a given PR number and
# installs it inside the target pocketpal-ai checkout so the E2E runner can
# use --skip-build.
#
# Two modes:
#   (default) prod  : newest completed ci.yml pull_request run for the PR,
#                     artifact android-release-apk -> app-release.apk
#                     (bridge-STRIPPED prod build).
#   --e2e           : resolves the PR's head branch, then the newest completed
#                     e2e-tests.yml workflow_dispatch run for that branch,
#                     artifact e2e-android-apk -> app-e2e-releaseE2e.apk
#                     (bridge-ENABLED E2E build; needed for specs that drive
#                     the automation bridge).
#
# E2E-mode note: e2e-tests.yml is a manual workflow_dispatch and is not linked
# to a PR. Matching is by run head_branch == the PR's head ref, so dispatch the
# workflow with the PR branch selected in the "Use workflow from" selector
# (or `gh workflow run e2e-tests.yml --ref <PR branch>`). Otherwise no run
# will match.
#
# Runs inside a pocketpal-ai worktree or standalone checkout. Set POCKETPAL_REPO
# to point at a specific checkout, else the current working directory is used.
set -euo pipefail

MODE="prod"
if [[ "${1:-}" == "--e2e" || "${1:-}" == "-e" ]]; then
  MODE="e2e"
  shift
fi

if [[ "${1:-}" == "" || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<EOF
Usage: $0 [--e2e] <pr_number> [artifact_name] [out_path]

Modes:
  (default)  prod build from ci.yml
             artifact default: android-release-apk
             out_path default: android/app/build/outputs/apk/release/app-release.apk
  --e2e      bridge-enabled E2E build from e2e-tests.yml
             artifact default: e2e-android-apk
             out_path default: android/app/build/outputs/apk/e2e/releaseE2e/app-e2e-releaseE2e.apk

Env:
  POCKETPAL_REPO  Path to pocketpal-ai checkout (default: cwd)
  GITHUB_TOKEN    Token with repo + actions:read (or GH_TOKEN)
EOF
  exit 1
fi

PR_NUMBER="$1"

if [[ "$MODE" == "e2e" ]]; then
  WORKFLOW="e2e-tests.yml"
  ARTIFACT_NAME="${2:-e2e-android-apk}"
  OUT_PATH="${3:-android/app/build/outputs/apk/e2e/releaseE2e/app-e2e-releaseE2e.apk}"
  APK_GLOB="app-e2e-releaseE2e.apk"
else
  WORKFLOW="ci.yml"
  ARTIFACT_NAME="${2:-android-release-apk}"
  OUT_PATH="${3:-android/app/build/outputs/apk/release/app-release.apk}"
  APK_GLOB="app-release.apk"
fi

REPO_ROOT="${POCKETPAL_REPO:-$(pwd)}"
if [[ ! -d "$REPO_ROOT/.git" && ! -f "$REPO_ROOT/.git" ]]; then
  echo "Error: $REPO_ROOT is not a git repo. Set POCKETPAL_REPO to a pocketpal-ai checkout." >&2
  exit 1
fi

TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
if [[ -z "${TOKEN}" ]]; then
  echo "Error: set GITHUB_TOKEN or GH_TOKEN with repo + actions:read." >&2
  exit 1
fi

REPO_SSH=$(git -C "$REPO_ROOT" remote get-url origin)
REPO=$(echo "$REPO_SSH" | sed -E 's#.*github.com[:/](.+/.+)\.git#\1#')
if [[ -z "${REPO}" ]]; then
  echo "Error: could not determine repo from origin of $REPO_ROOT." >&2
  exit 1
fi

API="https://api.github.com/repos/${REPO}"
AUTH=(-H "Authorization: Bearer ${TOKEN}" -H "Accept: application/vnd.github+json")

if [[ "$MODE" == "e2e" ]]; then
  PR_JSON=$(curl -sS "${AUTH[@]}" "${API}/pulls/${PR_NUMBER}")
  HEAD_REF=$(echo "$PR_JSON" | jq -r '.head.ref // empty')
  if [[ -z "${HEAD_REF}" ]]; then
    echo "Error: could not resolve head branch for PR #${PR_NUMBER}." >&2
    exit 1
  fi
  echo "PR #${PR_NUMBER} head branch: ${HEAD_REF}"

  RUNS_JSON=$(curl -sS "${AUTH[@]}" \
    "${API}/actions/workflows/${WORKFLOW}/runs?event=workflow_dispatch&status=completed&per_page=50")

  RUN_ID=$(echo "$RUNS_JSON" | jq -r --arg br "$HEAD_REF" '
    .workflow_runs
    | map(select(.head_branch == $br))
    | sort_by(.run_number)
    | reverse
    | .[0].id // empty
  ')

  if [[ -z "${RUN_ID}" ]]; then
    echo "Error: no completed ${WORKFLOW} workflow_dispatch run found for branch '${HEAD_REF}' (PR #${PR_NUMBER})." >&2
    echo "Dispatch ${WORKFLOW} with the PR branch selected as the workflow ref before retrying." >&2
    exit 1
  fi
else
  RUNS_JSON=$(curl -sS "${AUTH[@]}" \
    "${API}/actions/workflows/${WORKFLOW}/runs?event=pull_request&status=completed&per_page=50")

  RUN_ID=$(echo "$RUNS_JSON" | jq -r --argjson pr "$PR_NUMBER" '
    .workflow_runs
    | map(select(.pull_requests | any(.number == $pr)))
    | sort_by(.run_number)
    | reverse
    | .[0].id // empty
  ')

  if [[ -z "${RUN_ID}" ]]; then
    echo "Error: no completed CI runs found for PR #${PR_NUMBER}." >&2
    exit 1
  fi
fi

echo "Using ${WORKFLOW} run: ${RUN_ID}"

ARTIFACTS_JSON=$(curl -sS "${AUTH[@]}" "${API}/actions/runs/${RUN_ID}/artifacts")
ARCHIVE_URL=$(echo "$ARTIFACTS_JSON" | jq -r --arg name "$ARTIFACT_NAME" '
  .artifacts | map(select(.name == $name)) | .[0].archive_download_url // empty
')

if [[ -z "${ARCHIVE_URL}" ]]; then
  echo "Error: artifact '${ARTIFACT_NAME}' not found for run ${RUN_ID}." >&2
  exit 1
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

curl -sS -L "${AUTH[@]}" -o "${TMP_DIR}/artifact.zip" "${ARCHIVE_URL}"
unzip -q "${TMP_DIR}/artifact.zip" -d "${TMP_DIR}/artifact"

APK_PATH=$(find "${TMP_DIR}/artifact" -type f -name "${APK_GLOB}" | head -n 1 || true)
if [[ -z "${APK_PATH}" ]]; then
  echo "Error: ${APK_GLOB} not found inside artifact '${ARTIFACT_NAME}'." >&2
  exit 1
fi

ABS_OUT="$REPO_ROOT/$OUT_PATH"
mkdir -p "$(dirname "$ABS_OUT")"
cp -f "$APK_PATH" "$ABS_OUT"
echo "Saved APK to: $ABS_OUT"
