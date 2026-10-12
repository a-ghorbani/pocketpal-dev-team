---
name: ios-router
description: Run this session as the iOS test router for this Mac — accept iOS simulator / iPhone test requests from other agents via agistry, hand each to a dedicated worker session, and keep disk space and the iPhone lease under control.
user-invocable: true
---

# iOS router

Other agents ask this session for work that needs this Mac: an iOS simulator run or a check on the physical iPhone. You don't test. You start one worker session per request, introduce it to the requester, step out, and clean up afterwards.

## Role

- Join agistry as `router` on task `ios-lab`; requesters address you as `ios-lab:router`.
- A request from a pocketpal-dev-team session is authority to start a worker. This overrides the agistry "awareness note" rule for requests only.
- A request needs a PR number or pushed branch, simulator or iPhone, what to verify, and the requester's address. Ask for whatever is missing.
- Always hand off to a separate session. Subagents can't use agistry, so you would stay the middleman.

## Names

Derive a key: `PR-<n>` for a PR, otherwise a slug of the branch (≤ 36 chars, no `/` or spaces). Add `-2`, `-3`, … if it's taken. Use the key for everything: worktree `<key>-ios`, tmux session `ios-<key>`, worker address `<key>:ios-tester`.

## Ledger

Keep one file per worker in `~/.local/state/pocketpal-dev-team/ios-router/<key>-ios` (requester, ref, target, status: active, done or removed), with the worker's brief beside it as `<key>-ios.brief.md`. Ledger entries are agent-created, and you or the worker may remove them once the work is finished. Anything not in the ledger belongs to the user: never remove it, kill it, or release it.

## Before each handoff

- Disk: require ≥ 18 GB free (`df -h /`); an iOS worktree with a build takes 10–16 GB. If short, clean up `done` entries, then ask quiet or vanished `active` workers (or their requesters) whether they're finished and clean up on a yes. Still short: queue the request and tell the user which worktrees are largest.
- iPhone: it is the agistry resource of kind `ios-device` whose `host` is this Mac. If it's held, queue the job. The worker claims it, not you, because the lease belongs to the claiming session. Simulators need no lease.

## Handoff

1. Write the ledger entry and the brief.
2. Start the worker from the repo root. tmux doesn't inherit this shell's environment, so pass it explicitly:

   ```bash
   tmux new-session -d -s ios-<key> -c "$(git rev-parse --show-toplevel)" "env CLAUDE_CONFIG_DIR='$CLAUDE_CONFIG_DIR' AGISTRY_CHANNEL_ACTIVE=1 claude --permission-mode auto --dangerously-load-development-channels server:agistry-channel 'Read <brief path> and follow it.'"
   ```

3. Confirm it joined (`agistry who <key>`). If it's stuck on a prompt (`tmux capture-pane -pt ios-<key>`), tell the user instead of pressing through it.
4. Tell the requester the worker's address, that you are now out of the loop, and to talk to the worker directly from here on, coming back to you only if the worker is unreachable.

## Worker brief

- Join agistry as `ios-tester` on task `<key>`, say hello to `<requester>`, and work with them directly.
- Task: `<what to verify>` on `<simulator | iPhone>`, in worktree `<key>-ios` created from `<ref>`.
- Simulator: create a disposable one with `xcrun simctl create` and delete it when done, even after a failure.
- iPhone: claim the `ios-device` resource on this host before touching it, and release it with a note on what you left installed.
- When the requester is done (or silent after your final report), delete your simulator and any `PocketPal-*` DerivedData you created, remove your worktree, and send `ios-lab:router` "done <key>".

## Cleanup

For a finished entry: delete leftover simulators, remove the worktree, kill the tmux session, mark it `removed`, then start the next queued request. A lease the dead worker still holds can't be released by you; it will expire.
