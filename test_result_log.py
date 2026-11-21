"""Verify private result history, revisions, persistence and failed-write recovery."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from game_stats import GameStats
from result_log import ResultLog
from trainer import ALPHABET, Trainer


class ResultLogTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.log = ResultLog(self.root / 'results', 'test-release')
        self.stats = GameStats(self.root / 'game-stats.json')
        self.trainer = Trainer(self.stats, self.log)

    def tearDown(self):
        self.folder.cleanup()

    def events(self):
        return [json.loads(line) for path in sorted(self.log.directory.glob('*.jsonl'))
                for line in path.read_text().splitlines()]

    def test_all_modes_are_logged_without_text_or_request_identifiers(self):
        for mode in ('letter', 'word', 'sequence', 'challenge'):
            task = self.trainer.new(mode, 2000 if mode == 'challenge' else None)
            answer = ' '.join(ALPHABET[c] for c in task['prompt'])
            self.trainer.check(task['id'], answer + ' privateanswer', 'text')
            event = self.events()[-1]
            self.assertEqual(event['mode'], mode)
            self.assertEqual(event['speed_ms'], 2000 if mode == 'challenge' else None)
            self.assertEqual(event['total'], len(task['prompt']))
            self.assertEqual(event['correct'], len(task['prompt']))
            self.assertEqual(event['outcomes'][-1], dict(letter='', state='extra'))
            self.assertTrue(event['first_evaluation'])
            self.assertEqual(event['source'], 'text')
            self.assertEqual(event['release'], 'test-release')
            self.assertEqual(event['public_stats_eligible'], mode == 'challenge')
            self.assertNotIn(task['id'], json.dumps(event))
            self.assertNotIn('privateanswer', json.dumps(event))
            self.assertEqual(set(event), {'version', 'event_id', 'result_id', 'evaluated_at', 'release',
                                         'mode', 'speed_ms', 'source', 'evaluation', 'first_evaluation',
                                         'public_stats_eligible', 'score', 'correct', 'total', 'passed', 'outcomes'})
        path = next(self.log.directory.glob('*.jsonl'))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.log.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.stats.snapshot()['completed'], 1)

    def test_concurrent_rechecks_have_unique_revisions_and_one_public_count(self):
        task = self.trainer.new('challenge', 1000)
        self.trainer.check(task['id'], 'Alfa', 'speech')
        answer = ' '.join(ALPHABET[c] for c in task['prompt'])
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _: self.trainer.check(task['id'], answer, 'correction'), range(12)))
        events = self.events()
        self.assertEqual(len(events), 13)
        self.assertEqual([event['evaluation'] for event in events], list(range(1, 14)))
        self.assertEqual(len({event['event_id'] for event in events}), 13)
        self.assertEqual(len({event['result_id'] for event in events}), 1)
        self.assertEqual(sum(event['public_stats_eligible'] for event in events), 1)
        self.assertTrue(all(event['source'] == 'correction' and not event['first_evaluation']
                            for event in events[1:]))
        self.assertEqual(self.stats.snapshot()['average_score'], events[0]['score'])

    def test_invalid_checks_and_unfinished_tasks_produce_no_events(self):
        self.trainer.new('challenge', 3000)
        task = self.trainer.new('letter')
        for task_id, answer, source in [(task['id'], '', 'speech'), ('missing', 'Alfa', 'text'),
                                        (task['id'], 'Alfa', 'private source'), (task['id'], 'Alfa', [])]:
            with self.assertRaises(ValueError):
                self.trainer.check(task_id, answer, source)
        self.assertEqual(self.events(), [])
        self.assertFalse(self.log.directory.exists())

    def test_failed_sync_restores_journal_and_retry_remains_first_evaluation(self):
        task = self.trainer.new('challenge', 3000)
        answer = ' '.join(ALPHABET[c] for c in task['prompt'])
        self.trainer.check(task['id'], answer, 'speech')
        path = next(self.log.directory.glob('*.jsonl'))
        previous = path.read_bytes()
        other = self.trainer.new('challenge', 5000)
        with patch('result_log.os.fsync', side_effect=[OSError('disk unavailable'), None]):
            with self.assertRaises(OSError):
                self.trainer.check(other['id'], 'Alfa', 'speech')
        self.assertEqual(path.read_bytes(), previous)
        self.assertEqual(self.stats.snapshot()['completed'], 1)
        self.trainer.check(other['id'], 'Alfa', 'speech')
        event = self.events()[-1]
        self.assertEqual(event['evaluation'], 1)
        self.assertTrue(event['public_stats_eligible'])
        self.assertEqual(self.stats.snapshot()['completed'], 2)

    def test_short_writes_are_completed_and_history_survives_new_logger(self):
        task = self.trainer.new('sequence')
        write = os.write
        with patch('result_log.os.write', side_effect=lambda fd, data: write(fd, data[:13])):
            self.trainer.check(task['id'], 'Alfa', 'synthetic')
        self.trainer.results = ResultLog(self.log.directory, 'next-release')
        self.trainer.check(task['id'], 'Bravo', 'synthetic')
        self.assertEqual(len(self.events()), 2)
        self.assertEqual([event['release'] for event in self.events()], ['test-release', 'next-release'])

    def test_utc_days_and_incomplete_tail_are_preserved(self):
        task = self.trainer.new('letter')
        stored = self.trainer.tasks[task['id']]
        from trainer import compare
        result = compare(task['prompt'], 'Alfa')
        for day in (21, 22):
            self.log.record(stored, result, 'text', datetime(2026, 11, day, tzinfo=timezone.utc))
        paths = sorted(self.log.directory.glob('*.jsonl'))
        self.assertEqual([path.name for path in paths], ['results-2026-11-21.jsonl', 'results-2026-11-22.jsonl'])
        with paths[0].open('ab') as stream:
            stream.write(b'{"partial":')
        previous = paths[0].read_bytes()
        with self.assertRaises(OSError):
            self.log.record(stored, result, 'text', datetime(2026, 11, 21, tzinfo=timezone.utc))
        self.assertEqual(paths[0].read_bytes(), previous)
