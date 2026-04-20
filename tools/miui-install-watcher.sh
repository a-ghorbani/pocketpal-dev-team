#!/usr/bin/env bash
# Auto-accept MIUI "Install via USB" dialogs on Xiaomi devices.
# Watches for the com.miui.securitycenter install dialog, checks
# "Remember my choice", and taps "Install".
#
# Usage: ./miui-install-watcher.sh [device_serial]
# Run in background while executing e2e tests.

set -u
DEVICE="${1:-}"
ADB_CMD="adb"
[[ -n "$DEVICE" ]] && ADB_CMD="adb -s $DEVICE"

echo "MIUI Install Watcher started (device: ${DEVICE:-all})"
echo "Press Ctrl+C to stop"

while true; do
  FOCUS=$($ADB_CMD shell dumpsys window 2>/dev/null | grep "mCurrentFocus" || true)

  if echo "$FOCUS" | grep -q "com.miui.securitycenter"; then
    echo "$(date '+%H:%M:%S') Install dialog detected"

    $ADB_CMD shell uiautomator dump /sdcard/_miui_ui.xml 2>/dev/null
    CHECKED=$($ADB_CMD shell cat /sdcard/_miui_ui.xml 2>/dev/null | grep -o 'resource-id="com.miui.securitycenter:id/do_not_ask_checkbox"[^/]*checked="true"' || true)

    if [[ -z "$CHECKED" ]]; then
      BOUNDS=$($ADB_CMD shell cat /sdcard/_miui_ui.xml 2>/dev/null | grep -o 'resource-id="com.miui.securitycenter:id/do_not_ask_checkbox"[^/]*bounds="\[[0-9]*,[0-9]*\]\[[0-9]*,[0-9]*\]"' | grep -o 'bounds="\[[0-9]*,[0-9]*\]\[[0-9]*,[0-9]*\]"' || true)
      if [[ -n "$BOUNDS" ]]; then
        X1=$(echo "$BOUNDS" | grep -o '\[[0-9]*,' | head -1 | tr -d '[,')
        Y1=$(echo "$BOUNDS" | grep -o ',[0-9]*\]' | head -1 | tr -d ',]')
        X2=$(echo "$BOUNDS" | grep -o '\[[0-9]*,' | tail -1 | tr -d '[,')
        Y2=$(echo "$BOUNDS" | grep -o ',[0-9]*\]' | tail -1 | tr -d ',]')
        CX=$(( (X1 + X2) / 2 ))
        CY=$(( (Y1 + Y2) / 2 ))
        $ADB_CMD shell input tap "$CX" "$CY"
        echo "  Checked 'Remember my choice'"
        sleep 0.5
      fi
    fi

    $ADB_CMD shell uiautomator dump /sdcard/_miui_ui.xml 2>/dev/null
    BOUNDS=$($ADB_CMD shell cat /sdcard/_miui_ui.xml 2>/dev/null | grep -o 'resource-id="android:id/button2"[^/]*bounds="\[[0-9]*,[0-9]*\]\[[0-9]*,[0-9]*\]"' | grep -o 'bounds="\[[0-9]*,[0-9]*\]\[[0-9]*,[0-9]*\]"' || true)
    if [[ -n "$BOUNDS" ]]; then
      X1=$(echo "$BOUNDS" | grep -o '\[[0-9]*,' | head -1 | tr -d '[,')
      Y1=$(echo "$BOUNDS" | grep -o ',[0-9]*\]' | head -1 | tr -d ',]')
      X2=$(echo "$BOUNDS" | grep -o '\[[0-9]*,' | tail -1 | tr -d '[,')
      Y2=$(echo "$BOUNDS" | grep -o ',[0-9]*\]' | tail -1 | tr -d ',]')
      CX=$(( (X1 + X2) / 2 ))
      CY=$(( (Y1 + Y2) / 2 ))
      $ADB_CMD shell input tap "$CX" "$CY"
      echo "  Tapped 'Install'"
    fi

    sleep 2
  else
    sleep 1
  fi
done
