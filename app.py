"""Serve NatoCheck and local Whisper recognition without a Codex connection."""
import argparse
import collections
from html import escape
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from trainer import ALPHABET, Trainer
from recognition_worker import RecognitionWorker
from recording import MAX_UPLOAD_BYTES

BASE = Path(__file__).resolve().parent


def application_version():
    """Use the repository release identity as the application version."""
    try:
        return subprocess.check_output(
            ['git', '-c', f'safe.directory={BASE}', 'describe', '--tags', '--always', '--dirty'], cwd=BASE,
            text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return 'unknown'


APP_VERSION = application_version()
MAX_UPLOAD = MAX_UPLOAD_BYTES
FORMATS = {'audio/webm': ('.webm', b'\x1aE\xdf\xa3'),
           'audio/ogg': ('.ogg', b'OggS'), 'audio/mp4': ('.m4a', b'ftyp')}
LOG = logging.getLogger('natocheck')


class Application:
    def __init__(self, output):
        self.trainer = Trainer()
        self.recognizer = RecognitionWorker()
        self.output = output
        self.jobs = collections.OrderedDict()
        self.lock = threading.Lock()
        self.worker = threading.BoundedSemaphore(1)

    def status(self, job_id):
        with self.lock:
            if job_id not in self.jobs:
                raise ValueError('Recording not found; please record again')
            return dict(self.jobs[job_id])

    def upload(self, data, mime, language):
        if mime not in FORMATS or language != 'en':
            raise ValueError('Unsupported recording format or language')
        if not 0 < len(data) <= MAX_UPLOAD:
            raise ValueError('Recording must be between 1 byte and 2 MB')
        suffix, signature = FORMATS[mime]
        if (data[4:8] if mime == 'audio/mp4' else data[:4]) != signature:
            raise ValueError('Recording content does not match its audio format')
        if not self.worker.acquire(blocking=False):
            raise ValueError('Speech recognition is busy; please try again shortly')
        job_id = uuid.uuid4().hex
        source = self.output / (job_id + suffix)
        try:
            self.output.mkdir(parents=True, exist_ok=True, mode=0o700)
            source.write_bytes(data)
            source.chmod(0o600)
            with self.lock:
                self.jobs[job_id] = dict(id=job_id, state='busy', text='', error='')
                while len(self.jobs) > 100:
                    self.jobs.popitem(last=False)
            threading.Thread(target=self.transcribe, args=(job_id, source, language), daemon=True).start()
        except Exception:
            source.unlink(missing_ok=True)
            self.worker.release()
            raise
        return dict(id=job_id, state='busy', text='', error='')

    def transcribe(self, job_id, source, language):
        target = source.with_suffix('.txt')
        try:
            elapsed = self.recognizer.transcribe(source, language, target)
            LOG.info('recognition_complete job=%s elapsed_seconds=%.2f', job_id, elapsed)
            text = target.read_text(encoding='utf-8').strip()
            if not text:
                raise ValueError('No reliable speech recognized')
            state = dict(id=job_id, state='done', text=text, error='', elapsed_seconds=elapsed)
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
            state = dict(id=job_id, state='error', text='', error=str(error))
        finally:
            for path in (source, target, source.with_suffix('.wav')):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    LOG.exception('Could not remove temporary recording %s', path.name)
            self.worker.release()
        with self.lock:
            self.jobs[job_id] = state


def handler(app, hosts):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def send(self, code, value, mime='application/json'):
            if isinstance(value, bytes):
                data = value
            elif isinstance(value, str):
                data = value.encode('utf-8')
            else:
                data = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', mime + ('; charset=utf-8' if mime != 'image/webp' else ''))
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'same-origin')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'")
            self.end_headers()
            self.wfile.write(data)

        def allowed(self):
            host = self.headers.get('Host')
            origin = self.headers.get('Origin')
            origins = {'https://' + h for h in hosts}
            origins.update('http://' + h for h in hosts if h.startswith(('localhost:', '127.0.0.1:')))
            return host in hosts and (origin is None or origin in origins)

        def do_GET(self):
            if not self.allowed():
                return self.send(403, {'error': 'Host or origin not allowed'})
            path = urlparse(self.path).path
            files = {'/': ('trainer.html', 'text/html'), '/trainer.js': ('trainer.js', 'text/javascript'),
                     '/trainer.css': ('trainer.css', 'text/css'),
                     '/interface.js': ('interface.js', 'text/javascript'),
                     '/assets/eventhacker-logo-white.webp': ('assets/eventhacker-logo-white.webp', 'image/webp')}
            if path in files:
                filename, mime = files[path]
                content = (BASE / filename).read_bytes()
                if filename == 'trainer.html':
                    content = content.replace(b'{{APP_VERSION}}', escape(APP_VERSION).encode('utf-8'))
                return self.send(200, content, mime)
            if path == '/api/trainer/alphabet':
                return self.send(200, ALPHABET)
            if re.fullmatch(r'/api/transcriptions/[a-f0-9]{32}', path):
                try:
                    return self.send(200, app.status(path.rsplit('/', 1)[1]))
                except ValueError as error:
                    return self.send(404, {'error': str(error)})
            return self.send(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.allowed():
                return self.send(403, {'error': 'Host or origin not allowed'})
            try:
                path = urlparse(self.path).path
                mime = self.headers.get('Content-Type', '').split(';')[0]
                limit = MAX_UPLOAD if path == '/api/transcribe' else 16000
                if self.headers.get('Transfer-Encoding'):
                    return self.send(400, {'error': 'Transfer encoding is not supported'})
                length = int(self.headers.get('Content-Length', '0'))
                if length > limit:
                    self.close_connection = True
                    return self.send(413, {'error': 'Recording upload limit is 2 MB' if path == '/api/transcribe' else 'Request too large'})
                if not 0 < length <= limit:
                    raise ValueError('Invalid request size')
                data = self.rfile.read(length)
                if len(data) != length:
                    raise ValueError('Incomplete request')
                if path == '/api/transcribe':
                    return self.send(202, app.upload(data, mime, 'en'))
                if mime != 'application/json':
                    raise ValueError('Expected JSON')
                value = json.loads(data)
                if not isinstance(value, dict):
                    raise ValueError('Expected an object')
                if path == '/api/trainer/task':
                    return self.send(200, app.trainer.new(value.get('mode')))
                if path == '/api/trainer/check':
                    return self.send(200, app.trainer.check(value.get('task_id'), value.get('text')))
                return self.send(404, {'error': 'Not found'})
            except (ValueError, UnicodeDecodeError) as error:
                return self.send(400, {'error': str(error)})
            except OSError:
                LOG.exception('Recording request failed')
                return self.send(500, {'error': 'Recording could not be processed'})

        def log_message(self, message, *args):
            LOG.info(message, *args)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    output = Path(os.environ.get('NATOCHECK_DATA_DIR', str(BASE / 'out.user.local'))).expanduser().resolve()
    hosts = {f'127.0.0.1:{args.port}', f'localhost:{args.port}'}
    hosts.update(filter(None, os.environ.get('NATOCHECK_ALLOWED_HOSTS', '').split(',')))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
    app = Application(output)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(app, hosts))
    app.recognizer.start()
    print(f'NatoCheck: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.recognizer.close()


if __name__ == '__main__':
    main()
