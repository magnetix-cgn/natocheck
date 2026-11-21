"""Persist aggregate challenge counts without recordings or visitor identifiers."""
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo('Europe/Berlin')
SPEEDS = (1000, 2000, 3000, 5000)
SPEED_KEYS = tuple(str(speed) for speed in SPEEDS) + ('unknown',)


class GameStats:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.state = None
        self.dirty = False

    def _load(self, now):
        if self.state is not None:
            return
        try:
            state = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            state = dict(version=1, since=now.isoformat(), completed=0, perfect=0,
                         daily=dict(date=now.astimezone(BERLIN).date().isoformat(), completed=0))
            self.dirty = True
        if (not isinstance(state, dict) or state.get('version') != 1
                or any(type(state.get(key)) is not int or state[key] < 0 for key in ('completed', 'perfect'))
                or state['perfect'] > state['completed']
                or not isinstance(state.get('daily'), dict)
                or type(state['daily'].get('completed')) is not int
                or not 0 <= state['daily']['completed'] <= state['completed']):
            raise ValueError('Invalid game statistics')
        if datetime.fromisoformat(state['since']).tzinfo is None:
            raise ValueError('Statistics start requires a timezone')
        date.fromisoformat(state['daily']['date'])
        if 'details' not in state:
            state['details'] = dict(since=now.isoformat(), completed=0, score_total=0,
                                   by_speed={key: dict(completed=0, score_total=0) for key in SPEED_KEYS})
            self.dirty = True
        details = state['details']
        if (not isinstance(details, dict)
                or type(details.get('completed')) is not int
                or not 0 <= details['completed'] <= state['completed']
                or type(details.get('score_total')) is not int
                or not 0 <= details['score_total'] <= 100 * details['completed']
                or not isinstance(details.get('by_speed'), dict)
                or set(details['by_speed']) != set(SPEED_KEYS)):
            raise ValueError('Invalid detailed game statistics')
        if datetime.fromisoformat(details['since']).tzinfo is None:
            raise ValueError('Detailed statistics start requires a timezone')
        for counts in details['by_speed'].values():
            if (not isinstance(counts, dict) or type(counts.get('completed')) is not int
                    or counts['completed'] < 0 or type(counts.get('score_total')) is not int
                    or not 0 <= counts['score_total'] <= 100 * counts['completed']):
                raise ValueError('Invalid speed statistics')
        if any(sum(counts[key] for counts in details['by_speed'].values()) != details[key]
               for key in ('completed', 'score_total')):
            raise ValueError('Inconsistent detailed game statistics')
        self.state = state

    def _flush(self):
        if not self.dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             prefix='.game-stats-', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(self.state, stream, ensure_ascii=False)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
            self.dirty = False
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def record(self, perfect, now=None, *, speed_ms=None, score=None):
        if speed_ms is not None and (type(speed_ms) is not int or speed_ms not in SPEEDS):
            raise ValueError('Unsupported challenge speed')
        if score is None:
            score = 100 if perfect else 0
        if type(score) is not int or not 0 <= score <= 100:
            raise ValueError('Invalid challenge score')
        now = now or datetime.now(timezone.utc)
        today = now.astimezone(BERLIN).date().isoformat()
        with self.lock:
            self._load(now)
            self.state['completed'] += 1
            self.state['perfect'] += int(bool(perfect))
            if self.state['daily']['date'] != today:
                self.state['daily'] = dict(date=today, completed=0)
            self.state['daily']['completed'] += 1
            details = self.state['details']
            details['completed'] += 1
            details['score_total'] += score
            counts = details['by_speed'][str(speed_ms) if speed_ms is not None else 'unknown']
            counts['completed'] += 1
            counts['score_total'] += score
            self.dirty = True
            self._flush()

    def snapshot(self, now=None):
        now = now or datetime.now(timezone.utc)
        today = now.astimezone(BERLIN).date().isoformat()
        with self.lock:
            self._load(now)
            self._flush()
            details = self.state['details']
            def average(counts):
                return round(counts['score_total'] / counts['completed'], 1) if counts['completed'] else None
            return dict(completed=self.state['completed'], perfect=self.state['perfect'],
                        today_completed=self.state['daily']['completed'] if self.state['daily']['date'] == today else 0,
                        since=self.state['since'], as_of=now.isoformat(), timezone='Europe/Berlin',
                        details_since=details['since'], scored_completed=details['completed'],
                        average_score=average(details),
                        unclassified_completed=self.state['completed'] - sum(
                            details['by_speed'][str(speed)]['completed'] for speed in SPEEDS),
                        by_speed={str(speed): dict(completed=details['by_speed'][str(speed)]['completed'],
                                                  average_score=average(details['by_speed'][str(speed)]))
                                  for speed in SPEEDS})
