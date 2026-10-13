"""Android device driver for the release/stop matrix (com.pocketpalai.e2e).

Drives the E2E-only CrashReproAdapter (app/harness.patch) through
<ExternalDirectoryPath>/crash-command.json, taps Stop/Send for real via
uiautomator bounds, and records one JSON per attempt in <out>/runs/ plus a
summary row in <out>/result.json (<out> = $LLAMA_SOAK_OUT, default ./out).

`run.py --mode soak ...` hands off to soak.py (random soak) or, with
--scenario, to triage.py (fixed scenarios). See README.md.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import time
import sys
import xml.etree.ElementTree as ET

if '--mode' in sys.argv and sys.argv[sys.argv.index('--mode') + 1:][:1] == ['soak']:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    if '--scenario' in sys.argv:
        import triage
        triage.main(sys.argv[1:])
        raise SystemExit(0)
    import soak
    soak.main(sys.argv[1:])

PKG = 'com.pocketpalai.e2e'
FILES = f'/sdcard/Android/data/{PKG}/files'
MODES = ['baseline', 'background', 'release', 'switch', 'stop-send',
         'stop-tool-exec', 'stop-tool-followup',
         'mtp-stop', 'stop-retry', 'wait-gate', 'wait-switch', 'dc1', 'fault', 'dc4']
STOP_MODES = ('stop-send', 'mtp-stop', 'stop-retry')
IMAGE_TURN = 'Describe the image in one sentence.'
SPC_ABORT_RE = re.compile(r'llama_decode\(ctx_dft\)(?: head=\S+)? failed rc=2|failed to decode draft batch, ret = 2')
ABORT_RE = re.compile(r'Decoding interrupted, (restored state checkpoint|no usable state checkpoint \(([^)]*)\)|n_past:)')
CHUNKS_RE = re.compile(r'Evaluating chunks: n_past=(\d+)')
FACT_FIRST = 'The vault code is 4721.'
FACT_LAST = "The courier's name is Ilse."
FOLLOW_UP = "What are the vault code and the courier's name? Answer in one line."
DC1_PROMPT = ("The vault code is 4721. The courier's name is Ilse. The meeting is at the old harbour. "
              "What is the vault code? Answer in one sentence.")
DC1_OTHER = "Where is the meeting? Answer in one sentence."
CRASH_RE = re.compile(r'Fatal signal|SIGSEGV|SIGABRT|backtrace:')
EVENT_RE = re.compile(r"\[CRASH_REPRO\]'?,? (\d+),? '([^']+)'(?:,? '(.*)')?")

parser = argparse.ArgumentParser()
parser.add_argument('--serial', default=os.environ.get('ANDROID_SERIAL'), required=not os.environ.get('ANDROID_SERIAL'))
parser.add_argument('--mode', choices=MODES, required=True)
parser.add_argument('--threads', type=int, default=4)
parser.add_argument('--batch', type=int, default=512)
parser.add_argument('--words', type=int, default=1600)
parser.add_argument('--delay', type=float, default=0.75)
parser.add_argument('--model-a', default='SmolLM2-1.7B-Instruct-Q4_K_M.gguf')
parser.add_argument('--model-b', default='qwen2.5-coder-1.5b-instruct-q6_k.gguf')
parser.add_argument('--manual', action='store_true', help='release via manualReleaseContext (Models > unload)')
parser.add_argument('--sleep-ms', type=int, default=15000)
parser.add_argument('--attempt', required=True)
parser.add_argument('--timeout', type=float, default=3000)
parser.add_argument('--capture', action='store_true')
parser.add_argument('--speculative', action='store_true', help='enable MTP / speculative decoding before load')
parser.add_argument('--stop-at', choices=['prefill', 'gen'], default='prefill',
                    help='gen: wait for completion:first-token plus --delay before Stop')
parser.add_argument('--mmproj', help='projector filename in the files dir, passed to initContext')
parser.add_argument('--image', help='image filename in the files dir')
parser.add_argument('--image-turn', action='store_true',
                    help='send the image in a settled short turn before the stopped text turn')
parser.add_argument('--follow-up-first-token', action='store_true',
                    help='mtp-stop: end once the follow-up streams a token (alive, not busy) instead of waiting for it to settle')
parser.add_argument('--to', default='other', help="wait-switch target: 'other' (chat B) or 'new'")
parser.add_argument('--bg-hold', type=float, default=0,
                    help='background mode: stay backgrounded this many seconds after release:settled')
parser.add_argument('--force-stop', action='store_true',
                    help='dc1: stopCompletion right after getFormattedChat resolves (no abort sent)')
parser.add_argument('--no-reapply', action='store_true',
                    help='dc1: skip the patch re-apply (negative control)')
parser.add_argument('--warm-turn', action='store_true',
                    help='stop modes: a settled "Reply with OK" turn first, so the Stop lands on a warm context')
parser.add_argument('--dc1-plain', action='store_true',
                    help='dc1: plain send in a new chat (no tool pal), deterministic, then follow-up + replay')
parser.add_argument('--dc1-follow-up', choices=['same', 'different', 'ok'], default='ok',
                    help='dc1: follow-up text; same = the stopped prompt again')
parser.add_argument('--fault-mode', choices=['abort', 'throw', 'none'], default='none',
                    help='fault: written to f1-fault.txt; the fault build reads it on the 20th MTP refill')
args = parser.parse_args()
if args.mode == 'fault':
    args.stop_at = 'gen'

root = pathlib.Path(os.environ.get('LLAMA_SOAK_OUT') or pathlib.Path(__file__).resolve().parent / 'out')
runs = root / 'runs'
runs.mkdir(parents=True, exist_ok=True)
caps = root / 'captures'
caps.mkdir(exist_ok=True)
out = runs / f'{args.attempt}.json'
if out.exists():
    raise RuntimeError('Attempt already exists; use a new attempt name')
logfile = runs / f'{args.attempt}-logcat.txt'
events = []
outcome = {'attempt': args.attempt, 'mode': args.mode, 'threads': args.threads}


def adb(*cmd, check=True):
    result = subprocess.run(['adb', '-s', args.serial, *cmd], capture_output=True, text=True)
    if check:
        result.check_returncode()
    return result.stdout.strip()


def pid():
    return adb('shell', f'pidof {PKG}', check=False)


def event(name, **detail):
    item = {'event': name, 'time': time.time(), **detail}
    events.append(item)
    print(json.dumps(item), flush=True)


def command(action, **params):
    body = {'id': str(time.time_ns()), 'action': action, **params}
    local = runs / f'{args.attempt}-command.json'
    local.write_text(json.dumps(body))
    adb('push', str(local), f'{FILES}/crash-command-next.json')
    adb('shell', f'mv {FILES}/crash-command-next.json {FILES}/crash-command.json')
    event('command', action=action, **{k: v for k, v in params.items() if k != 'prompt'})


def logs():
    return logfile.read_text(errors='replace') if logfile.exists() else ''


RUN_START_MS = int(time.time() * 1000)


def app_events():
    found = []
    for match in EVENT_RE.finditer(logs()):
        if int(match.group(1)) < RUN_START_MS - 3000:
            continue
        found.append({'ms': int(match.group(1)), 'name': match.group(2), 'detail': match.group(3)})
    return found


def count(name):
    return sum(1 for e in app_events() if e['name'] == name)


def accept_memory_alert():
    """Tap Continue on the app's low-memory load confirmation (3B model B)."""
    adb('shell', 'uiautomator dump /sdcard/crash-ui.xml', check=False)
    xml = adb('shell', 'cat /sdcard/crash-ui.xml', check=False)
    try:
        tree = ET.fromstring(xml)
    except ET.ParseError:
        return
    for node in tree.iter('node'):
        if node.get('resource-id') == 'android:id/button1':
            x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
            adb('shell', f'input tap {(x1 + x2) // 2} {(y1 + y2) // 2}')
            event('tap', target='memory-alert-continue', text=node.get('text'))
            return


def wait_for(name, timeout=120, at_least=1):
    deadline = time.monotonic() + timeout
    next_alert_check = time.monotonic() + 2
    while time.monotonic() < deadline:
        if count(name) >= at_least:
            event('observed', marker=name, count=at_least)
            return True
        if not pid():
            event('process-gone', marker=name)
            return False
        if name in ('loaded', 'switched') and time.monotonic() > next_alert_check:
            accept_memory_alert()
            next_alert_check = time.monotonic() + 3
        time.sleep(0.1)
    event('timeout', marker=name)
    return False


def last_detail(name):
    matches = [e for e in app_events() if e['name'] == name]
    if not matches or not matches[-1]['detail']:
        return None
    raw = matches[-1]['detail'].replace("\\'", "'")
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def screencap(label):
    if not args.capture:
        return
    path = caps / f'{args.attempt}-{label}.png'
    with path.open('wb') as stream:
        subprocess.run(['adb', '-s', args.serial, 'exec-out', 'screencap', '-p'], stdout=stream, check=True)
    event('capture', label=label, path=str(path.relative_to(root)))


def ui_xml(tries=8):
    for _ in range(tries):
        adb('shell', 'rm -f /sdcard/crash-ui.xml')
        adb('shell', 'uiautomator dump /sdcard/crash-ui.xml', check=False)
        xml = adb('shell', 'cat /sdcard/crash-ui.xml', check=False)
        if xml.startswith('<?xml'):
            return xml
        time.sleep(0.5)
    raise RuntimeError('uiautomator dump failed (UI never idle)')


def bounds(resource):
    tree = ET.fromstring(ui_xml())
    for node in tree.iter('node'):
        if resource in node.get('resource-id', ''):
            x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
            return (x1 + x2) // 2, (y1 + y2) // 2
    raise RuntimeError(f'{resource} not on screen')


def tap(point, label):
    adb('shell', f'input tap {point[0]} {point[1]}')
    event('tap', target=label)


def type_and_send(text):
    tap(bounds('chat-input'), 'chat-input')
    adb('shell', 'input text ' + text.replace(' ', '%s').replace("'", "\\'").replace('?', '\\?'))
    tap(bounds('send-button'), 'send-button')


def long_prompt(with_facts):
    filler = ' '.join(
        f'record{i}: the river crosses the valley and the quiet village has a stone bridge.'
        for i in range(max(1, args.words // 16)))
    if with_facts:
        ask = ('\nNow describe every record above in detail, one paragraph each.'
               if args.stop_at == 'gen' else '')
        return f'{FACT_FIRST} Read the following data.\n{filler}\n{FACT_LAST}{ask}'
    return 'Read the following data and write a detailed analysis:\n' + filler


def detail_of(e):
    raw = (e['detail'] or '').replace("\\'", "'")
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def wait_settled_or_error(total, timeout, first_tokens=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        n = count('completion:settled') + count('completion:error')
        if first_tokens is not None and count('completion:first-token') >= first_tokens:
            event('observed', marker='follow-up-first-token')
            return True
        if n >= total:
            event('observed', marker='settled-or-error', count=total)
            return True
        if not pid():
            event('process-gone', marker='settled-or-error')
            return False
        time.sleep(0.1)
    event('timeout', marker='settled-or-error')
    return False


def wait_stop_point():
    if args.stop_at == 'gen':
        wait_for('completion:first-token', args.timeout, count('completion:first-token') + 1)
    time.sleep(args.delay)


def long_press(resource, label, index=-1):
    tree = ET.fromstring(ui_xml())
    found = [n for n in tree.iter('node') if resource in n.get('resource-id', '')]
    if not found:
        raise RuntimeError(f'{resource} not on screen')
    x1, y1, x2, y2 = map(int, re.findall(r'\d+', found[index].get('bounds')))
    x, y = (x1 + x2) // 2, (y1 + y2) // 2
    adb('shell', f'input swipe {x} {y} {x} {y} 900')
    event('long-press', target=label)


def tap_text(text, label):
    tree = ET.fromstring(ui_xml())
    for node in tree.iter('node'):
        if node.get('text') == text:
            x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
            tap(((x1 + x2) // 2, (y1 + y2) // 2), label)
            return
    raise RuntimeError(f'{text!r} not on screen')


def dump_ui(label):
    xml = ui_xml()
    (runs / f'{args.attempt}-{label}.xml').write_text(xml)
    tree = ET.fromstring(xml)
    send = [n for n in tree.iter('node') if 'send-button' in n.get('resource-id', '')]
    inputs = [n for n in tree.iter('node') if 'chat-input' in n.get('resource-id', '')]
    menu = {n.get('text'): n.get('enabled') for n in tree.iter('node')
            if n.get('text') in ('Copy', 'Regenerate', 'Regenerate with', 'Edit', 'Report Content')}
    texts = [n.get('text') for n in tree.iter('node') if n.get('text')]
    state = {'send_enabled': [n.get('enabled') for n in send],
             'composer': [n.get('text') for n in inputs],
             'stopping': any('Stopping' in t for t in texts),
             'menu': menu}
    event('ui', label=label, **state)
    return state


def chat_state(label):
    before = count('chat-state')
    command('chat-state')
    wait_for('chat-state', 30, before + 1)
    state = last_detail('chat-state')
    outcome.setdefault('chat_states', {})[label] = state
    return state


def settled_send(prompt):
    settled = count('completion:settled')
    type_and_send(prompt)
    wait_for('completion:settled', args.timeout, settled + 1)


def log_fields():
    text = logs()
    outcome['busy'] = 'Context is busy' in text
    outcome['spc_abort'] = len(SPC_ABORT_RE.findall(text))
    outcome['mem_shared'] = 'state cache disabled for this turn: mem-shared MTP draft' in text
    paths = []
    for m in ABORT_RE.finditer(text):
        if m.group(1).startswith('restored'):
            paths.append('restored')
        elif m.group(1).startswith('no usable'):
            paths.append(f'cleared ({m.group(2)})')
        else:
            paths.append('trim')
    outcome['abort_path'] = paths
    outcome['error_text'] = [detail_of(e) for e in app_events()
                             if e['name'] in ('completion:error', 'chat-send:error', 'error')]
    starts = [m.start() for m in re.finditer(r'\[CRASH_REPRO\]\S*,? \d+,? .completion:start', text)]
    outcome['refill_from'] = None
    if len(starts) >= 2:
        m = CHUNKS_RE.search(text, starts[-1])
        outcome['refill_from'] = int(m.group(1)) if m else None
    settled = [detail_of(e) for e in app_events() if e['name'] == 'completion:settled']
    outcome['draft_tokens'] = [d.get('draft_tokens') for d in settled if isinstance(d, dict)]


def release_ms():
    starts = [e['ms'] for e in app_events() if e['name'] == 'release:start']
    ends = [e['ms'] for e in app_events() if e['name'] == 'release:settled']
    if starts and ends and ends[-1] >= starts[-1]:
        return ends[-1] - starts[-1]
    return None


def follow_up_via_adapter(model):
    if not pid():
        return
    settled = count('completion:settled')
    if args.mode in ('background', 'release', 'switch'):
        # Fresh chat: otherwise "Reply with OK" re-prefills the 1,831-token prompt (~23 min at 1 thread).
        try:
            tap(bounds('reset-button'), 'new-chat')
            time.sleep(1.5)
        except RuntimeError as error:
            event('new-chat-failed', message=str(error))
    command('send', prompt='Reply with OK')
    if wait_for('completion:settled', 600, settled + 1):
        outcome['follow_up'] = last_detail('completion:settled')


def finish_recording(rec):
    adb('shell', 'pkill -INT screenrecord', check=False)
    rec.wait(timeout=10)
    adb('pull', '/sdcard/crash-stop.mp4', str(caps / f'{args.attempt}-send-drain.mp4'))
    return None


logcat = None
recorder = None
try:
    adb('shell', 'input keyevent KEYCODE_WAKEUP')
    adb('shell', 'wm dismiss-keyguard')
    adb('shell', f'am force-stop {PKG}')
    adb('shell', f'rm -f {FILES}/crash-command.json')
    apk = adb('shell', f'pm path {PKG}').split(':', 1)[1]
    outcome['apk_sha256'] = adb('shell', f'sha256sum {apk}').split()[0]
    if args.mode == 'fault':
        adb('shell', f'echo {args.fault_mode} > {FILES}/f1-fault.txt')
    adb('logcat', '-c')
    logcat = subprocess.Popen(['adb', '-s', args.serial, 'logcat', '-v', 'epoch'],
                              stdout=logfile.open('w'), stderr=subprocess.STDOUT)
    adb('shell', f'am start -n {PKG}/com.pocketpal.MainActivity')
    time.sleep(8)
    before = pid()
    event('start', pid=before, settings=vars(args))
    command('release')
    if not wait_for('manual-release:done'):
        raise RuntimeError('Initial release not observed')

    tool_mode = args.mode.startswith('stop-tool') or args.mode == 'dc1'
    model = args.model_b if tool_mode else args.model_a
    command('load', filename=model, threads=args.threads, n_ctx=4096, n_batch=args.batch,
            n_ubatch=args.batch, deterministic=args.mode in STOP_MODES + ('fault',) or args.dc1_plain,
            speculative=args.speculative, mmproj=args.mmproj)
    if not wait_for('loaded', 300):
        raise RuntimeError('Model load not observed')
    outcome['loaded'] = last_detail('loaded')

    if args.mode in ('wait-gate', 'wait-switch'):
        tap(bounds('reset-button'), 'new-chat')
        time.sleep(1.5)
        settled_send('Reply with OK')
        if args.mode == 'wait-gate':
            command('hold')
            wait_for('hold:granted', 30)
            type_and_send('first waiting message')
            time.sleep(1)
            adb('shell', 'input text second%swaiting%smessage')
            tap(bounds('send-button'), 'send-button')
            time.sleep(1)
            outcome['ui_waiting'] = dump_ui('wait-send-disabled')
            screencap('wait-send-disabled')
            adb('shell', 'input keyevent KEYCODE_BACK')
            time.sleep(0.5)
            long_press('ai-message', 'ai-row')
            time.sleep(1)
            outcome['ui_menu_ai'] = dump_ui('wait-menu-ai')
            screencap('wait-menu-disabled-ai')
            adb('shell', 'input tap 540 500')
            time.sleep(0.5)
            long_press('user-message', 'user-row')
            time.sleep(1)
            outcome['ui_menu_user'] = dump_ui('wait-menu-user')
            screencap('wait-menu-disabled-user')
            adb('shell', 'input tap 540 500')
            time.sleep(0.5)
            starts = count('completion:start')
            command('unhold')
            wait_for('completion:start', 60, starts + 1)
            time.sleep(0.5)
            outcome['ui_released'] = dump_ui('wait-released')
            screencap('wait-released')
            wait_for('completion:settled', args.timeout, count('completion:settled') + 1)
            time.sleep(3)
            outcome['completion_starts_after_unhold'] = count('completion:start') - starts
            chat_state('end')
        else:
            session_b = chat_state('b')['active']
            tap(bounds('reset-button'), 'new-chat')
            time.sleep(1.5)
            settled_send('Reply with OK')
            session_a = chat_state('a')['active']
            command('hold')
            wait_for('hold:granted', 30)
            type_and_send('message sent before the switch')
            time.sleep(1)
            target = 'new' if args.to == 'new' else session_b
            command('session', to=target)
            wait_for('session:done', 30)
            starts = count('completion:start')
            command('unhold')
            time.sleep(3)
            screencap('cancel-other-chat')
            outcome['completion_starts_after_unhold'] = count('completion:start') - starts
            chat_state('after-unhold')
            before_sess = count('session:done')
            command('session', to=session_a)
            wait_for('session:done', 30, before_sess + 1)
            time.sleep(1.5)
            outcome['ui_return'] = dump_ui('cancel-return')
            screencap('cancel-return')
            chat_state('back-in-a')
        log_fields()
        time.sleep(2)
        after = pid()
        crashed = bool(CRASH_RE.search(logs()))
        outcome.update(survived=bool(after) and after == before and not crashed, crashed=crashed)
        event('end', before=before, after=after, crashed=crashed)
        raise SystemExit(0)

    if args.mode == 'dc1':
        # --delay is seconds for every mode; dc1 passes it to the adapter, which
        # aborts that long after emitting the send (host polling is too coarse).
        command('dc1-flags', force_stop=args.force_stop, no_reapply=args.no_reapply)
        wait_for('dc1-flags', 30)
        settled = count('completion:settled') + count('completion:error')
        sends_done = count('chat-send:done')
        if args.dc1_plain:
            tap(bounds('reset-button'), 'new-chat')
            time.sleep(1.5)
            command('send', prompt=DC1_PROMPT)
        else:
            params = {'prompt': 'What is the code word? Use your tool.', 'sleepMs': args.sleep_ms}
            if not args.force_stop:
                params['abortAfterMs'] = int(args.delay * 1000)
            command('send-tool', **params)
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            if count('completion:settled') + count('completion:error') > settled or count('chat-send:done') > sends_done:
                break
            time.sleep(0.1)
        outcome['completion_started'] = count('completion:start') > 0
        time.sleep(2)
        text = logs()
        done = [detail_of(e) for e in app_events()
                if e['name'] in ('completion:settled', 'completion:error')]
        first = done[settled] if len(done) > settled else None
        outcome['reapply'] = '[dc1] reapply' in text
        outcome['forced'] = '[dc1] forced stop' in text
        outcome['abort_sent'] = count('abort:sent') > 0
        outcome['stopped'] = first
        if isinstance(first, dict):
            for key in ('interrupted', 'tokens_predicted', 'stopped_eos', 'stopped_limit'):
                outcome[key] = first.get(key)
        outcome['tool_started'] = count('tool:start') > 0
        command('dc1-flags', force_stop=False, no_reapply=False)
        wait_for('dc1-flags', 30, 2)
        after_first = count('completion:settled') + count('completion:error')
        follow_text = {'same': DC1_PROMPT, 'different': DC1_OTHER}.get(args.dc1_follow_up, 'Reply with OK')
        outcome['follow_up_text'] = args.dc1_follow_up
        command('send', prompt=follow_text)
        wait_settled_or_error(after_first + 1, args.timeout)
        outcome['follow_up'] = last_detail('completion:settled')
        if args.dc1_plain and pid():
            time.sleep(2)
            replays = count('replay:settled')
            command('replay')
            wait_for('replay:settled', args.timeout, replays + 1)
            outcome['replay'] = last_detail('replay:settled')
        log_fields()
        after = pid()
        crashed = bool(CRASH_RE.search(logs()))
        outcome.update(survived=bool(after) and after == before and not crashed, crashed=crashed)
        event('end', before=before, after=after, crashed=crashed)
        raise SystemExit(0)

    if args.mode == 'dc4':
        def ms_of(name, nth):
            found = [e['ms'] for e in app_events() if e['name'] == name]
            return found[nth] if len(found) > nth else None
        command('image-completion', image=args.image or 'test-image.jpg')
        wait_for('completion:start', 120)
        if args.stop_at == 'gen':
            wait_for('image-completion:first-token', args.timeout)
        time.sleep(args.delay)
        command('abort')
        wait_for('abort:sent', 30)
        wait_for('image-completion:settled', args.timeout)
        time.sleep(1)
        outcome['abort_ms'] = ms_of('abort:sent', 0)
        outcome['settled_ms'] = ms_of('image-completion:settled', 0)
        outcome['first_token_ms'] = ms_of('image-completion:first-token', 0)
        outcome['start_ms'] = ms_of('completion:start', 0)
        outcome['stopped'] = last_detail('completion:settled')
        outcome['image_settled'] = last_detail('image-completion:settled')
        outcome['chunks'] = [(float(m.group(1)), m.group(2)) for m in re.finditer(
            r'^\s*(\d+\.\d+).*processMedia:\d+ \[DEBUG\] (Evaluating chunk \d+[^\n]*|Cleaning up resources)',
            logs(), re.M)]
        command('image-completion', image=args.image or 'test-image.jpg')
        wait_for('image-completion:first-token', args.timeout, 2 if outcome['first_token_ms'] else 1)
        time.sleep(3)
        command('abort')
        wait_for('image-completion:settled', args.timeout, 2)
        time.sleep(1)
        outcome['next'] = last_detail('completion:settled')
        outcome['next_image_settled'] = last_detail('image-completion:settled')
        log_fields()
        after = pid()
        crashed = bool(CRASH_RE.search(logs()))
        outcome.update(survived=bool(after) and after == before and not crashed, crashed=crashed)
        event('end', before=before, after=after, crashed=crashed)
        raise SystemExit(0)

    if args.mode == 'fault':
        command('send', prompt=long_prompt(with_facts=True))
        wait_settled_or_error(1, args.timeout)
        time.sleep(1)
        adb('shell', f'rm -f {FILES}/f1-fault.txt')
        outcome['fault_lines'] = re.findall(r'\[f1-fault\][^\n]*', logs())
        screencap('fault-turn')
        tokens_before_follow_up = count('completion:first-token')
        type_and_send(FOLLOW_UP)
        wait_settled_or_error(2, args.timeout,
                              tokens_before_follow_up + 1 if args.follow_up_first_token else None)
        time.sleep(1)
        done = [detail_of(e) for e in app_events()
                if e['name'] in ('completion:settled', 'completion:error')]
        outcome['stopped'] = done[0] if done else None
        outcome['follow_up'] = done[1] if len(done) > 1 else None
        outcome['follow_up_streamed'] = count('completion:first-token') > tokens_before_follow_up
        screencap('follow-up')
        if not args.follow_up_first_token and pid():
            command('replay')
            wait_for('replay:settled', args.timeout)
            outcome['replay'] = last_detail('replay:settled')
        time.sleep(3)
        log_fields()
        after = pid()
        crashed = bool(CRASH_RE.search(logs()))
        outcome.update(survived=bool(after) and after == before and not crashed, crashed=crashed)
        event('end', before=before, after=after, crashed=crashed)
        raise SystemExit(0)

    if args.warm_turn:
        tap(bounds('reset-button'), 'new-chat')
        time.sleep(1.5)
        settled = count('completion:settled')
        command('send', prompt='Reply with OK')
        wait_for('completion:settled', args.timeout, settled + 1)
    if args.image_turn:
        settled = count('completion:settled')
        command('send', prompt=IMAGE_TURN, image=args.image)
        wait_for('completion:settled', args.timeout, settled + 1)

    if tool_mode:
        command('send-tool', prompt='What is the code word? Use your tool.', sleepMs=args.sleep_ms)
    elif args.mode in STOP_MODES:
        command('send', prompt=long_prompt(with_facts=True),
                image=None if args.image_turn else args.image)
    else:
        command('send', prompt=long_prompt(with_facts=False))

    if args.mode == 'stop-tool-exec':
        if not wait_for('tool:start', 600):
            raise RuntimeError('Tool never started; check tool support of the model')
    elif args.mode == 'stop-tool-followup':
        if not wait_for('tool:end', 600) or not wait_for('completion:start', 120, 2):
            raise RuntimeError('Follow-up turn never started')
    elif not wait_for('completion:start', 60, 2 if args.image_turn or args.warm_turn else 1):
        raise RuntimeError('Native completion start not observed')
    stop = None
    if args.mode in STOP_MODES:
        time.sleep(0.5)
        stop = bounds('stop-button')
        wait_stop_point()
    else:
        time.sleep(args.delay)
    screencap('mid-prefill')

    if args.mode == 'baseline':
        wait_for('completion:settled', args.timeout)
        outcome['completion'] = last_detail('completion:settled')
    elif args.mode == 'background':
        adb('shell', 'input keyevent KEYCODE_HOME')
        event('home')
        wait_for('release:settled', args.timeout)
        outcome['release_ms'] = release_ms()
        time.sleep(max(3, args.bg_hold))
        event('foreground', released_while_backgrounded=release_ms() is not None, pid=pid())
        adb('shell', f'am start -n {PKG}/com.pocketpal.MainActivity')
        # Let the app's own auto-reload finish before the adapter re-wraps the context.
        time.sleep(12)
        command('load', filename=model, threads=args.threads, n_ctx=4096, n_batch=args.batch,
                n_ubatch=args.batch)
        wait_for('loaded', 300, 2)
        follow_up_via_adapter(model)
    elif args.mode == 'release':
        command('release', manual=args.manual)
        time.sleep(0.3)
        screencap('unload-mid-stream')
        wait_for('release:settled', args.timeout)
        outcome['release_ms'] = release_ms()
        screencap('unload-after-drain')
        command('load', filename=model, threads=args.threads, n_ctx=4096, n_batch=args.batch,
                n_ubatch=args.batch)
        wait_for('loaded', 300, 2)
        follow_up_via_adapter(model)
    elif args.mode == 'switch':
        command('switch', filename=args.model_b)
        wait_for('switched', args.timeout)
        outcome['release_ms'] = release_ms()
        follow_up_via_adapter(args.model_b)
    else:
        stop = stop or bounds('stop-button')
        if args.capture:
            recorder = subprocess.Popen(['adb', '-s', args.serial, 'shell', 'screenrecord',
                                         '--time-limit', '60', '/sdcard/crash-stop.mp4'])
            time.sleep(1)
        starts_before_stop = count('completion:start')
        done_before_stop = 1 if args.image_turn or args.warm_turn else 0
        outcome['settled_before_stop'] = (
            count('completion:settled') + count('completion:error')) > done_before_stop
        tap(stop, 'stop-button')
        time.sleep(0.3)
        screencap('stop-tap')
        if args.mode in STOP_MODES:
            tokens_before_follow_up = count('completion:first-token')
            if args.mode == 'stop-retry':
                wait_settled_or_error(done_before_stop + 1, args.timeout)
                time.sleep(1)
                try:
                    long_press('ai-message', 'stopped-ai-row')
                except RuntimeError:
                    tree = ET.fromstring(ui_xml())
                    node = [n for n in tree.iter('node') if 'TTFT' in (n.get('text') or '')][-1]
                    x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
                    adb('shell', f'input swipe {(x1 + x2) // 2} {(y1 + y2) // 2} {(x1 + x2) // 2} {(y1 + y2) // 2} 900')
                    event('long-press', target='stopped-ai-row-footer')
                time.sleep(1)
                tap_text('Regenerate', 'regenerate')
            else:
                wait_settled_or_error(done_before_stop + 1, 120)
                tokens_before_follow_up = count('completion:first-token')
                type_and_send(FOLLOW_UP)
            wait_settled_or_error(
                done_before_stop + 2, args.timeout,
                tokens_before_follow_up + 1
                if args.mode == 'mtp-stop' and args.follow_up_first_token else None)
            time.sleep(1)
            done = [detail_of(e) for e in app_events()
                    if e['name'] in ('completion:settled', 'completion:error')]
            outcome['stopped'] = done[done_before_stop] if len(done) > done_before_stop else None
            outcome['follow_up'] = done[-1] if len(done) > done_before_stop + 1 else None
            outcome['follow_up_streamed'] = count('completion:first-token') > tokens_before_follow_up
            if args.mode == 'mtp-stop':
                chat_state('after-follow-up')
                recorder = finish_recording(recorder) if recorder else None
            screencap('follow-up')
            if args.mode == 'mtp-stop':
                raise StopIteration
            if recorder:
                recorder = finish_recording(recorder)
            replays = count('replay:settled')
            command('replay')
            wait_for('replay:settled', args.timeout, replays + 1)
            outcome['replay'] = last_detail('replay:settled')
        else:
            wait_for('chat-send:done', args.timeout)
            time.sleep(args.sleep_ms / 1000 + 5)
            outcome['completion_starts_after_stop'] = count('completion:start') - starts_before_stop
            follow_up_via_adapter(model)

    time.sleep(5)
    log_fields()
    after = pid()
    crashed = bool(CRASH_RE.search(logs()))
    outcome.update(survived=bool(after) and after == before and not crashed, crashed=crashed)
    event('end', before=before, after=after, crashed=crashed)
except StopIteration:
    time.sleep(5)
    log_fields()
    after = pid()
    crashed = bool(CRASH_RE.search(logs()))
    outcome.update(survived=bool(after) and after == before and not crashed, crashed=crashed)
    event('end', before=before, after=after, crashed=crashed)
except SystemExit:
    pass
except Exception as error:
    outcome['error'] = str(error)
    event('error', message=str(error))
    raise
finally:
    if recorder:
        recorder.terminate()
    if logcat:
        logcat.terminate()
    outcome['events'] = events
    out.write_text(json.dumps(outcome, indent=2))
    summary = root / 'result.json'
    rows = json.loads(summary.read_text()) if summary.exists() else []
    rows.append({k: v for k, v in outcome.items() if k != 'events'})
    summary.write_text(json.dumps(rows, indent=2))
