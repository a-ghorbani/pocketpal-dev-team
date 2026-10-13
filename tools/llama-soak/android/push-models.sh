#!/usr/bin/env bash
# push-models.sh <serial> <file...>: push models/images (src or src=dstname) into the e2e files dir,
# skipping files already there with the same size. Bare names resolve in $LLAMA_SOAK_MODELS
# (default ~/.cache/pocketpal-soak-models).
s=$1; shift
C=${LLAMA_SOAK_MODELS:-$HOME/.cache/pocketpal-soak-models}
F=/sdcard/Android/data/com.pocketpalai.e2e/files
adb -s "$s" shell monkey -p com.pocketpalai.e2e -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; sleep 8
adb -s "$s" shell am force-stop com.pocketpalai.e2e
adb -s "$s" shell mkdir -p $F
have=$(adb -s "$s" shell ls -l $F)
for m in "$@"; do
  dst=${m#*=}; src=${m%%=*}; [ "$dst" = "$m" ] && dst=$(basename "$src")
  [ -e "$C/$src" ] && src=$C/$src
  src=$(readlink -f "$src"); size=$(stat -c %s "$src")
  if echo "$have" | grep -q " $size .* $dst\$"; then echo "have $dst"; continue; fi
  adb -s "$s" push "$src" $F/$dst | tail -n 1
done
echo PUSH-DONE "$s"
