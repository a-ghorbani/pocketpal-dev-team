#!/bin/bash
# tools/linear.sh
# CLI wrapper for Linear GraphQL API
#
# Usage:
#   ./tools/linear.sh test                    # Test API connection
#   ./tools/linear.sh teams                   # List teams
#   ./tools/linear.sh projects [team_id]      # List projects
#   ./tools/linear.sh issues [project_id]     # List issues in project
#   ./tools/linear.sh create <title> [desc]   # Create issue
#   ./tools/linear.sh update <issue_id> <status>  # Update issue status
#   ./tools/linear.sh query <graphql>         # Run raw GraphQL query

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

if [ -z "$LINEAR_API_KEY" ]; then
    echo "Error: LINEAR_API_KEY not set. Add it to .env" >&2
    exit 1
fi

LINEAR_API="https://api.linear.app/graphql"

# Helper: execute GraphQL query
gql() {
    local query="$1"
    curl -s -X POST "$LINEAR_API" \
        -H "Content-Type: application/json" \
        -H "Authorization: $LINEAR_API_KEY" \
        -d "{\"query\": \"$query\"}"
}

# Helper: execute GraphQL with variables
gql_vars() {
    local query="$1"
    local variables="$2"
    curl -s -X POST "$LINEAR_API" \
        -H "Content-Type: application/json" \
        -H "Authorization: $LINEAR_API_KEY" \
        -d "{\"query\": \"$query\", \"variables\": $variables}"
}

cmd_test() {
    echo "Testing Linear API connection..."
    result=$(gql "{ viewer { id name email } }")
    if echo "$result" | jq -e '.data.viewer.name' > /dev/null 2>&1; then
        name=$(echo "$result" | jq -r '.data.viewer.name')
        email=$(echo "$result" | jq -r '.data.viewer.email')
        echo "Connected as: $name ($email)"
    else
        echo "Error: $(echo "$result" | jq -r '.errors[0].message // "Unknown error"')" >&2
        exit 1
    fi
}

cmd_teams() {
    gql "{ teams { nodes { id name key } } }" | jq '.data.teams.nodes'
}

cmd_projects() {
    local team_id="$1"
    if [ -n "$team_id" ]; then
        gql "{ team(id: \\\"$team_id\\\") { projects { nodes { id name state } } } }" | jq '.data.team.projects.nodes'
    else
        gql "{ projects { nodes { id name state teams { nodes { name } } } } }" | jq '.data.projects.nodes'
    fi
}

cmd_issues() {
    local project_id="$1"
    if [ -n "$project_id" ]; then
        gql "{ project(id: \\\"$project_id\\\") { issues { nodes { id identifier title state { name } priority } } } }" | jq '.data.project.issues.nodes'
    else
        gql "{ issues(first: 20) { nodes { id identifier title state { name } priority } } }" | jq '.data.issues.nodes'
    fi
}

cmd_create() {
    local title="$1"
    local description="${2:-}"
    local team_id="${3:-}"
    local project_id="${4:-}"

    if [ -z "$title" ]; then
        echo "Usage: linear.sh create <title> [description] [team_id] [project_id]" >&2
        exit 1
    fi

    # Escape for JSON
    title=$(echo "$title" | sed 's/"/\\"/g')
    description=$(echo "$description" | sed 's/"/\\"/g')

    local input="{ title: \\\"$title\\\""
    [ -n "$description" ] && input="$input, description: \\\"$description\\\""
    [ -n "$team_id" ] && input="$input, teamId: \\\"$team_id\\\""
    [ -n "$project_id" ] && input="$input, projectId: \\\"$project_id\\\""
    input="$input }"

    gql "mutation { issueCreate(input: $input) { success issue { id identifier title url } } }" | jq '.data.issueCreate'
}

cmd_update() {
    local issue_id="$1"
    local status="$2"

    if [ -z "$issue_id" ] || [ -z "$status" ]; then
        echo "Usage: linear.sh update <issue_id> <state_id>" >&2
        echo "" >&2
        echo "State IDs (founder advisors team):" >&2
        echo "  Backlog:     1f692912-2a27-4e8c-b4e8-77dac00666b2" >&2
        echo "  Todo:        b09856af-f221-495d-8280-cc886cca8255" >&2
        echo "  In Progress: 155b3856-c8ec-41ae-b339-007b7099d51f" >&2
        echo "  Done:        25b69969-5bfa-4885-bf43-f6764a9377d1" >&2
        echo "  Canceled:    33295a98-43af-40c0-9712-649d59f4d0af" >&2
        echo "" >&2
        echo "Use './tools/linear.sh states <team_id>' to fetch current states" >&2
        exit 1
    fi

    gql "mutation { issueUpdate(id: \\\"$issue_id\\\", input: { stateId: \\\"$status\\\" }) { success issue { id identifier title state { name } } } }" | jq '.data.issueUpdate'
}

cmd_states() {
    local team_id="$1"
    if [ -z "$team_id" ]; then
        echo "Usage: linear.sh states <team_id>" >&2
        exit 1
    fi
    gql "{ team(id: \\\"$team_id\\\") { states { nodes { id name type } } } }" | jq '.data.team.states.nodes'
}

cmd_query() {
    local query="$1"
    if [ -z "$query" ]; then
        echo "Usage: linear.sh query '<graphql_query>'" >&2
        exit 1
    fi
    gql "$query" | jq '.'
}

# Main command router
case "${1:-}" in
    test)
        cmd_test
        ;;
    teams)
        cmd_teams
        ;;
    projects)
        cmd_projects "$2"
        ;;
    issues)
        cmd_issues "$2"
        ;;
    create)
        cmd_create "$2" "$3" "$4" "$5"
        ;;
    update)
        cmd_update "$2" "$3"
        ;;
    states)
        cmd_states "$2"
        ;;
    query)
        cmd_query "$2"
        ;;
    *)
        echo "Linear CLI wrapper"
        echo ""
        echo "Usage: ./tools/linear.sh <command> [args]"
        echo ""
        echo "Commands:"
        echo "  test                      Test API connection"
        echo "  teams                     List all teams"
        echo "  projects [team_id]        List projects"
        echo "  issues [project_id]       List issues"
        echo "  states <team_id>          List workflow states for a team"
        echo "  create <title> [desc] [team_id] [project_id]"
        echo "                            Create a new issue"
        echo "  update <issue_id> <state_id>"
        echo "                            Update issue status (run with no args for state IDs)"
        echo "  query '<graphql>'         Run raw GraphQL query"
        ;;
esac
