#!/usr/bin/env bash
# Apply a review-l10n --auto decision to WEBLATE ONLY. DRY-RUN by default; --execute to write.
#
# Human-merge model (option B): the routine NEVER merges or comments on GitHub.
# It applies the Weblate fixes and RECORDS a MERGE/HOLD recommendation for a human,
# who reviews it (and the `main` ruleset's required approval) and merges manually.
#
# Recommendation source:
#   - decision.json mechanical_verdict == HOLD  -> HOLD (non-overridable hard blocker)
#   - else                                       -> --decision=MERGE|HOLD (session's call)
#
# In all cases it applies the full Weblate plan (overwrites + suggestions + comments).
# No gh pr merge, no gh pr comment, no GitHub token needed.
#
# Usage: apply-decision.sh <scratch-dir> [--execute] [--decision=MERGE|HOLD] [--reason=...]
set -euo pipefail

SCRATCH="${1:?scratch dir required}"
shift || true
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

EXECUTE=0
SESSION_DECISION=""
REASON=""
for a in "$@"; do
  case "$a" in
    --execute)    EXECUTE=1 ;;
    --decision=*) SESSION_DECISION="${a#--decision=}" ;;
    --reason=*)   REASON="${a#--reason=}" ;;
  esac
done

DEC="${SCRATCH}/decision.json"
PLAN="${SCRATCH}/plan.json"
[[ -f "${DEC}" ]] || { echo "missing ${DEC}"; exit 2; }

VERDICT=$(node -e "process.stdout.write(require('${DEC}').mechanical_verdict)")
PR=$(node -e "process.stdout.write(String(require('${DEC}').pr ?? ''))")

# Resolve the recommendation (advisory only — nothing merges here).
if [[ "${VERDICT}" == "HOLD" ]]; then
  RECO="HOLD"
  [[ -n "${SESSION_DECISION}" && "${SESSION_DECISION}" != "HOLD" ]] && \
    echo ">> NOTE: session said ${SESSION_DECISION} but a mechanical hard blocker forces HOLD."
else
  if [[ -z "${SESSION_DECISION}" ]]; then
    echo "ERROR: verdict is ADJUDICATE — pass --decision=MERGE|HOLD (the recommendation)." >&2
    exit 3
  fi
  RECO="${SESSION_DECISION}"
fi

DRYFLAG="--dry-run"; [[ "${EXECUTE}" -eq 1 ]] && DRYFLAG=""
echo ">> mechanical_verdict=${VERDICT} recommendation=${RECO} pr=${PR} execute=${EXECUTE}"

# Record the recommendation + reasoning into decision.json (durable, for the human).
node -e '
  const fs = require("fs"); const p = process.argv[1];
  const d = JSON.parse(fs.readFileSync(p, "utf-8"));
  d.recommendation = process.argv[2];
  if (process.argv[3]) d.adjudication = {decision: process.argv[2], reasoning: process.argv[3]};
  fs.writeFileSync(p, JSON.stringify(d, null, 2));
' "${DEC}" "${RECO}" "${REASON}"

# Apply the full Weblate plan (overwrites + suggestions + comments). Weblate only.
echo ">> applying Weblate writes (overwrites + suggestions + comments)"
node "${HERE}/apply-plan.mjs" "${PLAN}" ${DRYFLAG}

# Print the recommendation for the human to act on (no GitHub write).
echo ""
echo "================ HUMAN ACTION ================"
echo "PR #${PR} recommendation: ${RECO}"
[[ -n "${REASON}" ]] && echo "reason: ${REASON}"
WORD="previewed (dry-run)"; [[ "${EXECUTE}" -eq 1 ]] && WORD="applied"
echo "Weblate fixes ${WORD}. A maintainer reviews + merges PR #${PR} manually."
echo "============================================="
echo ">> done (recommendation: ${RECO}; no GitHub merge/comment performed)"
