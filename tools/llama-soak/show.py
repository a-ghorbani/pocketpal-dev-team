"""show.py <seed-N.jsonl glob...>: compact per-step view of triage rows."""
import glob, json, sys
for pat in sys.argv[1:]:
    for path in sorted(glob.glob(pat)):
        print('==', path)
        for l in open(path):
            r = json.loads(l)
            if r.get('step', 0) < 0:
                ld = r.get('loaded') or {}
                print('  setup', r.get('apk_sha256', '')[:12], (ld.get('ctx') or {}).get('androidLib'), ld.get('spec_type'), (ld.get('ctx') or {}).get('devices'))
                continue
            o = r.get('oracle') or {}
            f = r.get('flags') or {}
            ev = r.get('events') or []
            print(' ', r['step'], r['op'], r.get('all') or '', ('ev=' + ','.join(e for e in ev if e.startswith(('completion', 'stop', 'tool')))) if ev else '',
                  f.get('abort_kind', ''), f.get('load_path', ''), ('busy=%s' % f['busy']) if f.get('busy') else '',
                  r.get('errors') or '', o.get('result', ''), o.get('similarity', ''), repr((r.get('text') or '')[:40]))
