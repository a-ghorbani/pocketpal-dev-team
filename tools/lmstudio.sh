#!/usr/bin/env bash
#
# LM Studio Model Manager
#
# Manages models on LM Studio via its REST API.
# Used before E2E tests to ensure the correct model is loaded.
#
# Usage:
#   ./tools/lmstudio.sh status                    # Show server status and loaded models
#   ./tools/lmstudio.sh list                      # List all downloaded models
#   ./tools/lmstudio.sh loaded                    # List currently loaded models
#   ./tools/lmstudio.sh load <model-key>          # Load a model (unloads others first)
#   ./tools/lmstudio.sh unload [instance-id]      # Unload a specific model or all
#   ./tools/lmstudio.sh ensure <model-key>        # Load model only if not already loaded
#
# Environment:
#   LMSTUDIO_HOST     - Server host (default: 192.168.0.92)
#   LMSTUDIO_PORT     - Server port (default: 1234)
#   LMSTUDIO_API_KEY  - API key (default: lm-studio)
#
# Examples:
#   ./tools/lmstudio.sh status
#   ./tools/lmstudio.sh ensure "qwen/qwen3-1.7b"
#   ./tools/lmstudio.sh load "lmstudio-community/gemma-3-4b-it-GGUF"
#   ./tools/lmstudio.sh list | grep qwen

set -euo pipefail

HOST="${LMSTUDIO_HOST:-192.168.0.92}"
PORT="${LMSTUDIO_PORT:-1234}"
API_KEY="${LMSTUDIO_API_KEY:-${REMOTE_SERVER_API_KEY:-lm-studio}}"
BASE_URL="http://${HOST}:${PORT}"

# --- Helpers ---

curl_get() {
  curl -sS -H "Authorization: Bearer ${API_KEY}" -H "Content-Type: application/json" "$1"
}

curl_post() {
  curl -sS -H "Authorization: Bearer ${API_KEY}" -H "Content-Type: application/json" -d "$2" "$1"
}

check_reachable() {
  if ! curl -sS --connect-timeout 5 "${BASE_URL}/v1/models" -H "Authorization: Bearer ${API_KEY}" > /dev/null 2>&1; then
    echo "Error: LM Studio not reachable at ${BASE_URL}"
    exit 1
  fi
}

# --- Commands ---

cmd_status() {
  check_reachable
  echo "LM Studio: ${BASE_URL}"
  echo ""
  echo "Loaded models:"
  local loaded
  loaded=$(curl_get "${BASE_URL}/v1/models")
  echo "$loaded" | jq -r '.data[] | "  \(.id)"' 2>/dev/null || echo "  (none)"
}

cmd_list() {
  check_reachable
  curl_get "${BASE_URL}/api/v1/models" | jq -r '.models[] | .key' 2>/dev/null || true
}

cmd_loaded() {
  check_reachable
  curl_get "${BASE_URL}/v1/models" | jq -r '.data[] | "\(.id)\t\(.object)"' 2>/dev/null
}

cmd_unload() {
  check_reachable
  local instance_id="${1:-}"

  if [[ -z "$instance_id" ]]; then
    # Unload all
    local ids
    ids=$(curl_get "${BASE_URL}/v1/models" | jq -r '.data[].id' 2>/dev/null || true)
    if [[ -z "$ids" ]]; then
      echo "No models loaded"
      return
    fi
    while IFS= read -r mid; do
      echo "Unloading: $mid"
      curl_post "${BASE_URL}/api/v1/models/unload" "{\"instance_id\": \"$mid\"}" > /dev/null
    done <<< "$ids"
    echo "All models unloaded"
  else
    echo "Unloading: $instance_id"
    curl_post "${BASE_URL}/api/v1/models/unload" "{\"instance_id\": \"$instance_id\"}" > /dev/null
    echo "Done"
  fi
}

cmd_load() {
  local model_key="$1"
  local ctx="${2:-4096}"
  check_reachable

  # Unload all first to free memory
  cmd_unload

  echo "Loading: $model_key (ctx=$ctx)"
  local result
  result=$(curl_post "${BASE_URL}/api/v1/models/load" "{\"model\": \"$model_key\", \"context_length\": $ctx}")

  local load_time
  load_time=$(echo "$result" | jq -r '.load_time_seconds // "?"' 2>/dev/null)
  echo "Loaded in ${load_time}s"

  # Verify
  local loaded_id
  loaded_id=$(curl_get "${BASE_URL}/v1/models" | jq -r '.data[0].id // empty' 2>/dev/null)
  if [[ -n "$loaded_id" ]]; then
    echo "Verified: $loaded_id"
  else
    echo "Warning: model may not have loaded correctly"
    exit 1
  fi
}

cmd_ensure() {
  local model_key="$1"
  check_reachable

  # Check if already loaded
  local loaded_ids
  loaded_ids=$(curl_get "${BASE_URL}/v1/models" | jq -r '.data[].id' 2>/dev/null)

  if echo "$loaded_ids" | grep -qF "$model_key"; then
    echo "Already loaded: $model_key"
    return
  fi

  # Not loaded — load it
  cmd_load "$model_key"
}

# --- Main ---

CMD="${1:-}"
shift || true

case "$CMD" in
  status)
    cmd_status
    ;;
  list)
    cmd_list
    ;;
  loaded)
    cmd_loaded
    ;;
  load)
    if [[ -z "${1:-}" ]]; then
      echo "Usage: $0 load <model-key> [context-length]"
      exit 1
    fi
    cmd_load "$1" "${2:-4096}"
    ;;
  unload)
    cmd_unload "${1:-}"
    ;;
  ensure)
    if [[ -z "${1:-}" ]]; then
      echo "Usage: $0 ensure <model-key>"
      exit 1
    fi
    cmd_ensure "$1"
    ;;
  *)
    echo "Usage: $0 {status|list|loaded|load|unload|ensure} [args]"
    echo ""
    echo "Commands:"
    echo "  status              Show server info and loaded models"
    echo "  list                List all downloaded models"
    echo "  loaded              List currently loaded models"
    echo "  load <model> [ctx]  Unload all, then load model (ctx default: 4096)"
    echo "  unload [id]         Unload specific model or all"
    echo "  ensure <model>      Load model only if not already loaded"
    exit 1
    ;;
esac
