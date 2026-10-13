"""Deterministic repro scenarios for soak findings (uses soak.Soak's adb/event helpers).

python3 run.py --mode soak --scenario NAME --serial S --model-a M [--backend B] --tag T --seed N
Scenarios are short fixed command lists; most end with a replay oracle on the last completion.
Rows go to <out>/soak/triage/<tag>/seed-<N>.jsonl like a soak seed, plus a row in
<out>/soak/triage/summary.jsonl.
"""
import argparse
import json
import os
import subprocess
import time

import soak

LONG = soak.filler(1400)
SHORT_LONG = soak.filler(240)
COLD_PROMPT = f"The vault code is 4721. The courier's name is Ilse. Read the data.\n{soak.filler(480)}\nWhat is the vault code? Answer in one sentence."

SCENARIOS = {
    # Chat 1 holds > n_swa tokens; a new chat then reuses the 4-token template prefix.
    'swa-new-chat': [('send', f'The vault code is 4721. Read the data.\n{LONG}\nDescribe it in one sentence.'),
                     ('new',), ('send', 'Summarize our conversation so far in one sentence.'), ('oracle',)],
    # Same, but chat 1 stays below the window: no slid positions are reused.
    'swa-new-chat-short': [('send', f'The vault code is 4721. Read the data.\n{SHORT_LONG}\nDescribe it in one sentence.'),
                           ('new',), ('send', 'Summarize our conversation so far in one sentence.'), ('oracle',)],
    # Regenerate the last reply of a chat longer than the window (prefix reuse past the slid window).
    'swa-regenerate': [('send', f'The vault code is 4721. Read the data.\n{LONG}\nDescribe it in one sentence.'),
                       ('send', 'What is the vault code? Answer in one line.'), ('regenerate',), ('oracle',)],
    # Plain two-turn chat, nothing else: warm second turn vs cold.
    'two-turn': [('send', 'Remember this: the courier is Ilse. Reply with OK.'),
                 ('send', "What is the courier's name? Answer in one line."), ('oracle',)],
    'two-turn-long': [('send', f'The vault code is 4721. Read the data.\n{LONG}\nDescribe it in one sentence.'),
                      ('send', 'What is the vault code? Answer in one line.'), ('oracle',)],
    # Stop inside the formatting window (before the completion starts), then a plain follow-up.
    'stop-before-start': [('send', 'Remember this: the courier is Ilse. Reply with OK.'),
                          ('send-stop', 'What is 17 plus 25? Answer with the number only.', 'send', 20),
                          ('send', "What is the courier's name? Answer in one line."), ('state',), ('oracle',)],
    # Same, but the Stop lands in prefill (a completion runs and is interrupted).
    'stop-in-prefill': [('send', 'Remember this: the courier is Ilse. Reply with OK.'),
                        ('send-stop', f'Read the data.\n{LONG}\nDescribe it.', 'completion-start', 300),
                        ('send', "What is the courier's name? Answer in one line."), ('state',), ('oracle',)],
    # Stop during generation of a long prompt (recurrent: restoreAfterAbortedDecode), then a short follow-up.
    'stop-gen-then-send': [('send-stop', f'The vault code is 4721. Read the following data.\n{LONG}\nNow write a detailed analysis of the records.', 'first-token', 200),
                           ('send', 'What is the vault code? Answer in one line.'), ('oracle',)],
    # Same prompts, no Stop: the generation-reuse baseline.
    'gen-then-send': [('send', f'The vault code is 4721. Read the following data.\n{LONG}\nNow write a detailed analysis of the records.'),
                      ('send', 'What is the vault code? Answer in one line.'), ('oracle',)],
    # A reply made of repeated ordered-list markers ("2. 2. 2. ...") renders as ~40 nested <ol>.
    'nested-list-echo': [('send', 'Copy this line exactly and write nothing else: ' + '2. ' * 40), ('state',), ('status',)],
    # No Stop, no sliding-window crossing: a short turn, then a 560-token prompt on top of the cache.
    'short-then-long': [('send', 'Remember this: the courier is Ilse. Reply with OK.'),
                        ('send', f'The vault code is 4721. Read the following data.\n{soak.filler(480)}\nDescribe the data in two sentences.'),
                        ('oracle',)],
    # An image turn, then a long text turn reusing the cache that holds the image.
    'image-then-long': [('send-image', 'Describe the image in one sentence.', 'soak-image.jpg'),
                        ('send', f'The vault code is 4721. Read the following data.\n{soak.filler(480)}\nDescribe the data in two sentences.'),
                        ('oracle',)],
    # lfm25-350m seed 11 steps 8-11: long chat, edit, Stop in generation (checkpoint restore),
    # then a Stop before the next completion starts plus an immediate follow-up.
    'restore-then-early-stop': [('send', f'The vault code is 4721. Read the following data.\n{LONG}\nDescribe it in one sentence.'),
                                ('send', 'Name three colours, comma separated.'),
                                ('edit', 'Instead, name two animals that live in the sea.'),
                                ('send-stop', f'The courier is Ilse. Read the following data.\n{SHORT_LONG}\nNow write a detailed analysis of the records.', 'first-token', 0),
                                ('send-stop-then', 'Count from one to ten in words.', 'send', 20, 'Remember this: the vault code is 4721. Reply with OK.'),
                                ('oracle',)],
    # Same without the Stop in generation.
    'early-stop-only': [('send', f'The vault code is 4721. Read the following data.\n{LONG}\nDescribe it in one sentence.'),
                        ('send', 'Name three colours, comma separated.'),
                        ('edit', 'Instead, name two animals that live in the sea.'),
                        ('send', f'The courier is Ilse. Read the following data.\n{SHORT_LONG}\nNow write a detailed analysis of the records.'),
                        ('send-stop-then', 'Count from one to ten in words.', 'send', 20, 'Remember this: the vault code is 4721. Reply with OK.'),
                        ('oracle',)],
    # Same without the early Stop: Stop in generation, then a plain follow-up.
    'restore-only': [('send', f'The vault code is 4721. Read the following data.\n{LONG}\nDescribe it in one sentence.'),
                     ('send', 'Name three colours, comma separated.'),
                     ('edit', 'Instead, name two animals that live in the sea.'),
                     ('send-stop', f'The courier is Ilse. Read the following data.\n{SHORT_LONG}\nNow write a detailed analysis of the records.', 'first-token', 0),
                     ('send', 'Remember this: the vault code is 4721. Reply with OK.'),
                     ('oracle',)],
    # Repeated cold replays of the same params: is the cold path itself deterministic?
    'cold-twice': [('send', 'Write a haiku about a river.'), ('oracle',), ('oracle',)],
    # Cold context (fresh load, n_past 0): Stop as the first completion starts, then the same
    # message again (resend must process the full prompt) or a different one.
    'cold-stop-same': [('send-stop', COLD_PROMPT, 'completion-start', 0), ('send', COLD_PROMPT), ('state',), ('oracle',)],
    'cold-stop-diff': [('send-stop', COLD_PROMPT, 'completion-start', 0),
                       ('send', "What is the courier's name? Answer in one line."), ('state',), ('oracle',)],
    'cold-same-nostop': [('send', COLD_PROMPT), ('send', COLD_PROMPT), ('oracle',)],
    # Vision: Stop during the image encode / during generation, then a text follow-up (the image re-encodes).
    'image-stop-ingest': [('send-image-stop', 'Describe the image in one sentence.', 'soak-image.jpg', 'completion-start', 300),
                          ('send', 'What colours are in this picture? Answer in one line.'), ('state',), ('oracle',)],
    'image-stop-gen': [('send-image-stop', 'Describe the image in one sentence.', 'soak-image.jpg', 'first-token', 200),
                       ('send', 'What colours are in this picture? Answer in one line.'), ('state',), ('oracle',)],
    'image-then-send': [('send-image', 'Describe the image in one sentence.', 'soak-image.jpg'),
                        ('send', 'What colours are in this picture? Answer in one line.'), ('oracle',)],
    # Tools: Stop while e2e_sleep runs (tool-start + 500 of a 4 s sleep), or once the post-tool
    # completion has started (tool-start + sleep + 100 ms), then a plain follow-up.
    'tool-stop-exec': [('send-tool-stop', 'What is the code word? Use your tool.', 'tool-start', 500, 4000),
                       ('send', 'Remember this: the courier is Ilse. Reply with OK.'), ('state',), ('oracle',)],
    'tool-stop-gap': [('send-tool-stop', 'What is the code word? Use your tool.', 'tool-start', 1600, 1500),
                      ('send', 'Remember this: the courier is Ilse. Reply with OK.'), ('state',), ('oracle',)],
    'tool-stop-followup': [('send-tool-stop', 'What is the code word? Use your tool.', 'tool-start', 1900, 1500),
                           ('send', 'Remember this: the courier is Ilse. Reply with OK.'), ('state',), ('oracle',)],
    # Switch to a strict-alternation template (Gemma) in a chat that holds a tool turn / an empty stopped turn.
    'tool-then-gemma': [('send-tool', 'What is the code word? Use your tool.', 1500), ('switch', 'gemma-3-1b-it-q4_0.gguf'),
                        ('send', 'Reply with OK.'), ('state',)],
    'emptystop-then-gemma': [('send', 'Remember this: the courier is Ilse. Reply with OK.'),
                             ('send-stop', COLD_PROMPT, 'completion-start', 0), ('switch', 'gemma-3-1b-it-q4_0.gguf'),
                             ('send', 'Reply with OK.'), ('state',)],
    'tool-nostop': [('send-tool', 'What is the code word? Use your tool.', 1500),
                    ('send', 'Remember this: the courier is Ilse. Reply with OK.'), ('oracle',)],
}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['soak'])
    p.add_argument('--serial', required=True)
    p.add_argument('--model-a', required=True)
    p.add_argument('--mmproj-a')
    p.add_argument('--backend', default='cpu')
    p.add_argument('--scenario', choices=sorted(SCENARIOS), required=True)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--tag', required=True)
    p.add_argument('--n-predict', type=int, default=160)
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--batch', type=int, default=512)
    p.add_argument('--n-ctx', type=int, default=4096)
    p.add_argument('--expect-sha', default=os.environ.get('LLAMA_SOAK_APK_SHA', ''),
                   help='refuse to run unless the installed APK has this sha256 (default $LLAMA_SOAK_APK_SHA)')
    p.add_argument('--speculative', action='store_true')
    p.add_argument('--stop-ms', type=int, help='override stopAfterMs of every send-stop / send-image-stop op')
    a = p.parse_args(argv)
    for k, v in dict(model_b=None, mmproj_b=None, tools=False, image=None, drafts=False,
                     oracle_rate=1.0, step_timeout=900, skip='', control=False, max_words=1400, steps=0).items():
        setattr(a, k, v)
    a.tag = f'triage/{a.tag}'
    s = soak.Soak(a, soak.out_root())
    s.step_flags = {}
    logcat = None
    results = []
    try:
        s.adb('shell', 'input keyevent KEYCODE_WAKEUP')
        s.adb('shell', f'am force-stop {soak.PKG}')
        s.adb('shell', f'rm -f {soak.FILES}/crash-command.json')
        apk = s.adb('shell', f'pm path {soak.PKG}').split(':', 1)[1]
        apk_sha = s.adb('shell', f'sha256sum {apk}').split()[0]
        if a.expect_sha and apk_sha != a.expect_sha:
            raise RuntimeError(f'installed APK {apk_sha} is not the expected build {a.expect_sha}')
        s.adb('logcat', '-c', check=False)
        logcat = subprocess.Popen(['adb', '-s', a.serial, 'logcat', '-v', 'epoch'], stdout=s.log_path.open('w'),
                                  stderr=subprocess.STDOUT)
        s.adb('shell', f'am start -n {soak.PKG}/com.pocketpal.MainActivity')
        time.sleep(8)
        s.pid0 = s.pid()
        m = s.mark()
        s.command('release')
        s.wait_event(m, 'manual-release:done', 120)
        if s.ask('wipe-sessions', 'wipe-sessions:done', 60) is None:
            raise RuntimeError('wipe-sessions failed (old adapter?)')
        loaded = s.ask('load', 'loaded', 600, **s.load_params())
        s.ask('session', 'session:done', 30, to='new')
        results.append({'step': -1, 'scenario': a.scenario, 'apk_sha256': apk_sha, 'loaded': loaded})
        last = None
        ops = SCENARIOS[a.scenario]
        if a.stop_ms is not None:
            ops = [op[:3] + (a.stop_ms,) + op[4:] if op[0] == 'send-stop' else
                   op[:4] + (a.stop_ms,) + op[5:] if op[0] == 'send-image-stop' else op for op in ops]
            results[0]['stop_ms'] = a.stop_ms
        for i, op in enumerate(ops):
            m = s.mark()
            row = {'step': i, 'op': op[0]}
            if op[0] == 'send':
                s.command('send', prompt=op[1])
                row['idle'] = s.wait_idle(m, 900, need_start=True)
            elif op[0] == 'send-stop':
                s.command('send', prompt=op[1], stopOn=op[2], stopAfterMs=op[3])
                s.wait_event(m, 'chat-send:done', 900)
                row['idle'] = s.wait_idle(m, 900, need_start=False)
                row['events'] = [e['name'] for e in s.since(m) if e['name'] not in ('status', 'command')]
            elif op[0] == 'send-image-stop':
                s.command('send', prompt=op[1], image=op[2], stopOn=op[3], stopAfterMs=op[4])
                s.wait_event(m, 'chat-send:done', 900)
                row['idle'] = s.wait_idle(m, 900, need_start=False)
                row['events'] = [e['name'] for e in s.since(m) if e['name'] not in ('status', 'command')]
            elif op[0] == 'send-tool-stop':
                s.command('send-tool', prompt=op[1], stopOn=op[2], stopAfterMs=op[3], sleepMs=op[4])
                s.wait_event(m, 'chat-send:done', 900)
                row['idle'] = s.wait_idle(m, 900, need_start=False)
                row['events'] = [e['name'] for e in s.since(m) if e['name'] not in ('status', 'command')]
            elif op[0] == 'send-tool':
                s.command('send-tool', prompt=op[1], sleepMs=op[2])
                row['idle'] = s.wait_idle(m, 900, need_start=True)
                row['events'] = [e['name'] for e in s.since(m) if e['name'] not in ('status', 'command')]
            elif op[0] == 'send-stop-then':
                s.command('send', prompt=op[1], stopOn=op[2], stopAfterMs=op[3], thenSend=op[4])
                s.wait_event(m, 'stop:fired', 120)
                row['idle'] = s.wait_idle(m, 900, need_start=True)
                row['events'] = [e['name'] for e in s.since(m) if e['name'] not in ('status', 'command')]
            elif op[0] == 'edit':
                s.command('edit', prompt=op[1])
                row['idle'] = s.wait_idle(m, 900, need_start=True)
            elif op[0] == 'state':
                row['state'] = s.chat_state()
            elif op[0] == 'status':
                time.sleep(5)
                row['status'] = s.status()
                row['alive'] = s.alive()
            elif op[0] == 'send-image':
                s.command('send', prompt=op[1], image=op[2])
                row['idle'] = s.wait_idle(m, 900, need_start=True)
            elif op[0] == 'regenerate':
                s.command('regenerate')
                row['idle'] = s.wait_idle(m, 900, need_start=True)
            elif op[0] == 'switch':
                row['switched'] = str(s.ask('switch', 'switched', 600, filename=op[1], mmproj=None))[:200]
                s.wait_idle(s.mark(), 120)
            elif op[0] == 'new':
                s.ask('session', 'session:done', 30, to='new')
            elif op[0] == 'oracle':
                row['oracle'] = s.oracle(i, last)
            done = s.completions(m)
            if done and op[0] != 'oracle':
                last = done[-1]
                row['completion'] = {k: last.get(k) for k in ('prompt_n', 'tokens_evaluated', 'tokens_cached',
                                                              'tokens_predicted', 'interrupted')}
                row['text'] = (last.get('text') or {}).get('full')
                row['all'] = [{k: c.get(k) for k in ('prompt_n', 'tokens_evaluated', 'tokens_cached', 'tokens_predicted',
                                                     'interrupted')} for c in done]
            row['errors'] = [e['detail'] for e in s.since(m) if e['name'] in ('completion:error', 'chat-send:error', 'error')]
            row['flags'] = s.step_flags
            done_all = s.completions(m)
            if any(c.get('interrupted') for c in done_all) or s.step_flags.get('abort_path'):
                row['flags']['abort_kind'] = soak.classify_aborts(s.step_flags, done_all)
            s.step_flags = {}
            if row.get('idle') == 'timeout' or (op[0] == 'status' and row.get('status') is None):
                row['diagnostics'] = s.diagnose(i)
            results.append(row)
            print(json.dumps(row)[:700], flush=True)
    finally:
        if logcat:
            logcat.terminate()
            logcat.wait(timeout=10)
            subprocess.run(['gzip', '-f', str(s.log_path)], check=False)
        s.rows_path.write_text(''.join(json.dumps(r) + '\n' for r in results))
        verdicts = [r['oracle']['result'] for r in results if r.get('oracle')]
        sm = s.dir.parent / 'summary.jsonl'
        with sm.open('a') as f:
            f.write(json.dumps({'tag': a.tag, 'seed': a.seed, 'scenario': a.scenario, 'model': a.model_a, 'backend': a.backend,
                                'serial': a.serial, 'verdicts': verdicts,
                                'busy': sum((r.get('flags') or {}).get('busy', 0) for r in results),
                                'errors': [e for r in results for e in r.get('errors', [])][:5]}) + '\n')
        print('VERDICT', a.scenario, a.model_a, a.backend, verdicts, flush=True)


if __name__ == '__main__':
    main()
