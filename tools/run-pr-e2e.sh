#!/usr/bin/env bash
# Fetches the latest CI APK for a PR and runs E2E tests against it via the
# pocketpal-ai e2e runner (scripts/run-e2e.ts) with --skip-build.
#
# Target checkout is resolved via POCKETPAL_REPO env var, else cwd. Must be a
# pocketpal-ai worktree or standalone clone with e2e/ present.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ "${1:-}" == "" || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<EOF
Usage: $0 <pr_number> [--e2e] [--no-fetch] [--specs spec1,spec2,...] [-- <run-e2e.ts args>]

Fetches the CI APK for a PR and runs E2E tests via run-e2e.ts --skip-build.

  --e2e             Fetch the bridge-ENABLED E2E APK (com.pocketpalai.e2e)
                    from the newest e2e-tests.yml workflow_dispatch run for
                    the PR's head branch, instead of the default prod APK
                    from ci.yml. Required for specs that drive the automation
                    bridge. The e2e-tests.yml workflow must have been
                    dispatched with the PR branch first.
  --no-fetch        Skip APK download (reuse an already-installed APK)
  --specs <list>    Comma-separated specs to run in sequence (one invocation
                    each). If omitted, a single default run is performed and
                    --spec must be passed after -- instead.
  --                Everything after is passed verbatim to run-e2e.ts

Examples:
  $0 688 -- --devices connected
  $0 688 --e2e --specs quick-smoke -- --devices connected
  $0 688 --specs quick-smoke,load-stress,language -- --devices virtual-only
  $0 688 --no-fetch -- --spec load-stress --devices connected

Env:
  POCKETPAL_REPO    Path to pocketpal-ai checkout (default: cwd)
  GITHUB_TOKEN      For fetching the APK artifact (unless --no-fetch)
  ANDROID_HOME      Android SDK location (or ANDROID_SDK_ROOT). Must be set.
EOF
  exit 1
fi

PR_NUMBER="$1"
shift

NO_FETCH="false"
E2E_MODE="false"
SPECS=""
E2E_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --e2e)
      E2E_MODE="true"
      shift
      ;;
    --no-fetch)
      NO_FETCH="true"
      shift
      ;;
    --specs)
      SPECS="$2"
      shift 2
      ;;
    --)
      shift
      E2E_ARGS=("$@")
      break
      ;;
    *)
      echo "Error: unexpected argument '$1' (use -- to pass args to run-e2e.ts)" >&2
      exit 1
      ;;
  esac
done

REPO_ROOT="${POCKETPAL_REPO:-$(pwd)}"
if [[ ! -d "$REPO_ROOT/e2e" ]]; then
  echo "Error: $REPO_ROOT does not look like a pocketpal-ai checkout (no e2e/ dir)." >&2
  echo "Set POCKETPAL_REPO or cd into the worktree/checkout first." >&2
  exit 1
fi

if [[ -z "${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}" ]]; then
  echo "Error: set ANDROID_HOME (or ANDROID_SDK_ROOT) to the Android SDK location." >&2
  exit 1
fi
export ANDROID_HOME="${ANDROID_HOME:-$ANDROID_SDK_ROOT}"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"

# Load per-project env if present
if [[ -f "$REPO_ROOT/e2e/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "$REPO_ROOT/e2e/.env"
  set +a
fi

if [[ "$NO_FETCH" == "false" ]]; then
  if [[ -z "${GITHUB_TOKEN:-${GH_TOKEN:-}}" ]]; then
    echo "Error: GITHUB_TOKEN is required (or use --no-fetch)." >&2
    exit 1
  fi
  if [[ "$E2E_MODE" == "true" ]]; then
    POCKETPAL_REPO="$REPO_ROOT" "$SCRIPT_DIR/fetch-pr-apk.sh" --e2e "$PR_NUMBER"
  else
    POCKETPAL_REPO="$REPO_ROOT" "$SCRIPT_DIR/fetch-pr-apk.sh" "$PR_NUMBER"
  fi
else
  echo "Skipping APK fetch (--no-fetch)"
fi

adb start-server >/dev/null 2>&1 || true

cd "$REPO_ROOT/e2e"

run_one() {
  local extra_spec=("$@")
  echo ""
  echo "Running: yarn e2e:android --skip-build ${extra_spec[*]:-} ${E2E_ARGS[*]:-}"
  yarn e2e:android --skip-build "${extra_spec[@]}" "${E2E_ARGS[@]:-}"
}

OVERALL=0
if [[ -n "$SPECS" ]]; then
  IFS=',' read -r -a SPEC_LIST <<<"$SPECS"
  for SPEC in "${SPEC_LIST[@]}"; do
    SPEC_TRIMMED="$(echo "$SPEC" | xargs)"
    [[ -z "$SPEC_TRIMMED" ]] && continue
    echo ""
    echo "=== Spec: $SPEC_TRIMMED ==="
    if ! run_one --spec "$SPEC_TRIMMED"; then
      echo "Spec '$SPEC_TRIMMED' FAILED (continuing to next spec)" >&2
      OVERALL=1
    fi
  done
else
  run_one || OVERALL=$?
fi

exit "$OVERALL"
