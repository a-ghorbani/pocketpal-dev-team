"""Aggregate <out>/soak/<tag>/seed-*.jsonl into a coverage table (stdout, markdown).

python3 soak_report.py [subdir]   # e.g. `rc8` reports only <out>/soak/rc8/<tag>/
"""
import collections
import gzip
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import soak  # noqa: E402

root = soak.out_root() / 'soak'
if len(sys.argv) > 1:
    root = root / sys.argv[1]
cells = collections.OrderedDict()
for path in sorted(root.glob('*/seed-*.jsonl')):
    tag = path.parent.name
    if tag.startswith('smoke'):
        continue
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        continue
    head = rows[0]
    s = head.get('settings', {})
    loaded = head.get('loaded') or {}
    ctx = loaded.get('ctx') or {}
    key = (tag, s.get('serial'))
    c = cells.setdefault(key, {'model': s.get('model_a'), 'backend': s.get('backend'), 'devices': ctx.get('devices'),
                               'control': s.get('control'), 'seeds': [], 'steps': 0, 'oracle': 0, 'match': 0,
                               'mismatch': 0, 'stops': 0, 'interrupted': 0, 'actions': collections.Counter(),
                               'problems': [], 'abort_paths': collections.Counter(), 'load_paths': collections.Counter(), 'stop_ms': [],
                               'release_ms': []})
    log = path.with_name(path.stem + '-logcat.txt.gz')
    if log.exists():
        pending = None
        inflight = False
        for line in gzip.open(log, 'rt', errors='replace'):
            m = soak.EVENT_RE.search(line)
            if not m:
                continue
            name, ms = m.group(2), int(m.group(1))
            if name == 'completion:start':
                inflight = True
            elif name == 'stop:pressed' and inflight:
                pending = ms
            elif name in ('completion:settled', 'completion:error'):
                inflight = False
                if pending:
                    c['stop_ms'].append(ms - pending)
                    pending = None
    c['seeds'].append(s.get('seed'))
    for r in rows[1:]:
        if 'action' not in r:
            c['problems'].append(f"seed {s.get('seed')} step {r.get('step')}: {r.get('harness_error')}")
            continue
        c['steps'] += 1
        c['actions'][r['action']] += 1
        c['interrupted'] += sum(1 for x in r.get('completions', []) if x.get('interrupted'))
        flags = r.get('flags') or {}
        kinds = flags.get('abort_kind') or soak.classify_aborts(flags, r.get('completions', []))
        for kind in kinds:
            c['abort_paths'][kind] += 1
        for kind in flags.get('load_path', []):
            c['load_paths'][kind] += 1
        o = r.get('oracle')
        if o:
            c['oracle'] += 1
            if o.get('result') == 'match':
                c['match'] += 1
            else:
                c['mismatch'] += 1
        if r.get('release_ms') is not None:
            c['release_ms'].append(r['release_ms'])
        if not r.get('alive', True):
            c['problems'].append(f"seed {s.get('seed')} step {r['step']}: process gone ({r['action']})")
        if any(str(v) == 'timeout' for k, v in r.items() if k.startswith('idle')):
            c['problems'].append(f"seed {s.get('seed')} step {r['step']}: hang ({r['action']})")
        if r.get('session_issues'):
            c['problems'].append(f"seed {s.get('seed')} step {r['step']}: session {r['session_issues']}")
        if (r.get('flags') or {}).get('busy'):
            c['problems'].append(f"seed {s.get('seed')} step {r['step']}: Context is busy x{r['flags']['busy']}")
        if r.get('errors'):
            c['problems'].append(f"seed {s.get('seed')} step {r['step']}: errors {str(r['errors'])[:160]}")

def pct(v):
    if not v:
        return '-'
    v = sorted(v)
    return f"{v[len(v) // 2]:.0f} / {v[int(0.9 * (len(v) - 1))]:.0f} / {v[-1]:.0f}"


print('| tag | phone | model | backend (devices) | seeds | steps | interrupted | oracle match/mismatch | Stop->settled ms p50/p90/max (n) | release ms p50/p90/max (n) | problems |')
print('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
for (tag, serial), c in cells.items():
    print(f"| {tag}{' (control)' if c['control'] else ''} | {serial} | {c['model']} | {c['backend']} ({c['devices']}) | "
          f"{','.join(map(str, c['seeds']))} | {c['steps']} | {c['interrupted']} | {c['match']}/{c['mismatch']} | "
          f"{pct(c['stop_ms'])} ({len(c['stop_ms'])}) | {pct(c['release_ms'])} ({len(c['release_ms'])}) | "
          f"{len(c['problems'])} |")
print()
for (tag, serial), c in cells.items():
    print(f"## {tag} {serial}")
    print('actions:', dict(c['actions']))
    print('abort paths:', dict(c['abort_paths']))
    print('load paths:', dict(c['load_paths']))
    for p in c['problems']:
        print('-', p)
