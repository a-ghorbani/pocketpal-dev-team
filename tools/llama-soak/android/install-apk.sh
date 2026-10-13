#!/usr/bin/env bash
# install-apk.sh <serial> <apk> [--fresh]: wake, run the MIUI install watcher on Xiaomi, install,
# print the installed versionCode and sha256 (pass that sha as --expect-sha / $LLAMA_SOAK_APK_SHA).
# --fresh uninstalls the e2e package first (this deletes the models in its files dir).
s=$1; apk=$2
adb -s "$s" shell input keyevent KEYCODE_WAKEUP; adb -s "$s" shell wm dismiss-keyguard
[ "$3" = "--fresh" ] && adb -s "$s" uninstall com.pocketpalai.e2e
w=""
if [ "$(adb -s "$s" shell getprop ro.product.manufacturer | tr -d '\r')" = "Xiaomi" ]; then
  "$(dirname "$0")/../../miui-install-watcher.sh" "$s" > /dev/null 2>&1 & w=$!
fi
adb -s "$s" install -r "$apk"; rc=$?
[ -n "$w" ] && kill $w
adb -s "$s" shell dumpsys package com.pocketpalai.e2e | grep -m1 versionCode
p=$(adb -s "$s" shell pm path com.pocketpalai.e2e | cut -d: -f2 | tr -d '\r'); adb -s "$s" shell sha256sum "$p"
exit $rc
