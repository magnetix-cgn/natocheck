"""Behavior checks for spelling exercises, aliases and ordered comparison."""
import unittest
from trainer import ALPHABET, Trainer, compare, spoken_tokens


class TrainerTests(unittest.TestCase):
    def test_complete_alphabet_is_accepted_in_order(self):
        result = compare('ABCDEFGHIJKLMNOPQRSTUVWXYZ', ' '.join(ALPHABET.values()))
        self.assertTrue(result['passed'])
        self.assertEqual(result['score'], 100)

    def test_known_transcription_variants(self):
        self.assertTrue(compare('AFJOWX', 'Alpha, Fox Trot, Juliet, Oskar, Whisky, X-Ray!')['passed'])
        self.assertEqual(spoken_tokens('Québec'), ['Quebec'])
        self.assertTrue(compare('V', 'Viktor')['passed'])

    def test_beta_is_not_bravo_and_plain_letters_are_not_codewords(self):
        self.assertFalse(compare('AB', 'Alpha Beta')['passed'])
        self.assertFalse(compare('ABC', 'A B C')['passed'])
        self.assertFalse(compare('NATO', 'NATO')['passed'])

    def test_missing_word_does_not_shift_later_matches(self):
        result = compare('ABCD', 'Alfa Charlie Delta')
        self.assertEqual([row['state'] for row in result['feedback']], ['correct', 'missing', 'correct', 'correct'])
        self.assertEqual(result['correct'], 3)

    def test_unknown_words_numbers_and_duplicates_are_not_discarded(self):
        for text in ('Alfa Bravo test', '1 Alfa Bravo', 'Alfa Alfa Bravo'):
            with self.subTest(text=text):
                result = compare('AB', text)
                self.assertFalse(result['passed'])
                self.assertLess(result['score'], 100)
                self.assertIn('extra', [row['state'] for row in result['feedback']])

    def test_reordered_words_do_not_pass(self):
        self.assertFalse(compare('ABCD', 'Bravo Alfa Charlie Delta')['passed'])

    def test_generation_and_server_side_prompt(self):
        trainer = Trainer()
        for mode in ('letter', 'word', 'sequence'):
            task = trainer.new(mode)
            self.assertTrue(all(c in ALPHABET for c in task['prompt']))
            self.assertNotIn('expected', task)
            self.assertTrue(trainer.check(task['id'], ' '.join(ALPHABET[c] for c in task['prompt']))['passed'])
        self.assertEqual(len(trainer.new('letter')['prompt']), 1)
        self.assertEqual(len(trainer.new('sequence')['prompt']), 4)
        for mode in (None, 'unknown', [], {}):
            with self.assertRaises(ValueError):
                trainer.new(mode)
        for task_id in (None, [], 'missing'):
            with self.assertRaises(ValueError):
                trainer.check(task_id, 'Alfa')

    def test_invalid_answers(self):
        for text in ('', '   ', '!!!', None, [], 'Alfa '*501):
            with self.subTest(text=text), self.assertRaises(ValueError):
                compare('A', text)


if __name__ == '__main__':
    unittest.main()
