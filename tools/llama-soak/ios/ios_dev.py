"""iOS device layer for soak.Soak (devicectl instead of adb/logcat).

Commands go to the app's Documents/crash-command.json; the adapter mirrors every
[CRASH_REPRO] line into Documents/crash-repro.log in the logcat line shape, and a
puller thread copies it to the seed's log file, so Soak.pump/EVENT_RE are unchanged.
Both need the iOS adapter edits described in README.md ("iOS").

Device: $IOS_UDID (xcrun devicectl list devices); bundle: $IOS_BUNDLE (default ai.pocketpal).
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import soak  # noqa: E402

UDID = os.environ.get('IOS_UDID', '')
BUNDLE = os.environ.get('IOS_BUNDLE', 'ai.pocketpal')
EXE = 'PocketPal.app/PocketPal'
LOG = 'Documents/crash-repro.log'


def dctl(*args, timeout=90, check=True, tries=4):
    if not UDID:
        raise RuntimeError('set IOS_UDID (xcrun devicectl list devices)')
    for attempt in range(tries):
        r = subprocess.run(['xcrun', 'devicectl', *args], capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0 or 'interrupted' not in (r.stderr + r.stdout):
            break
        time.sleep(2 * (attempt + 1))  # transient CoreDevice tunnel drop
    if check and r.returncode != 0:
        raise RuntimeError(f'devicectl {args[:3]} failed: {(r.stderr or r.stdout)[-400:]}')
    return r


def app_args(*rest):
    return ['--device', UDID, '--domain-type', 'appDataContainer', '--domain-identifier', BUNDLE, *rest]


def push(local, remote):
    dctl('device', 'copy', 'to', *app_args('--source', str(local), '--destination', remote), '-q')


def pull(remote, local):
    r = dctl('device', 'copy', 'from', *app_args('--source', remote, '--destination', str(local)), '-q',
             check=False)
    return r.returncode == 0


def pids():
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        out = f.name
    try:
        dctl('device', 'info', 'processes', '--device', UDID, '-q', '-j', out, timeout=60)
        data = json.loads(pathlib.Path(out).read_text())
    finally:
        os.unlink(out)
    return [str(p['processIdentifier']) for p in data['result']['runningProcesses']
            if p.get('executable', '').endswith(EXE)]


def launch(bundle, terminate=False):
    args = ['device', 'process', 'launch', '--device', UDID, '-q']
    if terminate:
        args.append('--terminate-existing')
    dctl(*args, bundle, timeout=120)


def crash_logs():
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        out = f.name
    try:
        r = dctl('device', 'info', 'files', '--device', UDID, '--domain-type', 'systemCrashLogs', '-q', '-j', out,
                 check=False, timeout=60)
        if r.returncode != 0:
            return []
        data = json.loads(pathlib.Path(out).read_text())
    finally:
        os.unlink(out)
    files = data.get('result', {}).get('files', [])
    return sorted(f.get('name') or f.get('relativePath', '') for f in files
                  if 'PocketPal' in (f.get('name') or f.get('relativePath', '')))


class LogPuller(threading.Thread):
    """Copies the device log every ~1 s; the seed's log file holds the bytes after `start`."""

    def __init__(self, dest, start):
        super().__init__(daemon=True)
        self.dest = pathlib.Path(dest)
        self.start_at = start
        self.stop_flag = threading.Event()
        self.tmp = self.dest.with_suffix('.pull')

    def once(self):
        if pull(LOG, self.tmp):
            data = self.tmp.read_bytes()[self.start_at:]
            part = self.dest.with_suffix('.part')
            # Only ever grow the file: the reader keeps a byte offset into it.
            if not self.dest.exists() or len(data) >= self.dest.stat().st_size:
                part.write_bytes(data)
                os.replace(part, self.dest)

    def run(self):
        while not self.stop_flag.is_set():
            try:
                self.once()
            except Exception:  # noqa: BLE001 - a missed pull is retried
                pass
            self.stop_flag.wait(0.7)

    def stop(self):
        self.stop_flag.set()
        self.join(timeout=30)
        try:
            self.once()
        except Exception:  # noqa: BLE001
            pass
        self.tmp.unlink(missing_ok=True)


class IOSMixin:
    """Overrides Soak's adb-specific pieces."""
    _pid_cache = (0.0, None)

    def adb(self, *cmd, check=True, timeout=120):
        s = ' '.join(cmd)
        if 'KEYCODE_HOME' in s:
            launch('com.apple.Preferences')
            return ''
        if 'am start' in s:
            launch(BUNDLE)
            return ''
        raise RuntimeError(f'adb call not ported to iOS: {s}')

    def pid(self):
        now = time.monotonic()
        t, cached = self._pid_cache
        if cached is not None and now - t < 2.5:
            return cached
        try:
            p = pids()
        except Exception:  # noqa: BLE001 - devicectl hiccup: report the last known pid
            return cached or ''
        value = p[0] if len(p) == 1 else (' '.join(p) if p else '')
        self._pid_cache = (now, value)
        return value

    def command(self, action, **params):
        self.cmd_n += 1
        body = {'id': f'{self.a.seed}-{self.cmd_n}-{time.time_ns()}', 'action': action, **params}
        local = self.dir / f'.cmd-{self.a.serial}.json'
        local.write_text(json.dumps(body))
        push(local, 'Documents/crash-command.json')

    def diagnose(self, k):
        out = {'pid': self.pid(), 'crash_logs': crash_logs()[-5:]}
        (self.dir / f'seed-{self.a.seed}-hang-step{k}.txt').write_text(json.dumps(out, indent=1))
        return out

    def ios_setup(self):
        """Fresh process, empty command file, puller on the new bytes. Returns the setup head."""
        self.crash0 = crash_logs()
        empty = self.dir / '.empty.json'
        empty.write_text('{"id": "reset", "action": "status"}')
        # Reset the command file before launch: a fresh process runs whatever it finds there.
        push(empty, 'Documents/crash-command.json')
        # rnllama's LOG_INFO/LOG_WARNING go to stdout on iOS: launch attached to the console
        # and scan that stream too (Soak.scan_line: checkpoint restore/clear, aborted decodes).
        self.stdout_path = self.log_path.with_name(self.log_path.name.replace('-logcat.txt', '-stdout.txt'))
        self.stdout_off = 0
        self.console = subprocess.Popen(
            ['xcrun', 'devicectl', 'device', 'process', 'launch', '--console', '--terminate-existing',
             '--device', UDID, BUNDLE],
            stdout=self.stdout_path.open('w'), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        time.sleep(6)
        if self.console.poll() is not None:
            launch(BUNDLE, terminate=True)
            time.sleep(4)
        # Truncate the device log so each seed pulls only its own lines.
        blank = self.dir / '.blank.log'
        blank.write_text('')
        push(blank, LOG)
        self.log_path.write_text('')
        self.puller = LogPuller(self.log_path, 0)
        self.puller.start()
        time.sleep(4)
        self._pid_cache = (0.0, None)
        self.pid0 = self.pid()
        if not self.pid0 or ' ' in self.pid0:
            raise RuntimeError(f'app not running after launch: pid={self.pid0!r}')
        return {'pid': self.pid0, 'udid': UDID, 'build': os.environ.get('LLAMA_SOAK_BUILD', '')}

    def pump(self):
        super().pump()
        path = getattr(self, 'stdout_path', None)
        if not path or not path.exists():
            return
        with path.open('r', errors='replace') as f:
            f.seek(self.stdout_off)
            chunk = f.read()
        cut = chunk.rfind('\n') + 1
        self.stdout_off += len(chunk[:cut].encode('utf-8', errors='replace'))
        for line in chunk[:cut].splitlines():
            self.scan_line(line)

    def ios_teardown(self):
        if getattr(self, 'puller', None):
            self.puller.stop()
        if getattr(self, 'console', None) and self.console.poll() is None:
            self.console.terminate()
            try:
                self.console.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.console.kill()
        new_all = [c for c in crash_logs() if c not in getattr(self, 'crash0', [])]
        # cpu_resource / diskwrites reports are resource diagnostics ("Action taken: none"), not crashes.
        diag = [c for c in new_all if '.cpu_resource' in c or '.diskwrites' in c]
        if diag:
            self.findings.append({'kind': 'resource-diagnostic', 'seed': self.a.seed, 'files': diag})
        new = [c for c in new_all if c not in diag]
        if new:
            self.findings.append({'kind': 'crash-log', 'seed': self.a.seed, 'files': new})
            print('FINDING crash-log', new, flush=True)
        subprocess.run(['gzip', '-kf', str(self.log_path)], check=False)
        return new


class IOSSoak(IOSMixin, soak.Soak):
    def run(self):
        """soak.Soak.run with the adb setup replaced."""
        a = self.a
        started = time.time()
        rows = []
        ok = True
        out = self.rows_path.open('w')
        try:
            self.step_flags = {}
            head = {'seed': a.seed, 'step': -1, 'action': 'setup', **self.ios_setup(),
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
                except (subprocess.TimeoutExpired, RuntimeError) as error:
                    row, ok = {'seed': a.seed, 'step': k, 'harness_error': str(error)}, False
                rows.append(row)
                out.write(json.dumps(row) + '\n')
                out.flush()
                print(json.dumps({'step': k, 'action': row.get('action'), 'idle': row.get('idle'),
                                  'oracle': (row.get('oracle') or {}).get('result'),
                                  'n': len(row.get('completions', []))}), flush=True)
                if not ok:
                    break
        except Exception as error:  # noqa: BLE001
            self.findings.append({'kind': 'harness', 'seed': a.seed, 'error': repr(error)})
            print('HARNESS', repr(error), flush=True)
            ok = False
        finally:
            time.sleep(2)
            self.ios_teardown()
            self.pump()
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
