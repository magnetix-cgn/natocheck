"""Check persistent process reuse, timeout recovery and model caching."""
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from recognition_worker import RecognitionWorker
from recording import UncertainSpeechError, load_model

FIXTURE = '''
import json, pathlib, sys, time
for line in sys.stdin:
    job = json.loads(line)
    if job['language'] == 'timeout':
        time.sleep(10)
    if job['language'] == 'crash':
        sys.exit(1)
    if job['language'] == 'review':
        print(json.dumps({'ok': False, 'review_text': 'Alfa Beta'}), flush=True)
        continue
    pathlib.Path(job['output']).write_text('Alfa Bravo')
    print(json.dumps({'ok': True}), flush=True)
'''


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.real_popen = subprocess.Popen
        self.worker = RecognitionWorker(timeout=2)
        self.folder = tempfile.TemporaryDirectory()
        self.source = Path(self.folder.name) / 'input.webm'
        self.target = Path(self.folder.name) / 'output.txt'
        self.patcher = patch('recognition_worker.subprocess.Popen', side_effect=self.spawn)
        self.popen = self.patcher.start()

    def spawn(self, command, **kwargs):
        return self.real_popen([sys.executable, '-u', '-c', FIXTURE], **kwargs)

    def tearDown(self):
        self.worker.close()
        self.patcher.stop()
        self.folder.cleanup()

    def test_reuses_process_across_jobs(self):
        self.worker.transcribe(self.source, 'en', self.target)
        process = self.worker.process
        self.worker.transcribe(self.source, 'de', self.target)
        self.assertIs(self.worker.process, process)
        self.assertEqual(self.popen.call_count, 1)
        self.assertEqual(self.target.read_text(), 'Alfa Bravo')

    def test_timeout_kills_process_and_next_job_restarts(self):
        self.worker.timeout = 0.2
        with self.assertRaises(TimeoutError):
            self.worker.transcribe(self.source, 'timeout', self.target)
        self.assertIsNone(self.worker.process)
        self.worker.timeout = 2
        self.worker.transcribe(self.source, 'en', self.target)
        self.assertEqual(self.popen.call_count, 2)

    def test_crash_can_recover(self):
        with self.assertRaises(RuntimeError):
            self.worker.transcribe(self.source, 'crash', self.target)
        self.worker.transcribe(self.source, 'en', self.target)
        self.assertEqual(self.popen.call_count, 2)

    def test_review_transcript_crosses_worker_boundary_without_restart(self):
        with self.assertRaises(UncertainSpeechError) as raised:
            self.worker.transcribe(self.source, 'review', self.target)
        self.assertEqual(raised.exception.text, 'Alfa Beta')
        process = self.worker.process
        self.worker.transcribe(self.source, 'en', self.target)
        self.assertIs(self.worker.process, process)

    def test_model_is_loaded_once(self):
        load_model.cache_clear()
        loader = Mock(return_value=object())
        try:
            with patch.dict(sys.modules, {'whisper': types.SimpleNamespace(load_model=loader)}):
                self.assertIs(load_model('/local/base.pt'), load_model('/local/base.pt'))
                loader.assert_called_once_with('/local/base.pt', device='cpu')
        finally:
            load_model.cache_clear()


if __name__ == '__main__':
    unittest.main()
