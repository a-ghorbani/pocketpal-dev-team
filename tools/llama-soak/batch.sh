#!/usr/bin/env bash
# batch.sh <list>: sequential run.py matrix attempts, one line per run: "attempt|run.py flags".
# Skips attempts whose <out>/runs/<attempt>.json exists. Set ANDROID_SERIAL or pass --serial in the flags.
here="$(cd "$(dirname "$0")" && pwd)"
out=${LLAMA_SOAK_OUT:-$here/out}
mkdir -p "$out/runs"
while IFS='|' read -r att rest; do
  [ -z "$att" ] && continue
  case "$att" in \#*) continue;; esac
  [ -f "$out/runs/$att.json" ] && { echo "SKIP $att"; continue; }
  echo "RUN $att $(date +%T)"
  eval timeout 7200 python3 "$here/run.py" --attempt "$att" $rest > "$out/runs/$att.out" 2>&1 < /dev/null
  echo "DONE $att rc=$? $(date +%T)"
done < "$1"
echo BATCH_END
