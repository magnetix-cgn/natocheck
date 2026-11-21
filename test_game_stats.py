"""Verify durable, deduplicated aggregate counts and Berlin day boundaries."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from app import Application, handler
from game_stats import GameStats
from trainer import ALPHABET, Trainer


class GameStatsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'game-stats.json'

    def tearDown(self):
        self.folder.cleanup()

    def test_persistence_and_berlin_midnight(self):
        before = datetime(2026, 11, 21, 22, 59, tzinfo=timezone.utc)
        after = datetime(2026, 11, 21, 23, 0, tzinfo=timezone.utc)
        stats = GameStats(self.path)
        initial = stats.snapshot(before)
        stats.record(True, before)
        self.assertEqual(stats.snapshot(before)['today_completed'], 1)
        self.assertEqual(stats.snapshot(after)['today_completed'], 0)
        stats.record(False, after)
        restored = GameStats(self.path).snapshot(after)
        self.assertEqual((restored['completed'], restored['perfect'], restored['today_completed']), (2, 1, 1))
        self.assertEqual(restored['since'], initial['since'])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_only_first_valid_challenge_evaluation_counts(self):
        stats = GameStats(self.path)
        trainer = Trainer(stats)
        for mode in ['letter', 'word', 'sequence']:
            task = trainer.new(mode)
            trainer.check(task['id'], ' '.join(ALPHABET[c] for c in task['prompt']))
        task = trainer.new('challenge')
        with self.assertRaises(ValueError):
            trainer.check(task['id'], '')
        self.assertEqual(stats.snapshot()['completed'], 0)
        trainer.check(task['id'], 'Alfa')
        trainer.check(task['id'], ' '.join(ALPHABET[c] for c in task['prompt']))
        self.assertEqual((stats.snapshot()['completed'], stats.snapshot()['perfect']), (1, 0))
        self.assertNotIn('counted', task)

    def test_concurrent_rechecks_count_once(self):
        stats = GameStats(self.path)
        trainer = Trainer(stats)
        task = trainer.new('challenge')
        answer = ' '.join(ALPHABET[c] for c in task['prompt'])
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: trainer.check(task['id'], answer), range(24)))
        self.assertTrue(all(result['passed'] for result in results))
        self.assertEqual(stats.snapshot()['completed'], 1)
        self.assertEqual(stats.snapshot()['perfect'], 1)

    def test_failed_write_preserves_disk_and_retries_pending_count(self):
        stats = GameStats(self.path)
        stats.snapshot()
        previous = self.path.read_bytes()
        trainer = Trainer(stats)
        task = trainer.new('challenge')
        answer = ' '.join(ALPHABET[c] for c in task['prompt'])
        with patch('game_stats.os.fsync', side_effect=OSError('disk unavailable')):
            with self.assertLogs('natocheck', level='ERROR'):
                self.assertTrue(trainer.check(task['id'], answer)['passed'])
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        trainer.check(task['id'], answer)
        self.assertEqual(stats.snapshot()['completed'], 1)
        self.assertEqual(GameStats(self.path).snapshot()['completed'], 1)

    def test_invalid_existing_state_is_not_reset(self):
        for contents in ['broken', '[]', '{"version": 9}', '{"version": 1, "completed": true}']:
            with self.subTest(contents=contents):
                self.path.write_text(contents)
                with self.assertRaises(ValueError):
                    GameStats(self.path).snapshot()
                self.assertEqual(self.path.read_text(), contents)

    def test_http_returns_only_public_aggregates(self):
        app = Application(self.path.parent)
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(app, set()))
        port = server.server_address[1]
        server.RequestHandlerClass = handler(app, {f'127.0.0.1:{port}'})
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(path, payload=None):
            connection = http.client.HTTPConnection('127.0.0.1', port)
            connection.request('POST' if payload is not None else 'GET', path,
                               json.dumps(payload) if payload is not None else None,
                               {'Content-Type': 'application/json'})
            response = connection.getresponse()
            result = response.status, json.loads(response.read())
            connection.close()
            return result
        try:
            self.assertEqual(request('/api/stats')[1]['completed'], 0)
            _, task = request('/api/trainer/task', {'mode': 'challenge'})
            answer = ' '.join(ALPHABET[c] for c in task['prompt'])
            for _ in range(2):
                self.assertEqual(request('/api/trainer/check', {'task_id': task['id'], 'text': answer})[0], 200)
            status, result = request('/api/stats')
            self.assertEqual(status, 200)
            self.assertEqual((result['completed'], result['today_completed'], result['perfect']), (1, 1, 1))
            self.assertEqual(set(result), {'completed', 'today_completed', 'perfect', 'since', 'as_of', 'timezone'})
            self.assertNotIn(task['id'], json.dumps(result))
            self.assertEqual(request('/game-stats.json')[0], 404)
            app.stats = GameStats(self.path.parent / 'corrupt.json')
            app.stats.path.write_text('broken')
            with self.assertLogs('natocheck', level='ERROR'):
                self.assertEqual(request('/api/stats')[0], 503)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
