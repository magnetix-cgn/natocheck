"""Regression checks for unreliable local speech recognition."""
import unittest

from recording import recognized_text


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


if __name__ == '__main__':
    unittest.main()
