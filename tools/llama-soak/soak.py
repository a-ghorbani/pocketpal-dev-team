"""Seeded random soak for the stop/release/switch paths (run.py --mode soak).

One call runs one seed: K random steps against one model/backend on one phone,
through the E2E CrashReproAdapter. Every uninterrupted completion is a
candidate for the replay oracle (release, cold reload, the exact params
again); the cold text hash must equal the warm one. Writes
<out>/soak/<tag>/seed-<N>.jsonl (one row per step), seed-<N>-logcat.txt.gz and
a row in <out>/soak/summary.jsonl, where <out> is $LLAMA_SOAK_OUT (default:
./out next to this file). See README.md.
"""
import ast
import difflib
import json
import os
import pathlib
import random
import re
import subprocess
import time
import xml.etree.ElementTree as ET

PKG = 'com.pocketpalai.e2e'
HERE = pathlib.Path(__file__).resolve().parent
FILES = f'/sdcard/Android/data/{PKG}/files'
EVENT_RE = re.compile(r"\[CRASH_REPRO\]'?,? (\d+),? '([^']+)'(?:,? '(.*)')?")
CRASH_RE = re.compile(r'Fatal signal[^\n]*pocketpalai\.e2e|>>> com\.pocketpalai\.e2e <<<|'
                      r'Process: com\.pocketpalai\.e2e, PID')
ABORT_RE = re.compile(r'Decoding interrupted, [^\n]*')
# Native lines after a Stop, by patch generation. rc.5 patch (_v2): every aborted decode logs a
# `Decoding interrupted, ...` line (dense: `n_past: N` trim). rc.7 patch (_v3): only MTP-with-rollback
# memory (n_rs_seq > 0) logs restore/clear in endCompletion; everything else logs nothing and relies
# on llama_decode dropping the aborted ubatch plus the next loadPrompt's seq_rm / checkpoint restore.
LOAD_RES = ((re.compile(r'restored state checkpoint: reusing (\d+)/(\d+)'), 'load-restore'),
            (re.compile(r'no usable state checkpoint \(recurrent/hybrid/SWA model\)'), 'load-clear'),
            (re.compile(r'SWA cache lost positions'), 'swa-guard'),
            (re.compile(r'Failed to evaluate chunks'), 'media-chunk-fail'),
            (re.compile(r'Decoding Interrupted'), 'loop-interrupted'),
            (re.compile(r'failed to eval, n_eval'), 'eval-fail'),
            (re.compile(r'ctx_dft\)(?: head=\S+)? failed rc=2|llama_process returned 2|failed to decode draft batch, ret = 2'),
             'draft-abort'))


def abort_kind(line):
    """Classify one `Decoding interrupted, ...` line (rc.5 and rc.7 patch wording)."""
    if 'restored state checkpoint' in line:
        return 'restore'
    m = re.search(r'no usable state checkpoint \(([^)]*)\)', line)
    if m:
        return f'clear:{m.group(1)}'
    if 'n_past:' in line:
        return 'dense-trim'
    return 'other'


def classify_aborts(flags, completions):
    """Per-step abort classes: one per endCompletion line; an interrupted completion that logged
    none is 'implicit' (the rc.7 path for dense / non-MTP hybrid models, or a Stop between decodes)."""
    kinds = [abort_kind(p) for p in flags.get('abort_path', [])]
    n_int = sum(1 for c in completions if c.get('interrupted'))
    kinds += ['implicit'] * max(0, n_int - len(kinds))
    return kinds
BUSY_RE = re.compile(r'Context is busy')
DSP_RE = re.compile(r'dspqueue[^\n]*(failed|error)|wait_signal_locked failed', re.I)
LMK_RE = re.compile(r'lowmemorykiller[^\n]*pocketpalai\.e2e|Kill \'com\.pocketpalai\.e2e\'|'
                    r'ActivityManager: Killing \d+:com\.pocketpalai\.e2e')

FACTS = [('vault code', '4721'), ('courier', 'Ilse'), ('harbour gate', 'Gate 9'),
         ('password', 'TANGERINE'), ('meeting day', 'Thursday')]
SHORT = [
    'Reply with OK.',
    'What is 17 plus 25? Answer with the number only.',
    'Name three colours, comma separated.',
    'Summarize our conversation so far in one sentence.',
    'What is the vault code I gave you? Answer in one line.',
    "What is the courier's name? Answer in one line.",
    'Write a haiku about a river.',
    'List the facts I asked you to remember.',
    'Translate "good morning" into French and German.',
    'Count from one to ten in words.',
]
EDITS = [
    'Actually, what is 12 times 12? Answer with the number only.',
    'Instead, name two animals that live in the sea.',
    'Rather: what is the password I gave you?',
]
TOOL_PROMPTS = ['What is the code word? Use your tool.',
                'Use your tool, then tell me the code word in one sentence.']
IMAGE_PROMPTS = ['Describe the image in one sentence.', 'What colours are in this picture?']


def decode_detail(raw):
    """The detail is a JS string repr ('...' with \\\\, \\' and \\n escapes) of JSON."""
    if not raw:
        return None
    try:
        text = ast.literal_eval("'" + raw + "'")
    except (ValueError, SyntaxError):
        text = raw.replace("\\'", "'")
    try:
        return json.loads(text)
    except ValueError:
        return text


class RecRng:
    """random.Random that records every draw of the current step (session ids as their
    index in Soak.sessions) so a step can be replayed with the same choices."""
    def __init__(self, seed, soak):
        self.r = random.Random(seed)
        self.soak = soak
        self.log = []

    def random(self):
        v = self.r.random()
        self.log.append(v)
        return v

    def randint(self, a, b):
        v = self.r.randint(a, b)
        self.log.append(v)
        return v

    def choice(self, seq):
        v = self.r.choice(seq)
        self.log.append({'s': self.soak.sessions.index(v)} if isinstance(v, str) and v in self.soak.sessions else v)
        return v

    def choices(self, pop, weights):
        v = self.r.choices(pop, weights)
        self.log.append(v[0])
        return v


class ReplayRng:
    """Returns one scripted step's recorded draws in order."""
    def __init__(self, draws, soak):
        self.q = list(draws)
        self.soak = soak
        self.log = []

    def _next(self):
        if not self.q:
            raise RuntimeError('script step ran out of recorded draws')
        v = self.q.pop(0)
        self.log.append(v)
        return v

    def random(self):
        return self._next()

    def randint(self, a, b):
        return self._next()

    def choice(self, seq):
        v = self._next()
        if isinstance(v, dict) and 's' in v:
            v = self.soak.sessions[v['s']] if v['s'] < len(self.soak.sessions) else seq[0]
        return tuple(v) if isinstance(v, list) else v

    def choices(self, pop, weights):
        return [self._next()]


def filler(words):
    return ' '.join(f'record{i}: the river crosses the valley and the quiet village has a stone bridge.'
                    for i in range(max(1, words // 16)))


class Soak:
    def __init__(self, args, root):
        self.a = args
        self.rng = RecRng(args.seed, self)
        self.script = None
        if getattr(args, 'script', None):
            self.script = [json.loads(line) for line in pathlib.Path(args.script).read_text().splitlines()
                           if line.strip() and not line.lstrip().startswith('#')]
        self.tag = args.tag or f'{args.model_a.rsplit(".", 1)[0]}-{args.backend}-{args.serial}'
        self.dir = root / 'soak' / self.tag
        self.dir.mkdir(parents=True, exist_ok=True)
        self.rows_path = self.dir / f'seed-{args.seed}.jsonl'
        if self.rows_path.exists():
            raise RuntimeError(f'{self.rows_path} exists; pick a new seed or tag')
        self.log_path = self.dir / f'seed-{args.seed}-logcat.txt'
        self.summary_path = self.dir.parent / 'summary.jsonl'
        self.events = []
        self.offset = 0
        self.buf = ''
        self.logtext_tail = ''
        self.findings = []
        self.oracles = []
        self.sessions = []  # ids created in this seed, oldest first
        self.long_session = None
        self.model = args.model_a
        self.mmproj = args.mmproj_a
        self.pid0 = None
        self.cmd_n = 0
        self.tool_sessions = set()
        self.drafts = {}
        self.dead = set()  # chats that are full or wedged; the soak leaves them like a user would

    # ---------- adb / events ----------
    def adb(self, *cmd, check=True, timeout=120):
        r = subprocess.run(['adb', '-s', self.a.serial, *cmd], capture_output=True, text=True, timeout=timeout)
        if check:
            r.check_returncode()
        return r.stdout.strip()

    def pid(self):
        return self.adb('shell', f'pidof {PKG}', check=False)

    def pump(self):
        with self.log_path.open('r', errors='replace') as f:
            f.seek(self.offset)
            chunk = f.read()
            self.offset = f.tell()
        if not chunk:
            return
        text = self.buf + chunk
        lines = text.split('\n')
        self.buf = lines.pop()
        block = '\n'.join(lines)
        self.logtext_tail = (self.logtext_tail + '\n' + block)[-200000:]
        for line in lines:
            self.scan_line(line)
            m = EVENT_RE.search(line)
            if m:
                detail = decode_detail(m.group(3) or '')
                self.events.append({'i': len(self.events), 'ms': int(m.group(1)), 'name': m.group(2),
                                    'detail': detail})

    def scan_line(self, line):
        for rx, kind in ((CRASH_RE, 'crash-line'), (DSP_RE, 'dsp-error'), (LMK_RE, 'lmk-kill')):
            if rx.search(line):
                self.step_flags.setdefault(kind, []).append(line[-300:])
        if BUSY_RE.search(line):
            self.step_flags['busy'] = self.step_flags.get('busy', 0) + 1
        m = ABORT_RE.search(line)
        if m:
            self.step_flags.setdefault('abort_path', []).append(m.group(0)[:160])
        for rx, kind in LOAD_RES:
            if rx.search(line):
                self.step_flags.setdefault('load_path', []).append(kind)

    def mark(self):
        self.pump()
        return len(self.events)

    def since(self, mark, name=None):
        self.pump()
        return [e for e in self.events[mark:] if name is None or e['name'] == name]

    def command(self, action, **params):
        self.cmd_n += 1
        body = {'id': f'{self.a.seed}-{self.cmd_n}-{time.time_ns()}', 'action': action, **params}
        local = self.dir / f'.cmd-{self.a.serial}.json'
        local.write_text(json.dumps(body))
        self.adb('push', str(local), f'{FILES}/crash-command-next.json')
        self.adb('shell', f'mv {FILES}/crash-command-next.json {FILES}/crash-command.json')

    def wait_event(self, mark, name, timeout, at_least=1):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = self.since(mark, name)
            if len(found) >= at_least:
                return found[at_least - 1]
            errs = self.since(mark, 'error')
            if errs:
                return {'name': 'error', 'detail': errs[-1]['detail']}
            if not self.alive():
                return None
            time.sleep(0.2)
        return None

    def alive(self):
        p = self.pid()
        return bool(p) and p == self.pid0

    def ask(self, action, reply, timeout=60, **params):
        m = self.mark()
        self.command(action, **params)
        e = self.wait_event(m, reply, timeout)
        return e['detail'] if e else None

    def status(self):
        return self.ask('status', 'status', 30)

    def wait_idle(self, mark, timeout, need_start=False):
        """Idle = every completion started since mark has ended, and the store says
        not generating / not stopping / not loading on two polls in a row."""
        deadline = time.monotonic() + timeout
        calm = 0
        grace = time.monotonic() + 3
        while time.monotonic() < deadline:
            if not self.alive():
                return 'process-gone'
            starts = len(self.since(mark, 'completion:start'))
            ends = len(self.since(mark, 'completion:settled')) + len(self.since(mark, 'completion:error'))
            if need_start and starts == 0 and time.monotonic() < grace:
                time.sleep(0.3)
                continue
            if starts <= ends:
                st = self.status()
                if st and not st.get('generating') and not st.get('stopping') and not st.get('loading'):
                    calm += 1
                    if calm >= 2:
                        return 'idle'
                else:
                    calm = 0
                time.sleep(0.8)
            else:
                calm = 0
                time.sleep(1.0)
        return 'timeout'

    # ---------- steps ----------
    def step_row(self, k, action, **extra):
        return {'seed': self.a.seed, 'step': k, 'action': action, 't': time.time(), **extra}

    def completions(self, mark):
        return [e['detail'] for e in self.since(mark, 'completion:settled') if isinstance(e['detail'], dict)]

    def prompt_short(self):
        if self.rng.random() < 0.3:
            name, value = self.rng.choice(FACTS)
            return f'Remember this: the {name} is {value}. Reply with OK.'
        return self.rng.choice(SHORT)

    def prompt_long(self):
        words = self.rng.choice([240, 480, 900, 1400]) if self.a.max_words >= 1400 else \
            self.rng.choice([w for w in (240, 480, 900) if w <= self.a.max_words] or [self.a.max_words])
        name, value = self.rng.choice(FACTS)
        ask = self.rng.choice(['Describe the data in two sentences.', 'Now write a detailed analysis of the records.',
                               f'What is the {name}? Then summarize the records in one sentence.'])
        return f'The {name} is {value}. Read the following data.\n{filler(words)}\n{ask}'

    def send(self, prompt, image=None, stop=None, then_send=None, tool=False):
        params = {'prompt': prompt}
        if image:
            params['image'] = image
        if stop:
            params['stopOn'], params['stopAfterMs'] = stop
            if then_send:
                params['thenSend'] = then_send
        if tool:
            params['sleepMs'] = self.rng.choice([1500, 4000, 8000])
            self.command('send-tool', **params)
        else:
            self.command('send', **params)

    def random_stop(self, kinds):
        kind = self.rng.choice(kinds)
        if kind == 'send':
            return ('send', self.rng.choice([0, 20, 100, 400, 1200]))
        if kind == 'completion-start':
            return ('completion-start', self.rng.choice([0, 50, 300, 1000, 2500]))
        if kind == 'first-token':
            return ('first-token', self.rng.choice([0, 200, 800, 2000]))
        return ('tool-start', self.rng.choice([0, 500, 2000]))

    def chat_state(self):
        return self.ask('chat-state', 'chat-state', 30, ids=self.sessions)

    def ensure_session_known(self, st):
        if st and st.get('active') and st['active'] not in self.sessions:
            self.sessions.append(st['active'])

    def run_step(self, k, spec=None):
        a = self.a
        if spec is not None:
            self.rng = ReplayRng(spec.get('rng', []), self)
        else:
            self.rng.log = []
        weights = {
            'send-short': 14, 'send-long': 8, 'stop': 18, 'stop-then-send': 10,
            'regenerate': 7, 'edit': 6, 'switch-session': 7, 'new-chat': 4,
            'switch-mid': 4, 'background': 6, 'model-switch': 4 if a.model_b else 0,
            'release-mid': 4, 'tool': 8 if a.tools else 0, 'tool-stop': 8 if a.tools else 0,
            'image': 8 if self.mmproj and a.image else 0, 'image-stop': 8 if self.mmproj and a.image else 0,
            'draft': 3 if a.drafts else 0,
        }
        skip = a.skip.split(',') if a.skip else []
        if a.control:
            skip += ['stop', 'stop-then-send', 'switch-mid', 'background', 'model-switch', 'release-mid',
                     'tool-stop', 'image-stop']
        for name in skip:
            weights[name] = 0
        action = spec['action'] if spec is not None else self.rng.choices(list(weights), list(weights.values()))[0]
        if spec is not None:
            self.rng.log.append(action)
        before = self.chat_state()
        self.ensure_session_known(before)
        acted = before.get('active') if before else None
        row = self.step_row(k, action, session=acted)
        self.step_flags = {}
        m = self.mark()
        oracle_ok = False
        T = a.step_timeout

        has_assistant = bool(before and acted and any(
            s['id'] == acted and s['messages'] >= 2 for s in before.get('sessions', [])))

        if action in ('regenerate', 'edit') and not has_assistant:
            action = row['action'] = 'send-short'

        if action == 'send-short':
            p = self.prompt_short()
            row['prompt'] = p[:80]
            self.send(p)
            row['idle'] = self.wait_idle(m, T, need_start=True)
            oracle_ok = True
        elif action == 'send-long':
            p = self.prompt_long()
            row['prompt_len'] = len(p)
            self.send(p)
            row['idle'] = self.wait_idle(m, T, need_start=True)
            oracle_ok = True
            if self.long_session is None:
                self.long_session = acted
        elif action in ('stop', 'stop-then-send'):
            long = self.rng.random() < 0.6
            p = self.prompt_long() if long else self.prompt_short()
            stop = self.random_stop(['send', 'completion-start', 'completion-start', 'first-token', 'first-token'])
            follow = self.prompt_short() if action == 'stop-then-send' else None
            row.update(prompt_len=len(p), stop=stop, then_send=bool(follow))
            self.send(p, stop=stop, then_send=follow)
            row['idle'] = self.wait_idle(m, T, need_start=True)
            # the follow-up (if any) is the last completion; uninterrupted -> oracle
            oracle_ok = bool(follow)
        elif action == 'regenerate':
            stop = self.random_stop(['completion-start', 'first-token']) \
                if self.rng.random() < 0.4 and not a.control else None
            params = {}
            if stop:
                params['stopOn'], params['stopAfterMs'] = stop
            row['stop'] = stop
            self.command('regenerate', **params)
            row['idle'] = self.wait_idle(m, T, need_start=True)
            oracle_ok = not stop
            self.drafts[acted] = ''
        elif action == 'edit':
            stop = self.random_stop(['completion-start', 'first-token']) \
                if self.rng.random() < 0.3 and not a.control else None
            params = {'prompt': self.rng.choice(EDITS)}
            if stop:
                params['stopOn'], params['stopAfterMs'] = stop
            row['stop'] = stop
            self.command('edit', **params)
            row['idle'] = self.wait_idle(m, T, need_start=True)
            oracle_ok = not stop
            self.drafts[acted] = ''
        elif action == 'switch-session':
            others = [s for s in self.sessions if s != acted and s not in self.dead]
            if others:
                target = self.long_session if (self.long_session in others and self.rng.random() < 0.5) \
                    else self.rng.choice(others)
                row['to'] = target
                d = self.ask('session', 'session:done', 30, to=target)
                row['session_done'] = d
            else:
                row['to'] = 'new'
                self.ask('session', 'session:done', 30, to='new')
            row['idle'] = 'idle'
        elif action == 'new-chat':
            self.ask('session', 'session:done', 30, to='new')
            row['idle'] = 'idle'
        elif action == 'switch-mid':
            p = self.prompt_long()
            self.send(p)
            e = self.wait_event(m, 'completion:start', 120)
            time.sleep(self.rng.choice([0.2, 1.0, 3.0]))
            others = [s for s in self.sessions if s != acted and s not in self.dead]
            target = self.rng.choice(others) if others and self.rng.random() < 0.7 else 'new'
            row.update(prompt_len=len(p), to=target, started=bool(e))
            self.ask('session', 'session:done', 30, to=target)
            row['idle'] = self.wait_idle(m, T)
            oracle_ok = True
        elif action == 'background':
            mid = self.rng.random() < 0.7
            row['mid'] = mid
            if mid:
                self.send(self.prompt_long())
                self.wait_event(m, 'completion:start', 120)
                time.sleep(self.rng.choice([0.0, 0.5, 2.0, 5.0]))
            self.adb('shell', 'input keyevent KEYCODE_HOME')
            rel = None
            if self.wait_event(m, 'release:start', 20):
                rel = self.wait_event(m, 'release:settled', T)
            row['released'] = bool(rel)
            starts = [e['ms'] for e in self.since(m, 'release:start')]
            ends = [e['ms'] for e in self.since(m, 'release:settled')]
            row['release_ms'] = ends[-1] - starts[-1] if starts and ends else None
            time.sleep(self.rng.choice([2, 4, 8]))
            self.adb('shell', f'am start -n {PKG}/com.pocketpal.MainActivity')
            w = self.wait_event(m, 'wrapped', 300) if rel else None
            row['reloaded'] = bool(w)
            row['idle'] = self.wait_idle(m, T)
            time.sleep(1)
        elif action == 'model-switch':
            mid = self.rng.random() < 0.5
            row['mid'] = mid
            if mid:
                self.send(self.prompt_long())
                self.wait_event(m, 'completion:start', 120)
                time.sleep(self.rng.choice([0.2, 1.5]))
            mm = self.mark()
            sw = self.ask('switch', 'switched', 600, filename=a.model_b, mmproj=a.mmproj_b)
            row['to_b'] = bool(sw) and not (isinstance(sw, str))
            row['idle_b'] = self.wait_idle(mm, T)
            if self.rng.random() < 0.6:
                mm = self.mark()
                self.send(self.prompt_short(), stop=self.random_stop(['first-token']) if self.rng.random() < 0.3 else None)
                row['b_send'] = self.wait_idle(mm, T, need_start=True)
            mm = self.mark()
            back = self.ask('switch', 'switched', 600, filename=a.model_a, mmproj=a.mmproj_a)
            row['back'] = bool(back)
            row['idle'] = self.wait_idle(mm, T)
        elif action == 'release-mid':
            self.send(self.prompt_long())
            self.wait_event(m, 'completion:start', 120)
            time.sleep(self.rng.choice([0.0, 0.5, 2.0]))
            manual = self.rng.random() < 0.5
            row['manual'] = manual
            self.ask('release', 'manual-release:done', T, manual=manual)
            starts = [e['ms'] for e in self.since(m, 'release:start')]
            ends = [e['ms'] for e in self.since(m, 'release:settled')]
            row['release_ms'] = ends[-1] - starts[-1] if starts and ends else None
            row['idle_after_release'] = self.wait_idle(m, T)
            ld = self.ask('load', 'loaded', 600, **self.load_params())
            row['reloaded'] = bool(ld)
            row['idle'] = 'idle'
        elif action in ('tool', 'tool-stop'):
            stop = self.random_stop(['tool-start', 'tool-start', 'completion-start', 'first-token']) \
                if action == 'tool-stop' else None
            row['stop'] = stop
            self.send(self.rng.choice(TOOL_PROMPTS), tool=True, stop=stop,
                      then_send=self.prompt_short() if stop and self.rng.random() < 0.4 else None)
            self.tool_sessions.add(acted)
            row['idle'] = self.wait_idle(m, T, need_start=True)
            row['tool_started'] = len(self.since(m, 'tool:start'))
            oracle_ok = not stop
        elif action in ('image', 'image-stop'):
            stop = self.random_stop(['completion-start', 'completion-start', 'first-token']) \
                if action == 'image-stop' else None
            row['stop'] = stop
            self.send(self.rng.choice(IMAGE_PROMPTS), image=a.image, stop=stop,
                      then_send=self.prompt_short() if stop and self.rng.random() < 0.4 else None)
            row['idle'] = self.wait_idle(m, T, need_start=True)
            oracle_ok = not stop
        elif action == 'draft':
            row.update(self.draft_step(acted))
            row['idle'] = 'idle'

        # ---- health + invariants ----
        self.pump()
        row['completions'] = [{k2: c.get(k2) for k2 in ('interrupted', 'prompt_n', 'tokens_evaluated', 'tokens_cached',
                                                       'tokens_predicted', 'stopped_eos', 'stopped_limit', 'tool_calls')}
                              | {'hash': (c.get('text') or {}).get('hash'), 'len': (c.get('text') or {}).get('len')}
                              for c in self.completions(m)]
        row['errors'] = [e['detail'] for e in self.since(m) if e['name'] in ('completion:error', 'chat-send:error',
                                                                          'error', 'regenerate:error', 'edit:error')]
        row['flags'] = self.step_flags
        if any(c.get('interrupted') for c in row['completions']) or self.step_flags.get('abort_path'):
            self.step_flags['abort_kind'] = classify_aborts(self.step_flags, row['completions'])
        alive = self.alive()
        row['alive'] = alive
        if not alive or self.step_flags.get('crash-line'):
            self.finding('crash' if self.step_flags.get('crash-line') or not self.pid() else 'process-changed',
                         k, row)
            return row, False
        if row.get('idle') == 'timeout' or any(v == 'timeout' for kk, v in row.items() if kk.startswith('idle')):
            row['status_at_timeout'] = self.status()
            row['diagnostics'] = self.diagnose(k)
            self.finding('hang', k, row)
            return row, False
        if self.step_flags.get('dsp-error'):
            self.finding('dsp-error', k, row)

        after = self.chat_state()
        self.ensure_session_known(after)
        row['state'] = {'active': after and after.get('active'),
                        'sessions': after and [(s['id'][-6:], s['messages']) for s in after.get('sessions', [])]}
        self.check_sessions(k, row, before, after, acted, action)

        if any(re.search(r'Context is full|Not enough context|Unable to generate parser', str(e)) for e in row['errors']):
            gone = (after or {}).get('active') or acted
            if gone:
                self.dead.add(gone)
                row['left_dead_chat'] = gone
                self.ask('session', 'session:done', 30, to='new')
        last = self.completions(m)[-1:] or [None]
        last = last[0]
        # Any step whose last completion ran to its end is eligible, except the ones that
        # end on a different context than that completion's (model switch, reload).
        oracle_ok = oracle_ok or action in ('stop', 'regenerate', 'edit', 'tool-stop', 'image-stop')
        draws = list(self.rng.log[1:])
        want = False
        if oracle_ok and last and not last.get('interrupted') and not row['errors']:
            want = spec.get('oracle', False) if spec is not None else self.rng.random() < a.oracle_rate
        row['script'] = {'action': row['action'], 'rng': draws, 'oracle': want}
        if want:
            row['oracle'] = self.oracle(k, last)
            if not self.alive():
                self.finding('crash', k, row)
                return row, False
        return row, True

    def diagnose(self, k):
        """Thread states and freezer/ANR evidence for a hang, saved next to the seed."""
        pid = self.pid()
        out = {}
        cmds = {
            'threads': f'ps -T -o TID,STAT,WCHAN:32,NAME -p {pid}',
            'task_stat': f'for t in /proc/{pid}/task/*; do echo $(cat $t/comm) $(cut -d" " -f3 $t/stat) $(cat $t/wchan 2>/dev/null); done',
            'activity': 'dumpsys activity processes | grep -i -A3 pocketpalai.e2e | head -40',
            'freezer': f'cat /proc/{pid}/cgroup; dumpsys activity | grep -i frozen | head',
            'debuggerd': f'debuggerd -b {pid} 2>&1 | head -400',
            'window': 'dumpsys window | grep -E "mCurrentFocus|mScreenOn|mAwake" | head',
        }
        for name, cmd in cmds.items():
            try:
                out[name] = self.adb('shell', cmd, check=False, timeout=60)
            except subprocess.TimeoutExpired:
                out[name] = 'timeout'
        (self.dir / f'seed-{self.a.seed}-hang-step{k}.txt').write_text(
            '\n\n'.join(f'== {n}\n{v}' for n, v in out.items()))
        return {n: v[:300] for n, v in out.items()}

    def draft_step(self, acted):
        if not acted:
            return {'draft_skipped': 'new-chat screen'}
        word = self.rng.choice(['pending', 'unsent', 'draftcheck', 'halfway']) + str(self.rng.randint(10, 99))
        try:
            tree = ET.fromstring(self.ui_xml())
            node = next(n for n in tree.iter('node') if 'chat-input' in n.get('resource-id', ''))
            x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
            self.adb('shell', f'input tap {(x1 + x2) // 2} {(y1 + y2) // 2}')
            time.sleep(0.4)
            self.adb('shell', f'input text {word}')
            time.sleep(1.2)
            self.adb('shell', 'input keyevent KEYCODE_BACK')
        except (StopIteration, RuntimeError, ET.ParseError) as error:
            return {'draft_error': str(error)}
        self.drafts[acted or '__new_chat__'] = word
        return {'draft': word}

    def ui_xml(self, tries=6):
        for _ in range(tries):
            self.adb('shell', 'rm -f /sdcard/soak-ui.xml', check=False)
            self.adb('shell', 'uiautomator dump /sdcard/soak-ui.xml', check=False)
            xml = self.adb('shell', 'cat /sdcard/soak-ui.xml', check=False)
            if xml.startswith('<?xml'):
                return xml
            time.sleep(0.5)
        raise RuntimeError('uiautomator dump failed')

    def check_sessions(self, k, row, before, after, acted, action):
        if not before or not after:
            return
        prev = {s['id']: s for s in before.get('sessions', [])}
        now = {s['id']: s for s in after.get('sessions', [])}
        # switch-mid: the reply belongs to the origin session; every other session must be untouched.
        changed_ok = {acted}
        bad = []
        for sid, s in prev.items():
            if sid in changed_ok:
                continue
            n = now.get(sid)
            if n is None:
                bad.append({'session': sid, 'issue': 'vanished'})
            elif n['messages'] != s['messages'] or (n.get('last') or {}).get('hash') != (s.get('last') or {}).get('hash'):
                bad.append({'session': sid, 'issue': 'changed', 'before': s['messages'], 'after': n['messages']})
        if acted is None and action in ('send-short', 'send-long', 'stop', 'stop-then-send', 'tool', 'tool-stop',
                                        'image', 'image-stop', 'switch-mid', 'background', 'release-mid',
                                        'model-switch'):
            pass  # a send from the new-chat screen creates the session it lands in
        for sid, want in self.drafts.items():
            got = (now.get(sid) or {}).get('draft') if sid != '__new_chat__' else after.get('draftNew')
            if sid != '__new_chat__' and sid not in now:
                continue
            if sid == after.get('active'):
                continue  # ChatView saves the composer into the draft map only when the chat is left
            if want and got != want:
                bad.append({'session': sid, 'issue': 'draft', 'want': want, 'got': got})
            for other, o in now.items():
                if want and other != sid and o.get('draft') == want:
                    bad.append({'session': other, 'issue': 'draft-leak', 'draft': want, 'from': sid})
        if bad:
            row['session_issues'] = bad
            self.finding('session', k, row)

    def oracle(self, k, warm):
        m = self.mark()
        self.command('replay')
        e = self.wait_event(m, 'replay:settled', self.a.step_timeout)
        if not e or e.get('name') == 'error':
            res = {'result': 'no-replay', 'detail': e and e.get('detail')}
            self.finding('oracle-error', k, {'oracle': res})
            return res
        cold = e['detail']
        wt, ct = warm.get('text') or {}, cold.get('text') or {}
        res = {'result': 'match' if wt.get('hash') == ct.get('hash') else 'MISMATCH',
               'warm_hash': wt.get('hash'), 'cold_hash': ct.get('hash'), 'warm_len': wt.get('len'),
               'cold_len': ct.get('len'), 'params_same': warm.get('params') == cold.get('params'),
               'warm_prompt_n': warm.get('prompt_n'), 'warm_tokens_evaluated': warm.get('tokens_evaluated'),
               'warm_tokens_cached': warm.get('tokens_cached'), 'cold_prompt_n': cold.get('prompt_n')}
        if res['result'] != 'match':
            w, c = wt.get('full') or '', ct.get('full') or ''
            prefix = 0
            while prefix < min(len(w), len(c)) and w[prefix] == c[prefix]:
                prefix += 1
            res.update(warm_text=w, cold_text=c, common_prefix=prefix,
                       similarity=round(difflib.SequenceMatcher(None, w, c).ratio(), 3))
            self.finding('oracle-mismatch', k, {'oracle': res})
        self.oracles.append(res['result'])
        # the replay left a fresh context holding this conversation; settle before the next step
        self.wait_idle(self.mark(), 60)
        return res

    def batch_replays(self, batches):
        """Cold replays of the last completion's params at other n_batch/n_ubatch values: does
        the cold text itself depend on how the prompt is split into batches?"""
        res = []
        for b in batches:
            params = dict(self.load_params(), n_batch=b, n_ubatch=b)
            if not isinstance(self.ask('load', 'loaded', 600, **params), dict):
                res.append({'batch': b, 'error': 'load'})
                continue
            m = self.mark()
            self.command('replay')
            e = self.wait_event(m, 'replay:settled', self.a.step_timeout)
            d = (e or {}).get('detail') or {}
            t = d.get('text') or {} if isinstance(d, dict) else {}
            res.append({'batch': b, 'hash': t.get('hash'), 'len': t.get('len'), 'text': t.get('full'),
                        'prompt_n': d.get('prompt_n') if isinstance(d, dict) else None})
            print(json.dumps({'batch_replay': b, 'hash': t.get('hash')}), flush=True)
            self.wait_idle(self.mark(), 60)
        self.ask('load', 'loaded', 600, **self.load_params())
        return {'step': 'batch-replays', 'replays': res}

    def finding(self, kind, k, row):
        item = {'kind': kind, 'seed': self.a.seed, 'step': k, 'tag': self.tag}
        if kind != 'oracle-mismatch' and kind != 'oracle-error':
            item['row'] = {kk: v for kk, v in row.items() if kk != 'state'}
        else:
            item.update(row)
        self.findings.append(item)
        print('FINDING', json.dumps(item)[:600], flush=True)

    def load_params(self):
        a = self.a
        return dict(filename=a.model_a, mmproj=a.mmproj_a, threads=a.threads, n_ctx=a.n_ctx, n_batch=a.batch,
                    n_ubatch=a.batch, deterministic=True, backend=a.backend, n_predict=a.n_predict,
                    speculative=a.speculative, draft=getattr(a, 'draft', None))

    # ---------- driver ----------
    def run(self):
        a = self.a
        started = time.time()
        logcat = None
        rows = []
        ok = True
        out = self.rows_path.open('w')
        try:
            self.adb('shell', 'input keyevent KEYCODE_WAKEUP')
            self.adb('shell', 'wm dismiss-keyguard', check=False)
            self.adb('shell', 'svc power stayon usb', check=False)
            self.adb('shell', f'am force-stop {PKG}')
            self.adb('shell', f'rm -f {FILES}/crash-command.json')
            apk = self.adb('shell', f'pm path {PKG}').split(':', 1)[1]
            apk_sha = self.adb('shell', f'sha256sum {apk}').split()[0]
            if a.expect_sha and apk_sha != a.expect_sha:
                raise RuntimeError(f'installed APK {apk_sha} is not the expected build {a.expect_sha}')
            if not a.expect_sha:
                print('WARNING: no --expect-sha; the installed APK is not checked', flush=True)
            self.adb('logcat', '-c', check=False)
            logcat = subprocess.Popen(['adb', '-s', a.serial, 'logcat', '-v', 'epoch'],
                                      stdout=self.log_path.open('w'), stderr=subprocess.STDOUT)
            self.step_flags = {}
            self.adb('shell', f'am start -n {PKG}/com.pocketpal.MainActivity')
            time.sleep(8)
            self.pid0 = self.pid()
            head = {'seed': a.seed, 'step': -1, 'action': 'setup', 'apk_sha256': apk_sha, 'pid': self.pid0,
                    'settings': {k: v for k, v in vars(a).items()}}
            m = self.mark()
            self.command('release')
            self.wait_event(m, 'manual-release:done', 120)
            self.ask('wipe-sessions', 'wipe-sessions:done', 60)
            loaded = self.ask('load', 'loaded', 600, **self.load_params())
            head['loaded'] = loaded
            if not isinstance(loaded, dict):
                raise RuntimeError(f'load failed: {loaded}')
            self.ask('session', 'session:done', 30, to='new')
            out.write(json.dumps(head) + '\n')
            out.flush()
            print(json.dumps({'setup': True, 'ctx': loaded.get('ctx'), 'backend': loaded.get('backend')}), flush=True)
            n_steps = len(self.script) if self.script is not None else a.steps
            for k in range(n_steps):
                try:
                    row, ok = self.run_step(k, self.script[k] if self.script is not None else None)
                except subprocess.TimeoutExpired as error:
                    row, ok = {'seed': a.seed, 'step': k, 'harness_error': str(error)}, False
                rows.append(row)
                out.write(json.dumps(row) + '\n')
                out.flush()
                print(json.dumps({'step': k, 'action': row.get('action'), 'idle': row.get('idle'),
                                  'oracle': (row.get('oracle') or {}).get('result'),
                                  'n': len(row.get('completions', []))}), flush=True)
                if not ok:
                    break
            if ok and getattr(a, 'extra_replays', None):
                out.write(json.dumps(self.batch_replays([int(b) for b in a.extra_replays.split(',')])) + '\n')
                out.flush()
        except Exception as error:  # harness failure: record and stop this seed
            self.findings.append({'kind': 'harness', 'seed': a.seed, 'error': repr(error)})
            print('HARNESS', repr(error), flush=True)
            ok = False
        finally:
            time.sleep(2)
            self.pump()
            if logcat:
                logcat.terminate()
                logcat.wait(timeout=10)
                subprocess.run(['gzip', '-f', str(self.log_path)], check=False)
            out.close()
            summary = {'tag': self.tag, 'seed': a.seed, 'serial': a.serial, 'model': a.model_a,
                       'backend': a.backend, 'steps_done': len(rows), 'steps': a.steps, 'completed': ok,
                       'oracles': len(self.oracles), 'mismatches': self.oracles.count('MISMATCH'),
                       'findings': self.findings, 'minutes': round((time.time() - started) / 60, 1),
                       'actions': {}}
            for r in rows:
                summary['actions'][r.get('action')] = summary['actions'].get(r.get('action'), 0) + 1
            with self.summary_path.open('a') as f:
                f.write(json.dumps(summary) + '\n')
            print('SUMMARY', json.dumps(summary)[:2000], flush=True)
        return ok


def out_root():
    return pathlib.Path(os.environ.get('LLAMA_SOAK_OUT') or HERE / 'out')


def run(args, root):
    return Soak(args, root).run()


def main(argv):
    import argparse
    p = argparse.ArgumentParser(prog='run.py --mode soak')
    p.add_argument('--mode', choices=['soak'])
    p.add_argument('--serial', required=True)
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--steps', type=int, default=40)
    p.add_argument('--model-a', required=True)
    p.add_argument('--mmproj-a')
    p.add_argument('--model-b', help='model-switch target (omit to skip model switches)')
    p.add_argument('--mmproj-b')
    p.add_argument('--backend', choices=['cpu', 'gpu', 'hexagon'], default='cpu')
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--n-ctx', type=int, default=4096)
    p.add_argument('--batch', type=int, default=512)
    p.add_argument('--n-predict', type=int, default=160, help='cap on every completion (deterministic load)')
    p.add_argument('--max-words', type=int, default=1400, help='longest filler prompt (words)')
    p.add_argument('--speculative', action='store_true')
    p.add_argument('--draft', help='separate draft model file (paired speculative; needs --speculative)')
    p.add_argument('--tools', action='store_true', help='include tool / tool-stop steps (tool pal + e2e_sleep)')
    p.add_argument('--image', help='image file in the files dir (vision steps need --mmproj-a)')
    p.add_argument('--drafts', action='store_true', help='include composer draft steps (uiautomator)')
    p.add_argument('--oracle-rate', type=float, default=0.6)
    p.add_argument('--step-timeout', type=float, default=900)
    p.add_argument('--skip', default='', help='comma-separated step names to disable')
    p.add_argument('--control', action='store_true',
                   help='no Stop, release, background, switch-mid or model switch: the numerics baseline')
    p.add_argument('--expect-sha', default=os.environ.get('LLAMA_SOAK_APK_SHA', ''),
                   help='refuse to run unless the installed APK has this sha256 (default $LLAMA_SOAK_APK_SHA; '
                        'empty skips the check)')
    p.add_argument('--tag')
    p.add_argument('--script', help='JSONL of step specs ({action, rng, oracle}, as recorded in each row\'s '
                                     '"script" field); runs exactly these steps instead of seeded random ones')
    p.add_argument('--extra-replays', help='after the last step: cold replays at these n_batch (=n_ubatch) values')
    args = p.parse_args(argv)
    ok = run(args, out_root())
    raise SystemExit(0 if ok else 3)
