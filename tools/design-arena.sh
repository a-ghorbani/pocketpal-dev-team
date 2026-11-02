#!/usr/bin/env bash
# Design arena: independent design candidates from several models in tmux lanes,
# then a judge from another provider. The architect merges them (pipeline.md, Design exploration).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="${DESIGN_ARENA_CONF:-$ROOT/config/design-arena.conf}"
LEDGER_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/pocketpal-dev-team/design-arena"
GB_PER_LANE=10

usage() {
  cat <<'EOF'
Usage: tools/design-arena.sh run <STORY_DIR> [--ref <ref>] [--timeout <minutes>]
       tools/design-arena.sh status <STORY_DIR>
       tools/design-arena.sh cleanup <STORY_DIR>

run      Launch one lane per runner in config/design-arena.conf, wait for their
         candidates, run the judge, then stop the lanes and remove their worktrees.
         Needs <STORY_DIR>/handoff.txt (intake's handoff block).
         Exit: 0 judged; 1 fewer than two candidates; 2 usage or environment;
               3 candidates ready but the judge failed.
status   Show each lane's state.
cleanup  Stop lanes and remove worktrees left by an interrupted run.
EOF
}

die() { echo "design-arena: $*" >&2; exit 2; }
log() { echo "design-arena: $*"; }

[[ $# -ge 2 ]] || { usage; exit 2; }
CMD="$1"; STORY_DIR="$(cd "$2" 2>/dev/null && pwd)" || die "no story dir: $2"; shift 2
REF="origin/main"; TIMEOUT_MIN=180
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) REF="$2"; shift 2 ;;
    --timeout) TIMEOUT_MIN="$2"; shift 2 ;;
    *) usage; exit 2 ;;
  esac
done

TASK_ID="$(basename "$STORY_DIR")"
CAND="$STORY_DIR/candidates"
LEDGER="$LEDGER_DIR/$TASK_ID"

lanes() { grep -E "^$1[[:space:]]" "$CONF" || true; }
session_name() { echo "arena-$TASK_ID-$1"; }
alive() { tmux has-session -t "$1" 2>/dev/null; }

launch() {
  local session="$1" harness="$2" model="$3" effort="$4" brief="$5"
  local prompt="Read $brief and follow it."
  case "$harness" in
    claude)
      local env_cfg=""
      [[ -n "${CLAUDE_CONFIG_DIR:-}" ]] && env_cfg="CLAUDE_CONFIG_DIR='$CLAUDE_CONFIG_DIR'"
      # The prompt must precede --dangerously-load-development-channels, which takes several values.
      tmux new-session -d -s "$session" -c "$ROOT" \
        "env $env_cfg AGISTRY_CHANNEL_ACTIVE=1 claude '$prompt' --model '$model' --effort '$effort' --permission-mode auto --dangerously-load-development-channels server:agistry-channel"
      local i
      for i in $(seq 1 30); do
        sleep 1
        if tmux capture-pane -p -t "$session" | grep -q "Loading development channels"; then
          if tmux capture-pane -p -t "$session" | grep -q "server:agistry-channel"; then
            tmux send-keys -t "$session" Enter
          else
            log "WARN $session: unexpected channels prompt; left for the operator"
          fi
          return 0
        fi
      done
      log "WARN $session: no channels prompt within 30 s; check the pane"
      ;;
    codex)
      tmux new-session -d -s "$session" -c "$ROOT" \
        "codex -m '$model' -c 'model_reasoning_effort=\"$effort\"' -c 'sandbox_workspace_write.network_access=true' --approve-for-me -C '$ROOT' '$prompt'"
      ;;
    *) die "unknown harness '$harness' in $CONF" ;;
  esac
}

candidate_brief() {
  local name="$1" wt="$2" n="$3"
  cat <<EOF
# Design candidate \`$name\` for $TASK_ID

You are one of $n independent designers working from the same brief. Until you write DONE, read nothing under \`$CAND/\` except your own folder.

Act as the architect in \`agents/pocketpal-architect.md\`, from this handoff block:

\`\`\`text
$(cat "$STORY_DIR/handoff.txt")
\`\`\`

With these changes:

- Write your WHAT to \`$CAND/$name/what.md\` and spikes to \`$CAND/$name/spikes/\`, not to the story's \`what.md\`.
- Run spikes in \`$wt\` (detached at \`$REF\`; run \`yarn install\` first). Never commit there; it is deleted after the judge.
- Leave \`evidence.md\`, \`decisions.md\`, and \`context/architecture/\` unchanged. End your WHAT with "Proposed rows": the evidence rows and product calls (with defaults) you would add.
- Never stop for a question: an open product call gets your recommended default.
- Join agistry as \`arena-$name\` on task \`$TASK_ID\` so the operator or PM can reach you.
- Skip design exploration; this arena is the exploration.

When finished, write one line naming your design's shape to \`$CAND/$name/DONE\`.
EOF
}

judge_brief() {
  local names="$1"
  cat <<EOF
# Design judge for $TASK_ID

Read-only, except for your verdict. Read \`$STORY_DIR/intent-brief.md\`, \`evidence.md\`, \`decisions.md\`, and the architecture docs in \`$STORY_DIR/handoff.txt\`, then each candidate end to end: $(for n in $names; do printf '`%s/%s/what.md` ' "$CAND" "$n"; done)with its spikes.

Score each candidate 1–5, citing the WHAT section or spike, on:

1. Solves the claim in \`evidence.md\` (for a bug, the reporter's exact case) without added scope.
2. Premises proven: rerun one load-bearing spike per candidate when cheap.
3. Smallest design: every new piece has a reader; existing state reused where it does the job.
4. Fits the flow docs and the codebase's patterns.
5. Covers the evidence plan's risk rows.
6. Cheap to change later.

Recommend a base, and from each other candidate at most two ideas worth grafting into it. Candidates that converge are a finding; say so.

Write \`$CAND/judge.md\`, then one line naming the base to \`$CAND/JUDGE_DONE\`.
EOF
}

# Waits until each marker exists or its session is gone. Prints the names that finished.
wait_for() {
  local deadline=$(( $(date +%s) + TIMEOUT_MIN * 60 )) pending=("$@") done_names=() still name marker
  while [[ ${#pending[@]} -gt 0 && $(date +%s) -lt $deadline ]]; do
    still=()
    for name in "${pending[@]}"; do
      marker="$CAND/$name/DONE"; [[ "$name" == judge ]] && marker="$CAND/JUDGE_DONE"
      if [[ -s "$marker" ]]; then done_names+=("$name")
      elif alive "$(session_name "$name")"; then still+=("$name")
      else log "$name: lane exited without a result" >&2
      fi
    done
    pending=("${still[@]+"${still[@]}"}")
    [[ ${#pending[@]} -gt 0 ]] && sleep 30
  done
  [[ ${#pending[@]} -gt 0 ]] && log "timed out waiting for: ${pending[*]}" >&2
  echo "${done_names[*]+"${done_names[*]}"}"
}

cleanup() {
  [[ -f "$LEDGER" ]] || { log "nothing to clean for $TASK_ID"; return 0; }
  local kind value
  while read -r kind value <&3; do
    case "$kind" in
      session) alive "$value" && tmux kill-session -t "$value" ;;
      worktree)
        [[ -d "$ROOT/worktrees/$value" ]] || continue
        if [[ -z "$(git -C "$ROOT/worktrees/$value" status --porcelain --untracked-files=no)" ]]; then
          "$ROOT/tools/remove-worktree.sh" "$value" --yes --force >/dev/null
        else
          log "kept worktrees/$value: it has tracked changes"
        fi ;;
    esac
  done 3< "$LEDGER"
  rm -f "$LEDGER"
}

status() {
  local role name harness model effort marker state
  while read -r role name harness model effort; do
    marker="$CAND/$name/DONE"; [[ "$role" == judge ]] && marker="$CAND/JUDGE_DONE"
    if [[ -s "$marker" ]]; then state="done: $(head -1 "$marker")"
    elif alive "$(session_name "$name")"; then state="running (tmux: $(session_name "$name"))"
    else state="not running"
    fi
    printf '%-6s %-8s %-7s %-16s %s\n' "$role" "$name" "$harness" "$model" "$state"
  done < <(lanes runner; lanes judge)
}

run() {
  for f in intent-brief.md evidence.md decisions.md handoff.txt; do
    [[ -f "$STORY_DIR/$f" ]] || die "missing $STORY_DIR/$f"
  done
  [[ -f "$LEDGER" ]] && die "an arena for $TASK_ID is recorded in $LEDGER; run cleanup first"
  local runners judge n free
  runners="$(lanes runner)"; judge="$(lanes judge)"
  n="$(grep -c . <<<"$runners" || true)"
  [[ "$n" -ge 2 ]] || die "need at least two runners in $CONF"
  [[ -n "$judge" ]] || die "no judge in $CONF"
  free="$(df -BG --output=avail "$ROOT" | tail -1 | tr -dc 0-9)"
  [[ "$free" -ge $(( n * GB_PER_LANE )) ]] || die "need $(( n * GB_PER_LANE )) GB free, have ${free} GB"

  mkdir -p "$LEDGER_DIR" "$CAND"
  : > "$LEDGER"
  trap 'log "interrupted; lanes left for: tools/design-arena.sh cleanup $STORY_DIR"; exit 2' INT TERM

  local role name harness model effort wt names=()
  while read -r role name harness model effort <&3; do
    wt="$TASK_ID-arena-$name"
    mkdir -p "$CAND/$name/spikes"
    "$ROOT/tools/create-worktree.sh" "$wt" --detach --ref "$REF" >/dev/null
    "$ROOT/tools/sync-worktree-config.sh" "$ROOT/worktrees/$wt" >/dev/null
    printf 'worktree %s\nsession %s\n' "$wt" "$(session_name "$name")" >> "$LEDGER"
    candidate_brief "$name" "$ROOT/worktrees/$wt" "$n" > "$CAND/$name/brief.md"
    launch "$(session_name "$name")" "$harness" "$model" "$effort" "$CAND/$name/brief.md"
    log "launched $name ($harness $model $effort)"
    names+=("$name")
  done 3<<<"$runners"

  local finished
  finished="$(wait_for "${names[@]}")"
  log "candidates: ${finished:-none}"
  if [[ "$(wc -w <<<"$finished")" -lt 2 ]]; then cleanup; exit 1; fi

  read -r role name harness model effort <<<"$judge"
  judge_brief "$finished" > "$CAND/judge-brief.md"
  printf 'session %s\n' "$(session_name judge)" >> "$LEDGER"
  launch "$(session_name judge)" "$harness" "$model" "$effort" "$CAND/judge-brief.md"
  log "launched judge ($harness $model $effort)"
  local judged
  judged="$(wait_for judge)"
  cleanup
  [[ -n "$judged" ]] || { log "judge produced no verdict"; exit 3; }
  log "judged: base $(head -1 "$CAND/JUDGE_DONE")"
}

case "$CMD" in
  run) run ;;
  status) status ;;
  cleanup) cleanup ;;
  *) usage; exit 2 ;;
esac
