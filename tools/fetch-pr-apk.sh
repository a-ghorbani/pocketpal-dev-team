#!/usr/bin/env bash
# Fetches the latest android-release-apk artifact from CI for a given PR
# number and installs it at android/app/build/outputs/apk/release/app-release.apk
# inside the target pocketpal-ai checkout so the E2E runner can use --skip-build.
#
# Runs inside a pocketpal-ai worktree or standalone checkout. Set POCKETPAL_REPO
# to point at a specific checkout, else the current working directory is used.
set -euo pipefail

if [[ "${1:-}" == "" || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<EOF
Usage: $0 <pr_number> [artifact_name] [out_path]
  artifact_name default: android-release-apk
  out_path default: android/app/build/outputs/apk/release/app-release.apk

Env:
  POCKETPAL_REPO  Path to pocketpal-ai checkout (default: cwd)
  GITHUB_TOKEN    Token with repo + actions:read (or GH_TOKEN)
EOF
  exit 1
fi

PR_NUMBER="$1"
ARTIFACT_NAME="${2:-android-release-apk}"
OUT_PATH="${3:-android/app/build/outputs/apk/release/app-release.apk}"

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

RUNS_JSON=$(curl -sS "${AUTH[@]}" \
  "${API}/actions/workflows/ci.yml/runs?event=pull_request&status=completed&per_page=50")

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

echo "Using CI run: ${RUN_ID}"

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

APK_PATH=$(find "${TMP_DIR}/artifact" -type f -name "app-release.apk" | head -n 1 || true)
if [[ -z "${APK_PATH}" ]]; then
  echo "Error: app-release.apk not found inside artifact." >&2
  exit 1
fi

ABS_OUT="$REPO_ROOT/$OUT_PATH"
mkdir -p "$(dirname "$ABS_OUT")"
cp -f "$APK_PATH" "$ABS_OUT"
echo "Saved APK to: $ABS_OUT"
