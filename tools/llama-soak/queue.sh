#!/usr/bin/env bash
# queue.sh <serial> <list> [expect-sha]: runs each non-comment line of <list> as
# `run.py --mode soak --serial <serial> --expect-sha <sha> <line>`, one at a time.
# Lines are soak flags, or --scenario lines for triage. The sha defaults to $LLAMA_SOAK_APK_SHA.
# Log: $LLAMA_SOAK_OUT/soak/queue-<serial>.log (default out/ next to this script).
here="$(cd "$(dirname "$0")" && pwd)"
serial=$1; list=$(readlink -f "$2"); sha=${3:-${LLAMA_SOAK_APK_SHA:-}}
out=${LLAMA_SOAK_OUT:-$here/out}
mkdir -p "$out/soak"
log=$out/soak/queue-$serial.log
[ -z "$sha" ] && echo "WARNING: no expected APK sha; runs will not check the installed build" | tee -a "$log"
while IFS= read -r line; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  echo "=== $(date +%H:%M:%S) $line" >> "$log"
  timeout 10800 python3 "$here/run.py" --mode soak --serial "$serial" --expect-sha "$sha" $line < /dev/null >> "$log" 2>&1
  echo "=== exit $? $(date +%H:%M:%S)" >> "$log"
done < "$list"
echo "=== QUEUE DONE $(date +%H:%M:%S) $list" >> "$log"
