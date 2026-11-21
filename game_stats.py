"""Persist aggregate challenge counts without recordings or visitor identifiers."""
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo('Europe/Berlin')


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

    def record(self, perfect, now=None):
        now = now or datetime.now(timezone.utc)
        today = now.astimezone(BERLIN).date().isoformat()
        with self.lock:
            self._load(now)
            self.state['completed'] += 1
            self.state['perfect'] += int(bool(perfect))
            if self.state['daily']['date'] != today:
                self.state['daily'] = dict(date=today, completed=0)
            self.state['daily']['completed'] += 1
            self.dirty = True
            self._flush()

    def snapshot(self, now=None):
        now = now or datetime.now(timezone.utc)
        today = now.astimezone(BERLIN).date().isoformat()
        with self.lock:
            self._load(now)
            self._flush()
            return dict(completed=self.state['completed'], perfect=self.state['perfect'],
                        today_completed=self.state['daily']['completed'] if self.state['daily']['date'] == today else 0,
                        since=self.state['since'], as_of=now.isoformat(), timezone='Europe/Berlin')
