"""Regression checks for unreliable local speech recognition."""
import unittest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from recording import MAX_UPLOAD_BYTES, recognized_text, transcribe, validate_recording


def segment(text='Hallo Welt', **metrics):
    return dict(text=text, no_speech_prob=0.01, avg_logprob=-0.2,
                compression_ratio=1.2) | metrics


class RecognitionTests(unittest.TestCase):
    def test_preserves_reliable_segments_in_order(self):
        self.assertEqual(recognized_text({'segments': [segment(' Hallo '),
                         segment(' Welt ')]}), 'Hallo Welt')

    def test_rejects_unreliable_segments_even_when_full_text_exists(self):
        for metrics in ({'no_speech_prob': 0.8}, {'avg_logprob': -1.5},
                        {'compression_ratio': 3.0}, {'avg_logprob': float('nan')}):
            with self.subTest(metrics=metrics), self.assertRaises(ValueError):
                recognized_text({'text': 'Invented words',
                                 'segments': [segment(**metrics)]})

    def test_does_not_append_uncertain_text_to_speech(self):
        self.assertEqual(recognized_text({'segments': [segment(),
                         segment('Invented words', no_speech_prob=0.9)]}), 'Hallo Welt')

    def test_strict_mode_does_not_silently_drop_uncertain_answer_words(self):
        with self.assertRaises(ValueError):
            recognized_text({'segments': [segment('Alfa'),
                            segment('Beta', avg_logprob=-1.5)]}, strict=True)
        self.assertEqual(recognized_text({'segments': [segment('Alfa')]}, strict=True), 'Alfa')

    def test_requires_segment_confidence_and_nonempty_text(self):
        for result in ({}, {'segments': [{'text': 'Unknown confidence'}]},
                       {'segments': [segment(' ')]}):
            with self.subTest(result=result), self.assertRaises(ValueError):
                recognized_text(result)


class UploadValidationTests(unittest.TestCase):
    def make_audio(self, path, seconds=1, codec='libopus'):
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi',
                        '-i', 'sine=frequency=440:sample_rate=48000', '-t', str(seconds),
                        '-c:a', codec, str(path)], check=True, capture_output=True, timeout=20)

    def test_supported_browser_formats_decode(self):
        with tempfile.TemporaryDirectory() as folder:
            for suffix, codec in (('.webm', 'libopus'), ('.ogg', 'libopus'), ('.m4a', 'aac')):
                with self.subTest(suffix=suffix):
                    source = Path(folder) / ('valid' + suffix)
                    self.make_audio(source, codec=codec)
                    validate_recording(source, Path(folder) / 'decoded.wav')

    def test_missing_duration_cannot_bypass_decoded_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'long.webm'
            self.make_audio(source, seconds=63)
            # Browser WebM often omits duration; force that metadata case here.
            import recording
            real_run = subprocess.run
            def run(args, **kwargs):
                result = real_run(args, **kwargs)
                if args[0] == 'ffprobe':
                    import json
                    metadata = json.loads(result.stdout)
                    metadata['format'].pop('duration', None)
                    result.stdout = json.dumps(metadata)
                return result
            with patch.object(recording.subprocess, 'run', side_effect=run):
                with self.assertRaisesRegex(ValueError, '60-second'):
                    validate_recording(source, Path(folder) / 'decoded.wav')

    def test_invalid_inputs_never_reach_whisper(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'invalid.webm'
            for data in (b'not audio', b'\x1aE\xdf\xa3broken', b'x' * (MAX_UPLOAD_BYTES + 1)):
                source.write_bytes(data)
                with patch('recording.load_model') as model:
                    with self.assertRaises(ValueError):
                        transcribe(source, 'en', Path(folder) / 'text.txt')
                    model.assert_not_called()

    def test_video_stream_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'video.webm'
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi',
                            '-i', 'color=size=16x16:rate=1', '-t', '1', '-c:v', 'libvpx',
                            str(source)], check=True, capture_output=True, timeout=20)
            with self.assertRaisesRegex(ValueError, 'audio stream'):
                validate_recording(source, Path(folder) / 'decoded.wav')


if __name__ == '__main__':
    unittest.main()
