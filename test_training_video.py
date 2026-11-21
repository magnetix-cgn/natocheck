"""Check real HTTP byte ranges, pinned asset isolation and training markup."""
import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from app import Application, handler
from training_video import VIDEO, VIDEO_FILENAME, VIDEO_URL


class TrainingVideoTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.output = Path(self.temporary.name)
        self.data = b'abcdefghijklmnopqrstuvwxyz'
        self.source = self.output / 'training' / VIDEO_FILENAME
        self.source.parent.mkdir()
        self.source.write_bytes(self.data)
        self.manifest = patch.dict(VIDEO, bytes=len(self.data))
        self.manifest.start()
        app = Application(self.output)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler(app, set()))
        self.port = self.server.server_address[1]
        self.server.RequestHandlerClass = handler(app, {f'127.0.0.1:{self.port}'})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.manifest.stop()
        self.temporary.cleanup()

    def request(self, path=VIDEO_URL, method='GET', **headers):
        connection = http.client.HTTPConnection('127.0.0.1', self.port)
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_full_and_head_response(self):
        status, headers, body = self.request()
        self.assertEqual((status, body), (200, self.data))
        self.assertEqual(headers['Content-Type'], 'video/mp4')
        self.assertEqual(headers['Accept-Ranges'], 'bytes')
        self.assertEqual(headers['Content-Length'], str(len(self.data)))
        status, headers, body = self.request(method='HEAD')
        self.assertEqual((status, body), (200, b''))
        self.assertEqual(headers['Content-Length'], str(len(self.data)))

    def test_seek_ranges_and_if_range(self):
        for requested, expected, content_range in [('bytes=3-6', b'defg', 'bytes 3-6/26'),
                ('bytes=23-', b'xyz', 'bytes 23-25/26'),
                ('bytes=-4', b'wxyz', 'bytes 22-25/26'),
                ('bytes=23-999', b'xyz', 'bytes 23-25/26')]:
            with self.subTest(requested=requested):
                status, headers, body = self.request(Range=requested)
                self.assertEqual((status, body), (206, expected))
                self.assertEqual(headers['Content-Range'], content_range)
                self.assertEqual(int(headers['Content-Length']), len(expected))
        status, _, body = self.request(Range='bytes=0-1', **{'If-Range': '"old"'})
        self.assertEqual((status, body), (200, self.data))

    def test_invalid_ranges_are_bounded(self):
        for requested in ['bytes=99-', 'bytes=8-1', 'bytes=-0', 'bytes=-', 'bytes=0-1,3-4', 'bytes=' + '9' * 100 + '-']:
            with self.subTest(requested=requested):
                status, headers, body = self.request(Range=requested)
                self.assertEqual((status, body), (416, b''))
                self.assertEqual(headers['Content-Range'], 'bytes */26')

    def test_missing_wrong_size_and_unrelated_files_are_not_served(self):
        self.source.write_bytes(b'wrong')
        self.assertEqual(self.request()[0], 503)
        self.source.unlink()
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(self.request('/training/training-video.json')[0], 404)
        self.assertEqual(self.request('/training/../../app.py')[0], 404)
        self.assertEqual(self.request(Origin='https://untrusted.invalid')[0], 403)

    def test_training_controls_credit_source_and_lazy_video(self):
        status, _, body = self.request('/')
        self.assertEqual(status, 200)
        self.assertLess(body.index(b'id="trainingToggle"'), body.index(b'>YouTube</a>'))
        self.assertIn(VIDEO_URL.encode(), body)
        self.assertNotIn(b'{{TRAINING_VIDEO_URL}}', body)
        self.assertIn(b'https://www.youtube.com/watch?v=j7GLe1XDSAE', body)
        self.assertIn(b'Ron White', body)
        self.assertIn(b'controls playsinline preload="none"', body)
        self.assertNotIn(b'autoplay', body)
        self.assertNotIn(b'public.php', body)


if __name__ == '__main__':
    unittest.main()
