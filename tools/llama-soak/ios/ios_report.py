"""Markdown table of the iOS triage cells: <out>/soak/triage/<tag>/seed-N.jsonl + its event log.
For the soak seeds use ../soak_report.py."""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import soak  # noqa: E402

ROOT = soak.out_root() / 'soak' / 'triage'


def events(log):
    out = []
    if not log.exists():
        return out
    for line in log.read_text(errors='replace').splitlines():
        m = soak.EVENT_RE.search(line)
        if m:
            out.append((int(m.group(1)), m.group(2), m.group(3) or ''))
    return out


NATIVE = [('mm-restore', re.compile(r'Restored multimodal state checkpoint')),
          ('restore', re.compile(r'restored state checkpoint: reusing')),
          ('clear', re.compile(r'no usable state checkpoint')),
          ('interrupted', re.compile(r'Decoding interrupted|Decoding Interrupted')),
          ('media-diverged', re.compile(r'Media identity diverged')),
          ('swa-guard', re.compile(r'SWA cache lost')),
          ('chunk-fail', re.compile(r'Failed to evaluate chunks')),
          ('draft-abort', re.compile(r'ctx_dft\)(?: head=\S+)? failed rc=2|failed to decode draft batch')),
          ('ckpt-fail', re.compile(r'state checkpoint (alloc|capture|restore) failed'))]


def native_kinds(text):
    counts = {}
    for line in text.splitlines():
        for k, rx in NATIVE:
            if rx.search(line):
                counts[k] = counts.get(k, 0) + 1
    return counts


def latencies(ev):
    """Stop: stop:pressed -> the next completion:settled; native: stopCompletion:start -> :settled;
    release: release:start -> release:settled."""
    stop, native, rel = [], [], []
    pend = nat = r = None
    for ms, name, _ in ev:
        if name == 'stop:pressed':
            pend = ms
        elif name == 'completion:settled' and pend is not None:
            stop.append(ms - pend)
            pend = None
        elif name == 'stopCompletion:start':
            nat = ms
        elif name == 'stopCompletion:settled' and nat is not None:
            native.append(ms - nat)
            nat = None
        elif name == 'release:start':
            r = ms
        elif name == 'release:settled' and r is not None:
            rel.append(ms - r)
            r = None
    return stop, native, rel


def main():
    print('| cell | scenario | model | backend | build | oracle | stopped run (prompt_n/cached/predicted) | follow-up text | Stop->settled ms | stopCompletion ms | release ms | native lines | errors | alive |')
    print('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    for path in sorted(ROOT.glob('*/seed-*.jsonl')):
        rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        if not rows:
            continue
        head = rows[0]
        loaded = head.get('loaded') or {}
        log = path.with_name(path.stem + '-logcat.txt')
        ev = events(log)
        stop, native, rel = latencies(ev)
        out = path.with_name(path.stem + '-stdout.txt')
        kinds = native_kinds(out.read_text(errors='replace')) if out.exists() else None
        nat_lines = []
        stopped = next((r for r in rows if r.get('op', '').startswith('send') and 'stop' in r.get('op', '')), None)
        st = (stopped or {}).get('completion') or {}
        fol = [r for r in rows if r.get('op') == 'send']
        text = (fol[-1].get('text') or '')[:40].replace('\n', ' ').replace('|', '/') if fol else ''
        orc = ','.join(r['oracle']['result'] for r in rows if r.get('oracle'))
        errs = [e for r in rows for e in r.get('errors', [])] + [r['harness_error'] for r in rows if 'harness_error' in r]
        alive = all(r.get('alive', True) for r in rows)
        print(f"| {path.parent.name}/{path.stem} | {head.get('scenario')} | {loaded.get('mmproj') and 'VL ' or ''}"
              f"{(loaded.get('ctx') or {}) and ''}{path.parent.name.split('-')[0]} | {loaded.get('backend')} "
              f"(gpu={(loaded.get('ctx') or {}).get('gpu')}) | {head.get('build') or 'v1'} | {orc} | "
              f"{st.get('prompt_n')}/{st.get('tokens_cached')}/{st.get('tokens_predicted')} | {text!r} | "
              f"{','.join(map(str, stop)) or '-'} | {','.join(map(str, native)) or '-'} | {','.join(map(str, rel)) or '-'} | "
              f"{'n/a' if kinds is None else (', '.join(f'{k} x{v}' for k, v in kinds.items()) or 'none')} | {str(errs)[:80] if errs else ''} | {alive} |")


if __name__ == '__main__':
    main()
