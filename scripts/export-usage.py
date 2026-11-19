"""Export aggregate Apache request usage to the existing node textfile collector."""
import argparse
import collections
import datetime as dt
import gzip
import os
from pathlib import Path
import re
import tempfile
import time

WINDOWS = {'1h': 3600, '24h': 86400, '7d': 604800}
EVENTS = ('page', 'exercise', 'check', 'upload', 'other')
LINE = re.compile(r'^\S+ \S+ \S+ \[([^]]+)\] "(\S+) (\S+) [^"]+" (\d{3}) (\d+|-) ')


def classify(method, path):
    path = path.split('?', 1)[0]
    return {('GET', '/'): 'page', ('POST', '/api/trainer/task'): 'exercise',
            ('POST', '/api/trainer/check'): 'check',
            ('POST', '/api/transcribe'): 'upload'}.get((method, path), 'other')


def collect(paths, now):
    counts = collections.Counter()
    oldest = None
    newest = 0
    malformed = 0
    for path in paths:
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8', errors='replace') as stream:
            for line in stream:
                match = LINE.match(line)
                if not match:
                    malformed += 1
                    continue
                stamp, method, target, status, size = match.groups()
                try:
                    timestamp = dt.datetime.strptime(stamp, '%d/%b/%Y:%H:%M:%S %z').timestamp()
                except ValueError:
                    malformed += 1
                    continue
                if timestamp > now:
                    continue
                oldest = timestamp if oldest is None else min(oldest, timestamp)
                newest = max(newest, timestamp)
                event = classify(method, target)
                category = status[0] + 'xx'
                for window, seconds in WINDOWS.items():
                    if 0 <= now - timestamp < seconds:
                        counts[window, event, category] += 1
    lines = ['# HELP natocheck_usage_requests Requests in a rolling window of retained Apache logs.',
             '# TYPE natocheck_usage_requests gauge']
    for window in WINDOWS:
        for event in EVENTS:
            for category in ('1xx', '2xx', '3xx', '4xx', '5xx'):
                lines.append(f'natocheck_usage_requests{{window="{window}",event="{event}",status="{category}"}} {counts[window,event,category]}')
    for name, value in [('export_timestamp_seconds', now), ('newest_request_timestamp_seconds', newest),
                        ('oldest_retained_timestamp_seconds', oldest or 0),
                        ('log_files', len(paths)), ('malformed_lines', malformed)]:
        lines.extend([f'# TYPE natocheck_usage_{name} gauge', f'natocheck_usage_{name} {value}'])
    return '\n'.join(lines) + '\n'


def write_atomic(destination, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent,
                                         prefix='.natocheck-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o644)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log-dir', type=Path, default=Path('/var/log/apache2'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    paths = sorted(path for path in args.log_dir.glob('natocheck-access.log*')
                   if re.fullmatch(r'natocheck-access\.log(?:\.\d+(?:\.gz)?)?', path.name))
    if not paths:
        parser.error('No NatoCheck Apache access logs found; existing metrics remain unchanged')
    content = collect(paths, time.time())
    if args.output:
        write_atomic(args.output, content)
    else:
        print(content, end='')


if __name__ == '__main__':
    main()
