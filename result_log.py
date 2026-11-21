"""Keep private, durable result events for later statistical analysis."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import uuid


class ResultLog:
    def __init__(self, directory, release):
        self.directory = Path(directory)
        self.release = release

    def record(self, task, result, source, now=None):
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        event = dict(
            version=1, event_id=uuid.uuid4().hex, result_id=task['result_id'],
            evaluated_at=now.isoformat(), release=self.release,
            mode=task['mode'], speed_ms=task['speed_ms'], source=source,
            evaluation=task['evaluations'] + 1, first_evaluation=task['evaluations'] == 0,
            public_stats_eligible=task['mode'] == 'challenge' and task['evaluations'] == 0,
            score=result['score'], correct=result['correct'], total=result['total'],
            passed=result['passed'],
            outcomes=[dict(letter=row['letter'], state=row['state']) for row in result['feedback']],
        )
        data = (json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.directory / f'results-{now.date().isoformat()}.jsonl'
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            size = os.fstat(descriptor).st_size
            if size and os.pread(descriptor, 1, size - 1) != b'\n':
                raise OSError('Result journal has an incomplete final entry; preserve and inspect it')
            try:
                remaining = memoryview(data)
                while remaining:
                    written = os.write(descriptor, remaining)
                    if written == 0:
                        raise OSError('Could not append result event')
                    remaining = remaining[written:]
                os.fsync(descriptor)
            except OSError:
                # Restore the previous complete journal before allowing a retry.
                os.ftruncate(descriptor, size)
                os.fsync(descriptor)
                raise
        finally:
            os.close(descriptor)
