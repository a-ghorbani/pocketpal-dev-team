"""stoplat.py <seed-N-logcat.txt.gz...>: per Stop with a completion in flight: latency (stop:pressed ->
completion:settled), phase (prefill = no first token yet, gen = after first token), tokens_evaluated."""
import gzip
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import soak  # noqa: E402

for path in sys.argv[1:]:
    inflight = first = pending = None
    out = []
    for line in gzip.open(path, 'rt', errors='replace'):
        m = soak.EVENT_RE.search(line)
        if not m:
            continue
        name, ms = m.group(2), int(m.group(1))
        if name == 'completion:start':
            inflight, first = ms, None
        elif name == 'completion:first-token' and inflight:
            first = ms
        elif name == 'stop:pressed' and inflight:
            pending = (ms, 'gen' if first else 'prefill')
        elif name in ('completion:settled', 'completion:error') and inflight:
            if pending:
                d = soak.decode_detail(m.group(3) or '') or {}
                out.append((ms - pending[0], pending[1], d.get('tokens_evaluated') if isinstance(d, dict) else None,
                            d.get('prompt_n') if isinstance(d, dict) else None))
            inflight = pending = None
    pre = sorted(x[0] for x in out if x[1] == 'prefill'); gen = sorted(x[0] for x in out if x[1] == 'gen')
    print(path.split('soak/')[-1], 'prefill', pre, 'gen', gen)
