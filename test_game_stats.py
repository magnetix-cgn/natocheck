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
        task = trainer.new('challenge', 1000)
        answer = ' '.join(ALPHABET[c] for c in task['prompt'])
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: trainer.check(task['id'], answer), range(24)))
        self.assertTrue(all(result['passed'] for result in results))
        self.assertEqual(stats.snapshot()['completed'], 1)
        self.assertEqual(stats.snapshot()['perfect'], 1)
        self.assertEqual(stats.snapshot()['by_speed']['1000'], dict(completed=1, average_score=100.0))

    def test_speed_and_score_use_first_evaluation_and_survive_restart(self):
        stats = GameStats(self.path)
        trainer = Trainer(stats)
        with patch('trainer.secrets.choice', side_effect=lambda letters: letters[0]):
            for speed, correct in [(1000, 2), (2000, 4), (3000, 6), (5000, 8), (2000, 10)]:
                task = trainer.new('challenge', speed)
                answer = ' '.join(ALPHABET[c] for c in task['prompt'][:correct])
                result = trainer.check(task['id'], answer)
                self.assertEqual(result['score'], correct * 10)
                trainer.check(task['id'], ' '.join(ALPHABET[c] for c in task['prompt']))
        result = GameStats(self.path).snapshot()
        self.assertEqual(result['average_score'], 60.0)
        self.assertEqual(result['scored_completed'], 5)
        self.assertEqual(result['unclassified_completed'], 0)
        self.assertEqual(result['by_speed']['2000'], dict(completed=2, average_score=70.0))
        for speed, score in [('1000', 20), ('3000', 60), ('5000', 80)]:
            self.assertEqual(result['by_speed'][speed], dict(completed=1, average_score=score))

    def test_existing_counts_migrate_without_inventing_speed_or_score(self):
        since = '2026-11-20T10:00:00+00:00'
        self.path.write_text(json.dumps(dict(version=1, since=since, completed=17, perfect=3,
                                            daily=dict(date='2026-11-21', completed=4))))
        now = datetime(2026, 11, 21, 18, 0, tzinfo=timezone.utc)
        stats = GameStats(self.path)
        initial = stats.snapshot(now)
        self.assertEqual(initial['completed'], 17)
        self.assertEqual(initial['perfect'], 3)
        self.assertEqual(initial['today_completed'], 4)
        self.assertEqual(initial['since'], since)
        self.assertEqual(initial['details_since'], now.isoformat())
        self.assertEqual(initial['unclassified_completed'], 17)
        self.assertEqual(initial['scored_completed'], 0)
        self.assertIsNone(initial['average_score'])
        self.assertTrue(all(row == dict(completed=0, average_score=None) for row in initial['by_speed'].values()))
        stats.record(False, now, speed_ms=3000, score=40)
        stats.record(True, now, score=100)
        restored = GameStats(self.path).snapshot(now)
        self.assertEqual(restored['completed'], 19)
        self.assertEqual(restored['average_score'], 70.0)
        self.assertEqual(restored['scored_completed'], 2)
        self.assertEqual(restored['unclassified_completed'], 18)
        self.assertEqual(restored['by_speed']['3000'], dict(completed=1, average_score=40.0))

    def test_invalid_speed_and_score_do_not_change_counts(self):
        stats = GameStats(self.path)
        trainer = Trainer(stats)
        for speed in (True, '2000', 1500, 0, [], {}):
            with self.subTest(speed=speed), self.assertRaises(ValueError):
                trainer.new('challenge', speed)
        with self.assertRaises(ValueError):
            trainer.new('letter', 2000)
        for score in (True, -1, 101, '50'):
            with self.subTest(score=score), self.assertRaises(ValueError):
                stats.record(False, score=score)
        self.assertEqual(stats.snapshot()['completed'], 0)

    def test_corrupt_detail_totals_are_preserved_and_rejected(self):
        GameStats(self.path).snapshot()
        state = json.loads(self.path.read_text())
        state['details']['by_speed']['1000']['completed'] = 1
        self.path.write_text(json.dumps(state))
        previous = self.path.read_bytes()
        with self.assertRaises(ValueError):
            GameStats(self.path).snapshot()
        self.assertEqual(self.path.read_bytes(), previous)

    def test_failed_write_preserves_disk_and_retries_pending_count(self):
        stats = GameStats(self.path)
        stats.snapshot()
        previous = self.path.read_bytes()
        trainer = Trainer(stats)
        task = trainer.new('challenge', 2000)
        answer = ' '.join(ALPHABET[c] for c in task['prompt'])
        with patch('game_stats.os.fsync', side_effect=OSError('disk unavailable')):
            with self.assertLogs('natocheck', level='ERROR'):
                self.assertTrue(trainer.check(task['id'], answer)['passed'])
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        trainer.check(task['id'], answer)
        self.assertEqual(stats.snapshot()['completed'], 1)
        self.assertEqual(GameStats(self.path).snapshot()['completed'], 1)
        self.assertEqual(GameStats(self.path).snapshot()['by_speed']['2000'], dict(completed=1, average_score=100.0))

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
            self.assertEqual(request('/api/trainer/task', {'mode': 'challenge', 'speed_ms': 1500})[0], 400)
            _, task = request('/api/trainer/task', {'mode': 'challenge', 'speed_ms': 2000})
            answer = ' '.join(ALPHABET[c] for c in task['prompt'])
            for _ in range(2):
                self.assertEqual(request('/api/trainer/check', {'task_id': task['id'], 'text': answer})[0], 200)
            status, result = request('/api/stats')
            self.assertEqual(status, 200)
            self.assertEqual((result['completed'], result['today_completed'], result['perfect']), (1, 1, 1))
            self.assertEqual(result['by_speed']['2000'], dict(completed=1, average_score=100.0))
            self.assertEqual(result['average_score'], 100.0)
            self.assertEqual(set(result), {'completed', 'today_completed', 'perfect', 'since', 'as_of', 'timezone',
                                           'details_since', 'scored_completed', 'average_score',
                                           'unclassified_completed', 'by_speed'})
            self.assertNotIn(task['id'], json.dumps(result))
            self.assertEqual(request('/game-stats.json')[0], 404)
            journals = list((self.path.parent / 'results').glob('*.jsonl'))
            self.assertEqual(len(journals), 1)
            events = [json.loads(line) for line in journals[0].read_text().splitlines()]
            self.assertEqual(len(events), 2)
            self.assertEqual([event['first_evaluation'] for event in events], [True, False])
            self.assertEqual(request('/results/' + journals[0].name)[0], 404)
            with patch.object(app.trainer.results, 'record', side_effect=OSError('disk unavailable')):
                with self.assertLogs('natocheck', level='ERROR'):
                    self.assertEqual(request('/api/trainer/check', {'task_id': task['id'], 'text': answer})[0], 503)
            app.stats = GameStats(self.path.parent / 'corrupt.json')
            app.stats.path.write_text('broken')
            with self.assertLogs('natocheck', level='ERROR'):
                self.assertEqual(request('/api/stats')[0], 503)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
