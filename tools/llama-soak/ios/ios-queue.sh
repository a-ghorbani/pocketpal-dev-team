#!/usr/bin/env bash
# ios-queue.sh <list>: runs each non-comment line as `python3 ios_run.py <line>` (lines start with
# `soak` or `triage`), one at a time. Log: $LLAMA_SOAK_OUT/soak/queue-ios.log. Needs IOS_UDID.
here="$(cd "$(dirname "$0")" && pwd)"
out=${LLAMA_SOAK_OUT:-$here/../out}
mkdir -p "$out/soak"
log=$out/soak/queue-ios.log
while IFS= read -r line; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  echo "=== $(date +%H:%M:%S) $line" >> "$log"
  python3 "$here/ios_run.py" $line < /dev/null >> "$log" 2>&1
  echo "=== exit $? $(date +%H:%M:%S)" >> "$log"
done < "$1"
echo "=== QUEUE DONE $(date +%H:%M:%S)" >> "$log"
