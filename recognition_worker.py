"""Reuse one isolated recognition process while retaining a hard job timeout."""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import threading
import time

from recording import UncertainSpeechError


class RecognitionWorker:
    def __init__(self, timeout=300):
        self.timeout = timeout
        self.process = None
        self.lock = threading.Lock()

    def start(self):
        if self.process is not None and self.process.poll() is None:
            return
        self.close()
        self.process = subprocess.Popen(
            [sys.executable, '-u', str(Path(__file__).with_name('recording.py')), '--worker'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, start_new_session=True,
            env={**os.environ, 'OMP_NUM_THREADS': os.environ.get('OMP_NUM_THREADS', '2')},
        )

    def close(self):
        if self.process is None:
            return
        if self.process.poll() is None:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()
        self.process = None

    def transcribe(self, source, language, target):
        with self.lock:
            started = time.monotonic()
            try:
                self.start()
                self.process.stdin.write(json.dumps({
                    'source': str(source), 'language': language, 'output': str(target),
                }) + '\n')
                self.process.stdin.flush()
                if not select.select([self.process.stdout], [], [], self.timeout)[0]:
                    raise TimeoutError('Speech recognition timed out; please try again')
                line = self.process.stdout.readline()
                if not line:
                    raise RuntimeError('Speech recognition stopped; please try again')
                result = json.loads(line)
            except (OSError, ValueError, RuntimeError, TimeoutError):
                self.close()
                raise
            if result.get('review_text'):
                raise UncertainSpeechError(result['review_text'])
            if not result.get('ok'):
                raise ValueError(result.get('error', 'Speech recognition failed'))
            return round(time.monotonic() - started, 2)
