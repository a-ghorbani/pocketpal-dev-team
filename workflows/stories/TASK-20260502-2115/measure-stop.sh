#!/usr/bin/env bash
# measure-stop.sh — drive PocketPal through one stop-button scenario
# via adb, capturing the run-finished metrics log and the Hermes
# .cpuprofile artefact. No Appium needed.
#
# Prerequisites:
#  - PocketPal debug build installed (STREAM_DEBUG must be true → __DEV__)
#  - A model already loaded on the chat screen (local or remote)
#  - App in foreground on the chat screen, input empty
#  - adb in $PATH; exactly one device attached (or ANDROID_SERIAL set)
#
# Usage:
#   ./measure-stop.sh                          # default prompt + 5s wait
#   ./measure-stop.sh "your prompt here"
#   WAIT=3 ./measure-stop.sh                   # tap stop 3s after send
#   ./measure-stop.sh --help

set -euo pipefail

PKG="${PKG:-com.pocketpalai}"
WAIT="${WAIT:-5}"
PROMPT="${1:-Write a very long detailed story about humanity colonising Mars over the next two hundred years, with vivid characters, multiple subplots, and lots of atmospheric description. Take your time and include many paragraphs.}"

if [[ "$PROMPT" == "--help" || "$PROMPT" == "-h" ]]; then
  sed -n '2,18p' "$0"
  exit 0
fi

OUT="measure-output-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
echo "==> Out:    $OUT"

# --- Sanity checks -----------------------------------------------------------

if ! command -v adb >/dev/null; then
  echo "ERROR: adb not in PATH"; exit 1
fi

DEVICES=$(adb devices | awk 'NR>1 && $2=="device"{c++} END{print c+0}')
if [[ "$DEVICES" -eq 0 ]]; then
  echo "ERROR: no adb device attached"; exit 1
elif [[ "$DEVICES" -gt 1 && -z "${ANDROID_SERIAL:-}" ]]; then
  echo "ERROR: multiple devices attached, set ANDROID_SERIAL"; exit 1
fi

MODEL=$(adb shell getprop ro.product.model | tr -d '\r')
PID=$(adb shell pidof "$PKG" | tr -d '\r' || true)
if [[ -z "$PID" ]]; then
  echo "ERROR: $PKG not running. Open the app and reach the chat screen first."
  exit 1
fi
echo "==> Device: $MODEL (pid $PID)"

# --- Helpers -----------------------------------------------------------------

dump_ui() {
  local name="$1"
  adb shell uiautomator dump /sdcard/ui.xml >/dev/null
  adb pull /sdcard/ui.xml "$OUT/$name.xml" >/dev/null 2>&1
}

# Read center coordinates of the first element whose resource-id matches
# the given testID. Echoes "X Y" or returns 1 if not found.
find_center() {
  local xml="$1" testid="$2"
  python3 - "$xml" "$testid" <<'PY'
import re, sys
xml_path, testid = sys.argv[1], sys.argv[2]
content = open(xml_path).read()
# Match resource-id on the same node as bounds, in either attribute order.
pat_a = re.compile(rf'resource-id="{re.escape(testid)}"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
pat_b = re.compile(rf'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*?resource-id="{re.escape(testid)}"')
m = pat_a.search(content) or pat_b.search(content)
if not m:
    sys.exit(1)
x1, y1, x2, y2 = map(int, m.groups())
print((x1 + x2) // 2, (y1 + y2) // 2)
PY
}

tap_id() {
  local name="$1" testid="$2" xml="$3"
  local coords
  if ! coords=$(find_center "$xml" "$testid"); then
    echo "ERROR: testID '$testid' not found in $xml"
    return 1
  fi
  echo "    tap $name @ $coords"
  adb shell input tap $coords
}

# --- Phase 1: dump UI, locate input + send ----------------------------------

echo "==> Dump UI for input/send coords"
dump_ui pre-send

INPUT_XY=$(find_center "$OUT/pre-send.xml" chat-input) || {
  echo "ERROR: 'chat-input' not found. Is the chat screen actually open?"
  exit 1
}
SEND_XY=$(find_center "$OUT/pre-send.xml" send-button) || {
  echo "ERROR: 'send-button' not found (input may already be in send-disabled state)"
  exit 1
}
echo "    input  @ $INPUT_XY"
echo "    send   @ $SEND_XY"

# --- Phase 2: clear logcat, focus input, type, send -------------------------

echo "==> Clear logcat + start capture"
adb logcat -c
adb logcat -v time ReactNativeJS:I RNLlama:I '*:S' > "$OUT/logcat.txt" &
LOGCAT_PID=$!
trap 'kill $LOGCAT_PID 2>/dev/null || true' EXIT

# Focus the input, then send the prompt via `adb input text`. The keyboard
# input goes through the IME so multi-word prompts work; spaces must be
# escaped via %s.
echo "==> Focus input"
adb shell input tap $INPUT_XY
sleep 0.3

# Clear any stale text from a previous run that didn't actually Send.
# Move caret to end, then send a batch of KEYCODE_DEL (67). Bundling
# multiple keycodes in one adb call is much faster than looping.
echo "==> Clear existing input"
adb shell input keyevent 123  # KEYCODE_MOVE_END
DEL_BURST=$(printf '67 %.0s' {1..400})
adb shell input keyevent $DEL_BURST
sleep 0.3

echo "==> Type prompt ($(echo "$PROMPT" | wc -c) chars)"
ESCAPED=$(printf '%s' "$PROMPT" | sed -e 's/ /%s/g' -e "s/'/\\\\'/g")
adb shell input text "$ESCAPED"
sleep 0.4

# Dismiss the IME so layout returns to its pre-keyboard state and the
# send-button coords saved at startup are valid again. (Typing brings
# up the keyboard; the SendButton stays anchored to the input row but
# its absolute y on screen has shifted up by the keyboard's height.)
echo "==> Dismiss keyboard"
adb shell input keyevent 4   # KEYCODE_BACK
sleep 0.5

# Re-dump UI to get fresh send-button coords (defensive — handles
# layouts where dismissing the keyboard isn't enough).
dump_ui after-type
if FRESH_SEND_XY=$(find_center "$OUT/after-type.xml" send-button); then
  SEND_XY="$FRESH_SEND_XY"
  echo "    send (refreshed) @ $SEND_XY"
fi

echo "==> Tap Send"
adb shell input tap $SEND_XY
SEND_TS=$(date +%s)

# --- Phase 3: wait, dump UI for stop coords (it's now visible), tap stop ----

echo "==> Wait ${WAIT}s for streaming to be in steady state"
sleep "$WAIT"

echo "==> Dump UI for stop coords"
dump_ui pre-stop

# In some builds send-button and stop-button share the same on-screen slot.
# If stop-button isn't found, fall back to the send-button slot.
if STOP_XY=$(find_center "$OUT/pre-stop.xml" stop-button); then
  echo "    stop   @ $STOP_XY (from stop-button testID)"
else
  STOP_XY="$SEND_XY"
  echo "    stop   @ $STOP_XY (fallback: same slot as send-button)"
fi

echo "==> Tap Stop"
adb shell input tap $STOP_XY

# --- Phase 4: wait for run-finished, then pull artefacts --------------------

echo "==> Wait for [stream-debug] run-finished in logcat (max 180s)"
TIMEOUT=$((SECONDS + 180))
while [[ $SECONDS -lt $TIMEOUT ]]; do
  if grep -q "stream-debug.*run-finished" "$OUT/logcat.txt"; then
    echo "    seen at $(date +%H:%M:%S)"
    break
  fi
  sleep 0.5
done
sleep 1  # let the profile-saved log line land
kill $LOGCAT_PID 2>/dev/null || true

# --- Phase 5: pull the cpuprofile -------------------------------------------

PROFILE_LINE=$(grep -E "stream-debug.*profile saved" "$OUT/logcat.txt" | tail -1 || true)
if [[ -n "$PROFILE_LINE" ]]; then
  DEVICE_PROFILE=$(echo "$PROFILE_LINE" | grep -oE '/[^ )]*\.cpuprofile' | tail -1)
  if [[ -n "$DEVICE_PROFILE" ]]; then
    BASENAME=$(basename "$DEVICE_PROFILE")
    echo "==> Pull profile: $DEVICE_PROFILE"
    if adb exec-out run-as "$PKG" cat "files/$BASENAME" > "$OUT/$BASENAME" 2>/dev/null \
       && [[ -s "$OUT/$BASENAME" ]]; then
      echo "    saved → $OUT/$BASENAME ($(du -h "$OUT/$BASENAME" | cut -f1))"
    else
      echo "    (could not pull via run-as — try manually: adb exec-out run-as $PKG cat files/$BASENAME > $OUT/$BASENAME)"
    fi
  fi
else
  echo "WARNING: no 'profile saved' line in logcat — STREAM_DEBUG off, or run never finished"
fi

# --- Phase 6: extract the two dump-metrics lines for easy reading -----------

grep -E "stream-debug.*(stop-pressed|run-finished|PendingIndicatorView)" "$OUT/logcat.txt" \
  > "$OUT/dump.txt" || true

echo
echo "==> Done."
echo "    $OUT/dump.txt    — stream-debug snapshot lines"
echo "    $OUT/logcat.txt  — full filtered logcat"
echo "    $OUT/*.cpuprofile — Hermes profile (open in Chrome DevTools)"
echo "    $OUT/pre-*.xml   — UI dumps for diagnostics"
