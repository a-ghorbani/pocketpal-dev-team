# Visual capture runbook

Read from `docs/workflows/visual-capture.md`: Freshness and Local build prerequisites before any capture run or re-capture round; Flavour B pre/post when capturing a "before" off `origin/main`.

## Freshness

A capture must post-date the **installed** bundle, which must post-date the built APK, which must
post-date the last shippable `src/` commit. The middle term is the one that gets forgotten:
verifying the APK on disk proves nothing about what the phone is running, and an APK's mtime
updates on any repackage, so a fresh APK can ship a stale bundle. Hash the bundle inside the
installed package, before and after the run, and capture with reset disabled.

```bash
unzip -p <apk> assets/index.android.bundle | sha256sum   # compare against HEAD's rebuilt bundle
git log -1 --format='%cI %h' -- src \
    ':(exclude)src/**/__tests__/**' ':(exclude)src/**/*.test.*'   # tests do not ship; do not gate on them
```

**A release bundle is Hermes bytecode, so a plain `grep` returns zero for everything.** Use
`strings -a` and calibrate on a marker you know is present before trusting an absence. Hermes keeps
**two** string tables: a string containing any non-ASCII character (an ellipsis, a curly quote) is
stored UTF-16LE and invisible to an ASCII search, which reads exactly like a stale bundle — on
precisely the new user-facing copy people reach for as a freshness marker. Search both:
`iconv -f UTF-8 -t UTF-16LE <<<'MARKER' | grep -c -f - <bundle>`.

On a re-capture round check each expected file's mtime **individually**: a spec that skips a case
leaves the previous run's file in place, and a partly refreshed directory looks identical to a fully
refreshed one. Record the device, OS, locale and **navigation mode** beside the shots — nav mode
changes bottom insets, so a gesture-mode capture proves nothing about three-button clearance.

Some changes cannot be evidenced by a screenshot at all — a11y props, hit areas, a step count,
something that no longer happens. Those need a test or an a11y-tree dump, not a better capture.

## Local build prerequisites

**Never revert a local build prerequisite.** Leave it modified and unstaged for the life of the work
and keep it out of commits by never staging it — `git add <paths>` and `git commit -- <paths>`,
never `add -A`. Reverting it as housekeeping once coding finishes kills the rebuild and leaves the
capture step with no fresh artefact.

The leak check is therefore **commit-scoped**. A two-dot `git diff origin/main -- android/` compares
the working tree, so it reads non-empty while the prerequisite is correctly in place — a false
violation whose natural remedy is the revert:

```bash
git diff origin/main...HEAD --name-only | grep -c '^android/'   # must be 0
```

A fresh baseline worktree (for a "before" capture off `origin/main`) needs the prerequisite
re-applied; `sync-worktree-config.sh` does not carry `android/app/build.gradle`.

## Flavour B pre/post

The same spec runs against `main` and the branch:

```bash
# post (in the worktree, label defaults to 'post'):
VISUAL_CAPTURE_LABEL=post \
  yarn e2e:ios --spec visual-capture/<TASK-ID> --skip-build

# pre, in a separate baseline worktree off origin/main (from the dev-team root):
./tools/create-worktree.sh <TASK-ID>-base --detach --ref origin/main
cd worktrees/<TASK-ID>-base
cp ../<TASK-ID>/e2e/specs/visual-capture/<TASK-ID>.spec.ts e2e/specs/visual-capture/
git checkout feature/<branch> -- <any e2e/pages/*.ts or e2e/helpers/*.ts files the spec depends on> \
  <any product files with new testIDs the spec depends on>
yarn install && (cd ios && pod install) && yarn ios:build:e2e
VISUAL_CAPTURE_LABEL=pre \
  yarn e2e:ios --spec visual-capture/<TASK-ID> --skip-build

# after copying the pre captures out (from the dev-team root):
./tools/remove-worktree.sh <TASK-ID>-base --yes
```
