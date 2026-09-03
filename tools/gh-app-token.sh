#!/usr/bin/env bash
set -euo pipefail

# Mint (and cache) a GitHub App installation token for the pocketpal-dev-team
# bot. Prints the token to stdout; `tools/ghb` wraps `gh` with it so public
# writes (PR create, comments, reviews) are attributed to the bot, not to the
# operator's account.
#
# Config: $POCKETPAL_BOT_DIR (default ~/.config/pocketpal-dev-team), holding
#   env                   shell vars: GH_APP_ID (App ID or Client ID, required),
#                         GH_APP_PEM (default: the only *.pem in the dir),
#                         GH_APP_INSTALLATION_ID (default: discovered),
#                         GH_APP_SLUG (default: pocketpal-dev-team)
#   <slug>.<date>.private-key.pem   downloaded from the app's settings page
#
# Cache: ~/.cache/pocketpal-dev-team/gh-app-token.json (mode 600). Installation
# tokens live one hour; a cached one is reused while >5 minutes remain.
#
# Flags:
#   --force   ignore the cache and mint a fresh token
#   --info    print bot login, installation id, repos, expiry (no token)
#   --jwt     print the app JWT instead of an installation token (debugging)
#
# Exit 3 on any configuration/auth problem, with the fix printed to stderr.

umask 077

CONFIG_DIR="${POCKETPAL_BOT_DIR:-$HOME/.config/pocketpal-dev-team}"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/pocketpal-dev-team"
CACHE="$CACHE_DIR/gh-app-token.json"
API="https://api.github.com"

force=0 mode=token
for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    --info)  mode=info ;;
    --jwt)   mode=jwt ;;
    -h|--help) sed -n '3,25p' "$0"; exit 0 ;;
    *) echo "gh-app-token: unknown flag $arg" >&2; exit 2 ;;
  esac
done

fail() { echo "gh-app-token: $*" >&2; exit 3; }

# shellcheck disable=SC1090
[[ -f "$CONFIG_DIR/env" ]] && . "$CONFIG_DIR/env"

APP_ID="${GH_APP_ID:-}"
SLUG="${GH_APP_SLUG:-pocketpal-dev-team}"
PEM="${GH_APP_PEM:-}"
INSTALLATION_ID="${GH_APP_INSTALLATION_ID:-}"

if [[ -z "$PEM" ]]; then
  PEM="$(ls "$CONFIG_DIR"/*.pem 2>/dev/null | head -1 || true)"
fi
[[ -n "$PEM" && -r "$PEM" ]] || fail "no private key: put the app's .pem in $CONFIG_DIR/ or set GH_APP_PEM in $CONFIG_DIR/env"
[[ -n "$APP_ID" ]] || fail "GH_APP_ID is unset: write 'GH_APP_ID=<App ID from https://github.com/settings/apps/$SLUG>' to $CONFIG_DIR/env"

b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }

mint_jwt() {
  local now header payload sig
  now=$(date +%s)
  header=$(printf '{"alg":"RS256","typ":"JWT"}' | b64url)
  payload=$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' $((now - 60)) $((now + 540)) "$APP_ID" | b64url)
  sig=$(printf '%s.%s' "$header" "$payload" | openssl dgst -sha256 -sign "$PEM" | b64url)
  printf '%s.%s.%s' "$header" "$payload" "$sig"
}

api() {  # api <bearer> <method> <path>
  curl -sS -X "$2" -H "Authorization: Bearer $1" -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" "$API$3"
}

if [[ $mode == jwt ]]; then mint_jwt; echo; exit 0; fi

cached_token() {
  [[ $force -eq 0 && -f "$CACHE" ]] || return 1
  local exp now
  exp=$(jq -r '.expires_epoch // 0' "$CACHE" 2>/dev/null) || return 1
  now=$(date +%s)
  [[ $((exp - now)) -gt 300 ]] || return 1
  jq -r '.token // empty' "$CACHE"
}

mint_installation_token() {
  local jwt inst resp
  jwt=$(mint_jwt)
  inst="$INSTALLATION_ID"
  if [[ -z "$inst" ]]; then
    resp=$(api "$jwt" GET /app/installations)
    inst=$(echo "$resp" | jq -r 'if type=="array" then map(.id)|join(" ") else "" end')
    [[ -n "$inst" ]] || fail "app '$SLUG' is not installed anywhere (or GH_APP_ID/pem mismatch): $(echo "$resp" | jq -r '.message // "install it at https://github.com/settings/apps/'"$SLUG"'/installations"')"
    if [[ "$inst" == *" "* ]]; then
      fail "app has several installations ($inst); set GH_APP_INSTALLATION_ID in $CONFIG_DIR/env"
    fi
  fi
  resp=$(api "$jwt" POST "/app/installations/$inst/access_tokens")
  local token
  token=$(echo "$resp" | jq -r '.token // empty')
  [[ -n "$token" ]] || fail "token mint failed for installation $inst: $(echo "$resp" | jq -r '.message // .')"
  mkdir -p "$CACHE_DIR"
  jq -n --arg t "$token" --arg i "$inst" --argjson e $(( $(date +%s) + 3540 )) \
    '{token:$t, installation_id:($i|tonumber), expires_epoch:$e}' > "$CACHE"
  chmod 600 "$CACHE"
  echo "$token"
}

token=$(cached_token || mint_installation_token)

if [[ $mode == token ]]; then echo "$token"; exit 0; fi

# --info
inst=$(jq -r '.installation_id' "$CACHE")
exp=$(jq -r '.expires_epoch' "$CACHE")
repos=$(api "$token" GET /installation/repositories | jq -r '.repositories[]?.full_name' | paste -sd' ' -)
echo "bot login:       ${SLUG}[bot]"
echo "app id:          $APP_ID"
echo "installation id: $inst"
echo "repos:           ${repos:-<none>}"
echo "token expires:   in $(( (exp - $(date +%s)) / 60 )) min (cache: $CACHE)"
