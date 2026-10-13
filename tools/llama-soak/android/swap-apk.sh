#!/usr/bin/env bash
# swap-apk.sh <serial> <apk>: install an APK of any versionCode (also a downgrade) and keep the models:
# move them aside on /sdcard (same volume, a rename), uninstall, install, move them back.
s=$1; apk=$2
F=/sdcard/Android/data/com.pocketpalai.e2e/files; P=/sdcard/Download/pp-soak-park
adb -s "$s" shell "mkdir -p $P && mv $F/*.gguf $F/*.jpg $P/" || exit 2
adb -s "$s" uninstall com.pocketpalai.e2e
bash "$(dirname "$0")/install-apk.sh" "$s" "$apk" || exit 3
adb -s "$s" shell monkey -p com.pocketpalai.e2e -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; sleep 8
adb -s "$s" shell am force-stop com.pocketpalai.e2e
adb -s "$s" shell "mkdir -p $F && mv $P/* $F/ && rmdir $P && ls $F | grep -c gguf"
