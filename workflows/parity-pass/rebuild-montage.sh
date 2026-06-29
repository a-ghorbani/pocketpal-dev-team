#!/usr/bin/env bash
# Rebuild one or more parity montages from figma/ renders + device captures.
# Usage: ./rebuild-montage.sh <screen-key> [<screen-key> ...]
# Run from workflows/parity-pass/. Figma renders already in ./figma/ ; captures in ../stories/redesign-captures/.
set -euo pipefail
cd "$(dirname "$0")"
CAP=../stories/redesign-captures

# screen-key -> "figma-prefix capture-filename(no .png)"
declare -A MAP=(
  [home]="home home-empty-with-pals"
  [chat-conversation]="chat-conversation chat-conversation"
  [chat-model-picker]="chat-model-picker chat-model-picker"
  [models-ready]="models-ready models-screen-ready-tab"
  [models-explore]="models-explore models-screen-explore-tab"
  [model-settings]="model-settings model-settings-sheet"
  [explore-pals]="explore-pals explore-pals-tab"
  [explore-models-stub]="_no-source explore-models-stub"
  [my-pals-downloaded]="my-pals my-pals-downloaded"
  [my-pals-created]="my-pals my-pals-created-tab"
  [create-pal-general]="create-pal-general-roleplay create-pal-form-general"
  [create-pal-generation]="create-pal-generation create-pal-form-generation"
  [settings-launcher]="settings-launcher settings-launcher"
  [settings-preferences]="settings-preferences settings-preferences"
  [settings-app]="settings-app settings-app-settings"
  [settings-about]="settings-about settings-about"
  [search-prompt]="search-prompt search-prompt"
  [search-0-results]="search-0-results search-0-results"
)

build() {
  local key="$1"; local spec="${MAP[$key]:-}"
  [ -z "$spec" ] && { echo "unknown key: $key"; return 1; }
  local fig cap; read -r fig cap <<<"$spec"
  # pick capture file: prefer plain name, fall back to __BLOCKED
  pick() { local p="$1/${cap}.png"; [ -f "$p" ] && echo "$p" || echo "$1/${cap}__BLOCKED.png"; }
  local fl="figma/${fig}-light.png" fd="figma/${fig}-dark.png"
  [ "$fig" = "_no-source" ] && { fl="figma/_no-source.png"; fd="figma/_no-source.png"; }
  magick montage \
    -label "Figma light"   "$fl" \
    -label "iOS light"     "$(pick $CAP/ios/light)" \
    -label "Android light" "$(pick $CAP/android/light)" \
    -label "Figma dark"    "$fd" \
    -label "iOS dark"      "$(pick $CAP/ios/dark)" \
    -label "Android dark"  "$(pick $CAP/android/dark)" \
    -tile 3x2 -geometry x1100+8+8 -background white -fill black -pointsize 22 \
    "montages/${key}.png"
  echo "rebuilt montages/${key}.png"
}

[ $# -eq 0 ] && { echo "usage: $0 <screen-key> [...]"; echo "keys: ${!MAP[*]}"; exit 1; }
for k in "$@"; do build "$k"; done
