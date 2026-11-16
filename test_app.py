"""Test HTTP routes and transcription isolation without accessing a microphone."""
import http.client
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from app import APP_VERSION, Application, application_version, handler


class ApplicationTests(unittest.TestCase):
    def test_version_uses_git_identity_and_handles_missing_git(self):
        with patch('app.subprocess.check_output', return_value='v1.2-3-gabcdef0\n'):
            self.assertEqual(application_version(), 'v1.2-3-gabcdef0')
        with patch('app.subprocess.check_output', side_effect=FileNotFoundError):
            self.assertEqual(application_version(), 'unknown')

    def test_recordings_require_supported_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Application(Path(folder))
            for data, mime, language in [(b'wrong', 'audio/webm', 'en'),
                    (b'OggSdata', 'audio/ogg', 'ja'), (b'OggSdata', 'text/plain', 'en')]:
                with self.assertRaises(ValueError):
                    app.upload(data, mime, language)
            self.assertTrue(app.worker.acquire(blocking=False))
            app.worker.release()

    def test_success_is_private_and_temporary_files_are_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Application(Path(folder))
            source = Path(folder)/'recording.webm'
            source.write_bytes(b'example')
            source.with_suffix('.txt').write_text('Alfa Bravo')
            source.with_suffix('.wav').write_bytes(b'example')
            app.worker.acquire()
            with patch.object(app.recognizer, 'transcribe', return_value=1.25) as runner:
                app.transcribe('one', source, 'en')
            runner.assert_called_once_with(source, 'en', source.with_suffix('.txt'))
            self.assertEqual(app.status('one')['elapsed_seconds'], 1.25)
            self.assertEqual(app.status('one')['text'], 'Alfa Bravo')
            with self.assertRaises(ValueError):
                app.status('unknown')
            self.assertFalse(list(Path(folder).iterdir()))
            self.assertTrue(app.worker.acquire(blocking=False))
            app.worker.release()

    def test_failed_recognition_has_no_transcript_and_releases_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Application(Path(folder))
            source = Path(folder)/'recording.webm'
            source.write_bytes(b'example')
            app.worker.acquire()
            with patch.object(app.recognizer, 'transcribe', side_effect=TimeoutError('Recognition timed out')):
                app.transcribe('failed', source, 'en')
            self.assertEqual(app.status('failed')['state'], 'error')
            self.assertEqual(app.status('failed')['text'], '')
            self.assertFalse(source.exists())
            self.assertTrue(app.worker.acquire(blocking=False))
            app.worker.release()

    def test_busy_recognition_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Application(Path(folder))
            app.worker.acquire()
            with self.assertRaises(ValueError):
                app.upload(b'OggSdata', 'audio/ogg', 'en')
            app.worker.release()
            self.assertFalse(list(Path(folder).iterdir()))

    def test_http_exercise_flow_and_origin_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Application(Path(folder))
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler(app, set()))
            port = server.server_address[1]
            server.RequestHandlerClass = handler(app, {f'127.0.0.1:{port}'})
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def request(method, path, body=None, **headers):
                conn = http.client.HTTPConnection('127.0.0.1', port)
                data = json.dumps(body) if body is not None else None
                conn.request(method, path, data, {'Content-Type': 'application/json', **headers})
                response = conn.getresponse()
                result = response.status, response.read(), response.getheader('Content-Type')
                conn.close()
                return result
            try:
                status, body, mime = request('GET', '/')
                self.assertEqual(status, 200)
                self.assertIn(b'NatoCheck', body)
                self.assertIn(('Version ' + APP_VERSION).encode(), body)
                self.assertNotIn(b'{{APP_VERSION}}', body)
                self.assertLess(body.index(b'id="answer"'), body.index(b'class="workspace"'))
                self.assertIn('text/html', mime)
                status, body, _ = request('POST', '/api/trainer/task', {'mode': 'word'})
                self.assertEqual(status, 200)
                task = json.loads(body)
                from trainer import ALPHABET
                answer = ' '.join(ALPHABET[c] for c in task['prompt'])
                status, body, _ = request('POST', '/api/trainer/check', {'task_id': task['id'], 'text': answer})
                self.assertEqual(status, 200)
                self.assertTrue(json.loads(body)['passed'])
                self.assertEqual(request('POST', '/api/trainer/task', {'mode': 'letter'}, Origin='https://untrusted.invalid')[0], 403)
                self.assertEqual(request('POST', '/api/trainer/task', {'mode': []})[0], 400)
                self.assertEqual(request('POST', '/api/trainer/check', {'task_id': task['id'], 'text': ''})[0], 400)
                self.assertEqual(request('GET', '/api/transcriptions/' + 'a'*32)[0], 404)
                self.assertEqual(request('GET', '/api/status')[0], 404)
                self.assertEqual(request('GET', '/../../app.py')[0], 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
