#!/bin/bash
# tools/plane.sh
# CLI wrapper for the Plane.so REST API (https://api.plane.so)
#
# Replaces tools/linear.sh as the crew's action tracker. Same friendly verbs.
#
# Auth:   X-API-Key header, PLANE_TOKEN from .env (secret).
# Config: workspace + project map from tools/plane.config (copy the .example,
#         fill in your IDs). No connection values are hardcoded here.
# Model:  Workspace -> Project -> Work Item (Plane has no "team" layer).
#
# Usage:
#   ./tools/plane.sh test                              # Verify API connection
#   ./tools/plane.sh projects                          # List projects
#   ./tools/plane.sh states <project>                  # List workflow states
#   ./tools/plane.sh labels <project>                  # List labels
#   ./tools/plane.sh issues [project]                  # List work items (all, or one project)
#   ./tools/plane.sh create "<title>" "<desc>" [project] [state] [priority]
#   ./tools/plane.sh update <project> <work_item_id> <state>
#   ./tools/plane.sh comment <project> <work_item_id> "<body>"
#   ./tools/plane.sh get|post|patch <path> [json]      # Raw REST against API base
#
#   <project> accepts a name ("Advisory Actions"), code (ADV), or UUID.
#   <state>   accepts a name: Backlog | Todo | In Progress | In Review | Done | Cancelled
#   <priority>accepts: urgent | high | medium | low | none   (default none)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
[ -f "$PROJECT_ROOT/.env" ] && source "$PROJECT_ROOT/.env"
[ -z "$PLANE_TOKEN" ] && { echo "Error: PLANE_TOKEN not set in .env" >&2; exit 1; }

# Connection config (workspace + project map) — copy tools/plane.config.example
CONFIG="$SCRIPT_DIR/plane.config"
if [ ! -f "$CONFIG" ]; then
  echo "Error: $CONFIG not found. Copy tools/plane.config.example to tools/plane.config and fill in your workspace + project IDs." >&2
  exit 1
fi
source "$CONFIG"

PLANE_API="${PLANE_API:-https://api.plane.so}"
WS="${PLANE_WORKSPACE:?PLANE_WORKSPACE not set in tools/plane.config}"

# Build lookup maps from PLANE_PROJECTS entries ("CODE|Name|UUID")
declare -A PROJ_ID=()    # name -> uuid
declare -A CODE_ID=()    # code -> uuid
declare -A CODE_FOR=()   # uuid -> code
for _entry in "${PLANE_PROJECTS[@]}"; do
  IFS='|' read -r _code _name _uuid <<< "$_entry"
  PROJ_ID["$_name"]="$_uuid"; CODE_ID["$_code"]="$_uuid"; CODE_FOR["$_uuid"]="$_code"
done

resolve_project() {  # name|code|uuid -> uuid
  local p="$1" up
  if [ -n "${CODE_ID[$p]:-}" ]; then echo "${CODE_ID[$p]}"; return; fi
  if [ -n "${PROJ_ID[$p]:-}" ]; then echo "${PROJ_ID[$p]}"; return; fi
  up=$(echo "$p" | tr '[:lower:]' '[:upper:]')
  if [ -n "${CODE_ID[$up]:-}" ]; then echo "${CODE_ID[$up]}"; return; fi
  echo "$p"  # assume it's already a UUID
}

api() {  # method path [body]
  local method="$1" path="$2" body="${3:-}"
  if [ -n "$body" ]; then
    curl -s -X "$method" -H "X-API-Key: $PLANE_TOKEN" -H "Content-Type: application/json" \
      -d "$body" "$PLANE_API$path"
  else
    curl -s -X "$method" -H "X-API-Key: $PLANE_TOKEN" "$PLANE_API$path"
  fi
}

# state name -> state UUID for a given project (queries API)
state_id() {  # pid name
  local pid="$1" name="$2"
  api GET "/api/v1/workspaces/$WS/projects/$pid/states/" \
    | jq -r --arg n "$name" '(.results // .)[] | select(.name|ascii_downcase==($n|ascii_downcase)) | .id' | head -1
}

# id->name state map for a project (compact json)
states_map() {  # pid
  api GET "/api/v1/workspaces/$WS/projects/$pid/states/" 2>/dev/null
}

list_issues_for() {  # pid — paginates over all work items
  local pid="$1" code="${CODE_FOR[$1]:-PRJ}"
  local smap cursor page
  smap=$(api GET "/api/v1/workspaces/$WS/projects/$pid/states/" \
        | jq -c '[ (.results // .)[] | {(.id): .name} ] | add')
  cursor=""
  while :; do
    local q="/api/v1/workspaces/$WS/projects/$pid/work-items/?per_page=100"
    [ -n "$cursor" ] && q="$q&cursor=$cursor"
    page=$(api GET "$q")
    echo "$page" | jq -r --argjson s "$smap" --arg code "$code" \
      '(.results // .)[] | "\($code)-\(.sequence_id)\t[\($s[.state] // "—")]\t(\(.priority))\t\(.name)"'
    if [ "$(echo "$page" | jq -r '.next_page_results // false')" = "true" ]; then
      cursor=$(echo "$page" | jq -r '.next_cursor')
    else
      break
    fi
  done
}

# find a work item's UUID by its <CODE>-<seq> reference (paginates)
find_wid() {  # pid seq
  local pid="$1" seq="$2" cursor="" page hit
  while :; do
    local q="/api/v1/workspaces/$WS/projects/$pid/work-items/?per_page=100"
    [ -n "$cursor" ] && q="$q&cursor=$cursor"
    page=$(api GET "$q")
    hit=$(echo "$page" | jq -r --argjson n "$seq" '(.results // .)[] | select(.sequence_id==$n) | .id' | head -1)
    [ -n "$hit" ] && { echo "$hit"; return; }
    if [ "$(echo "$page" | jq -r '.next_page_results // false')" = "true" ]; then
      cursor=$(echo "$page" | jq -r '.next_cursor')
    else return; fi
  done
}

cmd_show() {  # <CODE>-<seq>, e.g. POC-22
  local ref="$1"; [ -z "$ref" ] && { echo "Usage: plane.sh show <CODE-N>  (e.g. POC-22)" >&2; exit 1; }
  local code="${ref%%-*}" seq="${ref##*-}" pid wid item smap
  pid=$(resolve_project "$code")
  wid=$(find_wid "$pid" "$seq")
  [ -z "$wid" ] && { echo "Not found: $ref" >&2; exit 1; }
  item=$(api GET "/api/v1/workspaces/$WS/projects/$pid/work-items/$wid/")
  smap=$(api GET "/api/v1/workspaces/$WS/projects/$pid/states/" | jq -c '[ (.results // .)[] | {(.id): .name} ] | add')
  echo "$item" | jq -r --argjson s "$smap" --arg ref "$ref" '
    "Identifier: \($ref)",
    "Title:      \(.name)",
    "State:      \($s[.state] // "—")",
    "Priority:   \(.priority)",
    "ID:         \(.id)",
    "",
    "Description:",
    (.description_html // "" | gsub("<[^>]+>";"") )'
}

cmd_test() {
  echo "Testing Plane API connection (workspace: $WS)..."
  local me; me=$(api GET "/api/v1/users/me/")
  if echo "$me" | jq -e '.email' >/dev/null 2>&1; then
    echo "Connected as: $(echo "$me" | jq -r '.display_name') ($(echo "$me" | jq -r '.email'))"
    echo "Projects:"
    api GET "/api/v1/workspaces/$WS/projects/" | jq -r '(.results // .)[] | "  \(.identifier)  \(.name)  \(.id)"'
  else
    echo "Error: $(echo "$me" | jq -r '.error // .detail // "unknown"')" >&2; exit 1
  fi
}

cmd_create() {
  local title="$1" desc="${2:-}" project="${3:-Advisory Actions}" state="${4:-Backlog}" prio="${5:-none}"
  [ -z "$title" ] && { echo "Usage: plane.sh create \"<title>\" \"<desc>\" [project] [state] [priority]" >&2; exit 1; }
  local pid sid; pid=$(resolve_project "$project"); sid=$(state_id "$pid" "$state")
  # plain text/markdown desc -> minimal HTML (preserve line breaks)
  local body
  body=$(jq -n --arg name "$title" --arg desc "$desc" --arg sid "$sid" --arg prio "$prio" \
    '{name:$name, priority:$prio}
     + (if $desc=="" then {} else {description_html: ("<p>" + ($desc|gsub("\n";"<br>")) + "</p>")} end)
     + (if $sid=="" then {} else {state:$sid} end)')
  api POST "/api/v1/workspaces/$WS/projects/$pid/work-items/" "$body" \
    | jq '{id, sequence_id, name, priority}'
}

cmd_update() {
  local project="$1" wid="$2" state="$3"
  [ -z "$project" ] || [ -z "$wid" ] || [ -z "$state" ] && {
    echo "Usage: plane.sh update <project> <work_item_id> <state>" >&2; exit 1; }
  local pid sid; pid=$(resolve_project "$project"); sid=$(state_id "$pid" "$state")
  [ -z "$sid" ] && { echo "Error: state '$state' not found in project" >&2; exit 1; }
  api PATCH "/api/v1/workspaces/$WS/projects/$pid/work-items/$wid/" "$(jq -n --arg s "$sid" '{state:$s}')" \
    | jq '{id, sequence_id, name, state}'
}

cmd_comment() {
  local project="$1" wid="$2" body="$3"
  [ -z "$project" ] || [ -z "$wid" ] || [ -z "$body" ] && {
    echo "Usage: plane.sh comment <project> <work_item_id> \"<body>\"" >&2; exit 1; }
  local pid; pid=$(resolve_project "$project")
  api POST "/api/v1/workspaces/$WS/projects/$pid/work-items/$wid/comments/" \
    "$(jq -n --arg b "$body" '{comment_html: ("<p>" + ($b|gsub("\n";"<br>")) + "</p>")}')" \
    | jq '{id, created_at}'
}

case "${1:-}" in
  test)     cmd_test ;;
  projects) api GET "/api/v1/workspaces/$WS/projects/" | jq -r '(.results // .)[] | "\(.identifier)\t\(.name)\t\(.id)"' ;;
  states)   pid=$(resolve_project "$2"); api GET "/api/v1/workspaces/$WS/projects/$pid/states/" | jq -r '(.results // .)[] | "\(.name)\t\(.group)\t\(.id)"' ;;
  labels)   pid=$(resolve_project "$2"); api GET "/api/v1/workspaces/$WS/projects/$pid/labels/" | jq -r '(.results // .)[] | "\(.name)\t\(.id)"' ;;
  show)     cmd_show "$2" ;;
  issues)
    if [ -n "$2" ]; then list_issues_for "$(resolve_project "$2")"
    else for _entry in "${PLANE_PROJECTS[@]}"; do
           IFS='|' read -r _code _name _uuid <<< "$_entry"
           echo "## $_name"; list_issues_for "$_uuid"; echo
         done
    fi ;;
  create)   cmd_create "$2" "$3" "$4" "$5" "$6" ;;
  update)   cmd_update "$2" "$3" "$4" ;;
  comment)  cmd_comment "$2" "$3" "$4" ;;
  delete)   pid=$(resolve_project "$2"); api DELETE "/api/v1/workspaces/$WS/projects/$pid/work-items/$3/" >/dev/null; echo "deleted $3" ;;
  get)      api GET "$2" | jq '.' ;;
  post)     api POST "$2" "$3" | jq '.' ;;
  patch)    api PATCH "$2" "$3" | jq '.' ;;
  *)
    cat <<'EOF'
Plane CLI wrapper (action tracker for the advisory crew)

Usage: ./tools/plane.sh <command> [args]

  test                          Verify API connection + list projects
  projects                      List projects (identifier, name, id)
  states <project>              List workflow states for a project
  labels <project>              List labels for a project
  issues [project]              List work items (all projects, or one)
  show <CODE-N>                 Show one work item by reference (e.g. POC-22)
  create "<title>" "<desc>" [project] [state] [priority]
                                Create a work item (default: Advisory Actions / Backlog / none)
  update <project> <work_item_id> <state>
                                Move a work item to a new state
  comment <project> <work_item_id> "<body>"
                                Add a comment to a work item
  get|post|patch <path> [json]  Raw REST call against the API base

  <project>: name ("Advisory Actions"), code (POC|PAL|ADV), or UUID
  <state>:   Backlog | Todo | In Progress | In Review | Done | Cancelled
  <priority>:urgent | high | medium | low | none
EOF
    ;;
esac
