"""iOS entry point: `ios_run.py soak <soak.py flags>` or `ios_run.py triage <flags>`.

soak: soak.main's flags (--serial is a label here; the device is $IOS_UDID).
triage: triage.SCENARIOS plus the iOS cells below (Home, model switch, no-Stop baselines).
Output goes to $LLAMA_SOAK_OUT like the Android runs. Set LLAMA_SOAK_BUILD to label the build.
"""
import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import ios_dev  # noqa: E402
import soak  # noqa: E402
import triage  # noqa: E402
LONG = soak.filler(1400)
LONG_ASK = f'The meeting day is Thursday. Read the following data.\n{LONG}\nNow write a detailed analysis of the records.'
GEN_PROMPT = f'The vault code is 4721. Read the following data.\n{LONG}\nNow write a detailed analysis of the records.'

EXTRA = {
    # Home (background -> auto-release) during prefill / generation, back to the app, follow-up.
    'home-prefill': [('send-bg', GEN_PROMPT, 'completion:start', 0.3),
                     ('send', 'What is the vault code? Answer in one line.'), ('state',), ('oracle',)],
    'home-gen': [('send-bg', GEN_PROMPT, 'completion:first-token', 1.0),
                 ('send', 'What is the vault code? Answer in one line.'), ('state',), ('oracle',)],
    # Model switch while the reply streams, a turn on B, back to A, a follow-up.
    'switch-mid-gen': [('send-switch', GEN_PROMPT, 'completion:first-token', 1.0),
                       ('send', 'Reply with OK.'), ('switch-back',),
                       ('send', 'What is the vault code? Answer in one line.'), ('state',), ('oracle',)],
    # No-Stop baseline: three sends, then a cold replay of the last.
    'baseline3': [('send', 'Remember this: the courier is Ilse. Reply with OK.'),
                  ('send', f'The vault code is 4721. Read the following data.\n{soak.filler(480)}\nDescribe the data in two sentences.'),
                  ('send', "What is the courier's name? Answer in one line."), ('oracle',)],
    # Stop mid-generation (MTP), then a follow-up.
    'stop-gen-short': [('send', 'Remember this: the courier is Ilse. Reply with OK.'),
                       ('send-stop', 'Count from one to fifty in words, comma separated.', 'first-token', 400),
                       ('send', "What is the courier's name? Answer in one line."), ('state',), ('oracle',)],
    # smol-cpu seed 101 steps 0-1: Stop 1 s after completion-start (mid-generation) with the follow-up
    # sent in the same tick, then the cold replay of the follow-up.
    'smol-s101': [('send', 'Remember this: the meeting day is Thursday. Reply with OK.'),
                  ('send-stop-then', 'Remember this: the courier is Ilse. Reply with OK.', 'completion-start', 1000,
                   'Summarize our conversation so far in one sentence.'), ('state',), ('oracle',)],
    # Same turns without the Stop.
    'smol-s101-nostop': [('send', 'Remember this: the meeting day is Thursday. Reply with OK.'),
                         ('send', 'Remember this: the courier is Ilse. Reply with OK.'),
                         ('send', 'Summarize our conversation so far in one sentence.'), ('oracle',)],
    # Stop then a separate (not same-tick) follow-up.
    'smol-s101-sep': [('send', 'Remember this: the meeting day is Thursday. Reply with OK.'),
                      ('send-stop', 'Remember this: the courier is Ilse. Reply with OK.', 'completion-start', 1000),
                      ('send', 'Summarize our conversation so far in one sentence.'), ('state',), ('oracle',)],
    # smol-cpu seed 101 steps 3-5: new chat, long prompt stopped in prefill, edit, cold replay.
    'smol-s101-edit': [('send-stop', LONG_ASK, 'send', 1200), ('edit', 'Instead, name two animals that live in the sea.'),
                       ('state',), ('oracle',)],
    # Same final params, no Stop: the long prompt completes, then the edit replaces it.
    'smol-s101-edit-nostop': [('send', LONG_ASK), ('edit', 'Instead, name two animals that live in the sea.'),
                              ('oracle',)],
    # lfmvl-cpu seed 101 steps 16-18 without the Stops: two image turns, two short turns, then the long turn.
    'lfmvl-s101-nostop': [('send-image', 'What colours are in this picture?', 'soak-image.jpg'),
                          ('send', 'Remember this: the meeting day is Thursday. Reply with OK.'),
                          ('send-image', 'Describe the image in one sentence.', 'soak-image.jpg'),
                          ('send', 'What is 17 plus 25? Answer with the number only.'),
                          ('send', f"The courier is Ilse. Read the following data.\n{LONG}\nNow write a detailed analysis of the records."),
                          ('oracle',)],
}
SCENARIOS = {**triage.SCENARIOS, **EXTRA}


class IOSTriage(ios_dev.IOSMixin, soak.Soak):
    pass


def run_triage(argv):
    p = argparse.ArgumentParser()
    p.add_argument('--serial', default='ios')
    p.add_argument('--model-a', required=True)
    p.add_argument('--mmproj-a')
    p.add_argument('--model-b')
    p.add_argument('--mmproj-b')
    p.add_argument('--backend', default='cpu')
    p.add_argument('--scenario', choices=sorted(SCENARIOS), required=True)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--tag', required=True)
    p.add_argument('--n-predict', type=int, default=160)
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--batch', type=int, default=512)
    p.add_argument('--n-ctx', type=int, default=4096)
    p.add_argument('--speculative', action='store_true')
    p.add_argument('--stop-ms', type=int)
    a = p.parse_args(argv)
    for k, v in dict(tools=False, image=None, drafts=False, oracle_rate=1.0, step_timeout=900, skip='',
                     control=False, max_words=1400, steps=0).items():
        setattr(a, k, v)
    a.tag = f'triage/{a.tag}'
    s = IOSTriage(a, soak.out_root())
    s.step_flags = {}
    results = []
    try:
        head = s.ios_setup()
        m = s.mark()
        s.command('release')
        s.wait_event(m, 'manual-release:done', 120)
        if s.ask('wipe-sessions', 'wipe-sessions:done', 60) is None:
            raise RuntimeError('wipe-sessions failed')
        loaded = s.ask('load', 'loaded', 600, **s.load_params())
        if not isinstance(loaded, dict):
            raise RuntimeError(f'load failed: {loaded}')
        s.ask('session', 'session:done', 30, to='new')
        results.append({'step': -1, 'scenario': a.scenario, **head, 'loaded': loaded})
        ops = SCENARIOS[a.scenario]
        if a.stop_ms is not None:
            ops = [op[:3] + (a.stop_ms,) + op[4:] if op[0] == 'send-stop' else
                   op[:4] + (a.stop_ms,) + op[5:] if op[0] == 'send-image-stop' else op for op in ops]
            results[0]['stop_ms'] = a.stop_ms
        last = None
        for i, op in enumerate(ops):
            m = s.mark()
            row = {'step': i, 'op': op[0]}
            kind = op[0]
            if kind == 'send':
                s.command('send', prompt=op[1])
                row['idle'] = s.wait_idle(m, 900, need_start=True)
            elif kind in ('send-stop', 'send-image-stop', 'send-tool-stop'):
                if kind == 'send-stop':
                    s.command('send', prompt=op[1], stopOn=op[2], stopAfterMs=op[3])
                elif kind == 'send-image-stop':
                    s.command('send', prompt=op[1], image=op[2], stopOn=op[3], stopAfterMs=op[4])
                else:
                    s.command('send-tool', prompt=op[1], stopOn=op[2], stopAfterMs=op[3], sleepMs=op[4])
                s.wait_event(m, 'chat-send:done', 900)
                row['idle'] = s.wait_idle(m, 900, need_start=False)
            elif kind == 'send-tool':
                s.command('send-tool', prompt=op[1], sleepMs=op[2])
                row['idle'] = s.wait_idle(m, 900, need_start=True)
            elif kind == 'send-stop-then':
                s.command('send', prompt=op[1], stopOn=op[2], stopAfterMs=op[3], thenSend=op[4])
                s.wait_event(m, 'stop:fired', 120)
                row['idle'] = s.wait_idle(m, 900, need_start=True)
            elif kind == 'edit':
                s.command('edit', prompt=op[1])
                row['idle'] = s.wait_idle(m, 900, need_start=True)
            elif kind == 'state':
                row['state'] = s.chat_state()
            elif kind == 'status':
                time.sleep(5)
                row['status'] = s.status()
                row['alive'] = s.alive()
            elif kind == 'send-image':
                s.command('send', prompt=op[1], image=op[2])
                row['idle'] = s.wait_idle(m, 900, need_start=True)
            elif kind == 'regenerate':
                s.command('regenerate')
                row['idle'] = s.wait_idle(m, 900, need_start=True)
            elif kind == 'new':
                s.ask('session', 'session:done', 30, to='new')
            elif kind == 'send-bg':
                s.command('send', prompt=op[1])
                row['trigger'] = bool(s.wait_event(m, op[2], 300))
                time.sleep(op[3])
                s.adb('shell', 'input keyevent KEYCODE_HOME')
                rel = s.wait_event(m, 'release:start', 20) and s.wait_event(m, 'release:settled', 300)
                row['released'] = bool(rel)
                st = [e['ms'] for e in s.since(m, 'release:start')]
                en = [e['ms'] for e in s.since(m, 'release:settled')]
                row['release_ms'] = en[-1] - st[-1] if st and en else None
                time.sleep(4)
                s.adb('shell', 'am start')
                row['reloaded'] = bool(s.wait_event(m, 'wrapped', 300)) if rel else None
                row['idle'] = s.wait_idle(m, 900)
            elif kind == 'send-switch':
                s.command('send', prompt=op[1])
                row['trigger'] = bool(s.wait_event(m, op[2], 300))
                time.sleep(op[3])
                sw = s.ask('switch', 'switched', 600, filename=a.model_b, mmproj=a.mmproj_b)
                row['switched'] = isinstance(sw, dict)
                st = [e['ms'] for e in s.since(m, 'release:start')]
                en = [e['ms'] for e in s.since(m, 'release:settled')]
                row['release_ms'] = en[-1] - st[-1] if st and en else None
                row['idle'] = s.wait_idle(m, 900)
            elif kind == 'switch-back':
                sw = s.ask('switch', 'switched', 600, filename=a.model_a, mmproj=a.mmproj_a)
                row['switched'] = isinstance(sw, dict)
                row['idle'] = s.wait_idle(m, 900)
            elif kind == 'oracle':
                row['oracle'] = s.oracle(i, last) if last else {'result': 'no-completion'}
            done = s.completions(m)
            row['events'] = [e['name'] for e in s.since(m) if e['name'] not in ('status', 'command', 'chat-state')]
            if done and kind != 'oracle':
                last = done[-1]
                row['completion'] = {k: last.get(k) for k in ('prompt_n', 'tokens_evaluated', 'tokens_cached',
                                                              'tokens_predicted', 'interrupted')}
                row['text'] = (last.get('text') or {}).get('full')
                row['all'] = [{k: c.get(k) for k in ('prompt_n', 'tokens_evaluated', 'tokens_cached',
                                                     'tokens_predicted', 'interrupted')} for c in done]
            row['errors'] = [e['detail'] for e in s.since(m)
                             if e['name'] in ('completion:error', 'chat-send:error', 'error', 'regenerate:error',
                                              'edit:error')]
            row['alive'] = s.alive()
            row['flags'] = s.step_flags
            s.step_flags = {}
            if row.get('idle') == 'timeout' or not row['alive']:
                row['diagnostics'] = s.diagnose(i)
            results.append(row)
            print(json.dumps(row), flush=True)
            if not row['alive']:
                break
    except Exception as error:  # noqa: BLE001
        results.append({'harness_error': repr(error)})
        print('HARNESS', repr(error), flush=True)
    finally:
        crashes = s.ios_teardown()
        s.rows_path.write_text(''.join(json.dumps(r) + '\n' for r in results))
        verdicts = [r['oracle']['result'] for r in results if r.get('oracle')]
        with (s.dir.parent / 'summary.jsonl').open('a') as f:
            f.write(json.dumps({'tag': a.tag, 'seed': a.seed, 'scenario': a.scenario, 'model': a.model_a,
                                'backend': a.backend, 'verdicts': verdicts, 'crash_logs': crashes,
                                'alive': all(r.get('alive', True) for r in results),
                                'busy': sum(1 for r in results for e in r.get('errors', []) if 'busy' in str(e)),
                                'errors': [e for r in results for e in r.get('errors', [])][:5]}) + '\n')
        print('VERDICT', a.scenario, a.model_a, a.backend, verdicts, flush=True)


def run_soak(argv):
    p_args = list(argv)
    if '--serial' not in p_args:
        p_args += ['--serial', 'ios']
    if '--expect-sha' not in p_args:
        p_args += ['--expect-sha', '']
    orig = soak.run
    soak.run = lambda args, root: ios_dev.IOSSoak(args, root).run()
    try:
        soak.main(p_args)
    finally:
        soak.run = orig


if __name__ == '__main__':
    {'soak': run_soak, 'triage': run_triage}[sys.argv[1]](sys.argv[2:])
