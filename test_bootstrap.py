"""Check installer planning without changing the host."""
import ast
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('scripts') / 'bootstrap-debian.sh'


class BootstrapTests(unittest.TestCase):
    def test_plan_has_no_external_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            marker = folder / 'called'
            for command in ('curl', 'git', 'apt-get', 'python3', 'systemctl'):
                path = folder / command
                path.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 99\n')
                path.chmod(0o755)
            result = subprocess.run(['/bin/bash', str(SCRIPT), '--threads', '4'],
                env={**os.environ, 'PATH': str(folder) + ':/usr/bin:/bin'}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Plan only', result.stdout)
            self.assertFalse(marker.exists())

    def test_help_and_invalid_arguments(self):
        result = subprocess.run(['/bin/bash', str(SCRIPT), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        for args in (['--threads', '0'], ['--threads', '2;true'], ['--model'], ['--unknown']):
            with self.subTest(args=args):
                result = subprocess.run(['/bin/bash', str(SCRIPT), *args], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)

    def test_shell_and_embedded_python_syntax(self):
        subprocess.run(['/bin/bash', '-n', str(SCRIPT)], check=True)
        blocks = re.findall(r"<<'PY'\n(.*?)\nPY", SCRIPT.read_text(), re.S)
        self.assertEqual(len(blocks), 2)
        for block in blocks:
            ast.parse(block)
