"""Run a variant of a recorded soak seed (bisect a mismatch or a failure step by step).

Every soak row records its step's random draws in a `script` field. --base takes either a
recorded seed (its rows' `script` fields are used) or a script JSONL of step specs; drop, keep
or replace steps and replay the rest exactly:

  python3 script_variant.py NAME --base <out>/soak/<tag>/seed-11.jsonl [--drop 3,7] [--keep 0,2,9] [--set 'K:{json spec}'] \
      [--oracle-only-last] [--extra-replays 1,4,512] -- --serial S --seed 11 --model-a M [other soak flags]

Writes <out>/soak/triage/variants/script-NAME.jsonl, runs it (tag triage/variants/NAME) and prints
the last step's oracle verdict. Pass the same soak flags (models, --tools, --drafts, --backend) as
the recorded seed, or the replayed draws will not line up.
"""
import argparse
import json
import subprocess
import sys

import soak

p = argparse.ArgumentParser()
p.add_argument('name')
p.add_argument('--base', required=True, help='a recorded seed-N.jsonl, or a JSONL of step specs ({action, rng, oracle})')
p.add_argument('--raw', action='store_true', help='run --base as is (no step selection or oracle rewriting)')
p.add_argument('--drop', default='')
p.add_argument('--keep', default='')
p.add_argument('--set', action='append', default=[], help='K:{json spec} replaces step K (index in base)')
p.add_argument('--extra-replays')
p.add_argument('--oracle-only-last', action='store_true', help='no intermediate oracles (replays)')
p.add_argument('soak_args', nargs=argparse.REMAINDER, help='after --: run.py --mode soak flags')
a = p.parse_args()
rest = [x for x in a.soak_args if x != '--']
seed = rest[rest.index('--seed') + 1] if '--seed' in rest else None
if seed is None:
    raise SystemExit('pass --seed (and the rest of the recorded seed\'s soak flags) after --')

B = soak.out_root() / 'soak' / 'triage' / 'variants'
B.mkdir(parents=True, exist_ok=True)
steps = [json.loads(line) for line in open(a.base).read().splitlines() if line.strip()]
if any('script' in r for r in steps):
    steps = [r['script'] for r in steps if 'script' in r]
for item in a.set:
    k, spec = item.split(':', 1)
    steps[int(k)] = json.loads(spec)
idx = list(range(len(steps)))
if a.keep:
    idx = [int(x) for x in a.keep.split(',')]
if a.drop:
    idx = [i for i in idx if i not in {int(x) for x in a.drop.split(',')}]
out = [dict(steps[i], src=steps[i].get('src', i)) for i in idx]
if a.oracle_only_last:
    for s in out[:-1]:
        s['oracle'] = False
out[-1]['oracle'] = True
if a.raw:
    out = steps
sp = B / f'script-{a.name}.jsonl'
sp.write_text(''.join(json.dumps(s) + '\n' for s in out))
cmd = [sys.executable, str(soak.HERE / 'run.py'), '--mode', 'soak', *rest, '--tag', f'triage/variants/{a.name}',
       '--script', str(sp)] + (['--extra-replays', a.extra_replays] if a.extra_replays else [])
with (B / f'{a.name}.out').open('w') as f:
    subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=3600)
rows = [json.loads(line) for line in (B / a.name / f'seed-{seed}.jsonl').read_text().splitlines()]
br = [r for r in rows if r.get('step') == 'batch-replays']
rows = [r for r in rows if r.get('step') != 'batch-replays']
last = rows[-1]
o = last.get('oracle') or {}
print('RESULT', a.name, 'apk', (rows[0].get('apk_sha256') or '')[:12], 'steps', [s.get('src') for s in out],
      'last', last.get('action'), o.get('result'), 'warm', o.get('warm_hash'), 'cold', o.get('cold_hash'),
      'sim', o.get('similarity'), 'warm_prompt_n', o.get('warm_prompt_n'), 'tokens_eval', o.get('warm_tokens_evaluated'),
      'others', [(r['step'], (r.get('oracle') or {}).get('result')) for r in rows[1:-1] if r.get('oracle')],
      'errors', [r.get('errors') for r in rows[1:] if r.get('errors')], flush=True)
if br:
    print('BATCH', [(x['batch'], x.get('hash')) for x in br[0]['replays']], flush=True)
