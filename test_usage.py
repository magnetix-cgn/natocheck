"""Verify rotated-log accounting, privacy and rolling-window boundaries."""
import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('usage', Path(__file__).parent / 'scripts/export-usage.py')
usage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(usage)


class UsageTests(unittest.TestCase):
    def test_rotated_logs_windows_and_request_semantics(self):
        with tempfile.TemporaryDirectory() as folder:
            current = Path(folder) / 'natocheck-access.log'
            rotated = Path(folder) / 'natocheck-access.log.1.gz'
            prefix = '192.0.2.1 - - [19/Nov/2026:12:00:00 +0000] '
            current.write_text(prefix + '"POST /api/transcribe HTTP/1.1" 202 20 "-" "private-agent"\n'
                               + prefix + '"POST /api/transcribe HTTP/1.1" 400 20 "-" "private-agent"\n'
                               + prefix + '"GET /?lang=de HTTP/1.1" 200 100 "-" "private-agent"\n'
                               + 'malformed\n', encoding='utf-8')
            with gzip.open(rotated, 'wt') as stream:
                stream.write('192.0.2.1 - - [18/Nov/2026:12:00:00 +0000] "POST /api/trainer/task HTTP/1.1" 200 50 "-" "agent"\n')
            now = usage.dt.datetime(2026, 11, 19, 12, tzinfo=usage.dt.timezone.utc).timestamp()
            result = usage.collect([current, rotated], now)
            self.assertIn('window="1h",event="upload",status="2xx"} 1', result)
            self.assertIn('window="1h",event="upload",status="4xx"} 1', result)
            self.assertIn('window="24h",event="exercise",status="2xx"} 0', result)
            self.assertIn('window="7d",event="exercise",status="2xx"} 1', result)
            self.assertIn('natocheck_usage_malformed_lines 1', result)
            self.assertNotIn('192.0.2.1', result)
            self.assertNotIn('private-agent', result)

    def test_failed_read_preserves_existing_output_and_atomic_replace(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'usage.prom'
            usage.write_atomic(target, 'previous\n')
            with self.assertRaises(FileNotFoundError):
                usage.write_atomic(target, usage.collect([Path(folder) / 'missing'], 100))
            self.assertEqual(target.read_text(), 'previous\n')
            usage.write_atomic(target, 'replacement\n')
            self.assertEqual(target.read_text(), 'replacement\n')
            self.assertEqual(list(Path(folder).iterdir()), [target])


if __name__ == '__main__':
    unittest.main()
