"""Local NATO spelling exercises and deterministic transcript comparison."""
import collections
import re
import secrets
import string
import threading
import unicodedata
import uuid


ALPHABET = dict(zip(string.ascii_uppercase, (
    'Alfa', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel',
    'India', 'Juliett', 'Kilo', 'Lima', 'Mike', 'November', 'Oscar', 'Papa',
    'Quebec', 'Romeo', 'Sierra', 'Tango', 'Uniform', 'Victor', 'Whiskey',
    'X-ray', 'Yankee', 'Zulu',
)))
WORDS = ('NATO', 'RADIO', 'HOTEL', 'KABEL', 'TECHNO', 'LICHT', 'STAGE',
         'CLUB', 'LASER', 'MIXER', 'SOUND', 'FUNK', 'TANGO', 'ECHO', 'KONTROLLE')
ALIASES = {word.lower().replace('-', ''): word for word in ALPHABET.values()}
ALIASES.update({'alpha': 'Alfa', 'juliet': 'Juliett', 'whisky': 'Whiskey',
                'oskar': 'Oscar', 'viktor': 'Victor', 'charly': 'Charlie'})


def spoken_tokens(text):
    """Normalize spelling variants, without guessing or dropping unknown words."""
    normalized = unicodedata.normalize('NFKD', text.lower())
    normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
    words = re.findall(r'[^\W_]+', normalized, re.UNICODE)
    result = []
    index = 0
    while index < len(words):
        pair = tuple(words[index:index + 2])
        if pair in {('fox', 'trot'), ('x', 'ray')}:
            result.append(ALIASES[''.join(pair)])
            index += 2
        else:
            result.append(ALIASES.get(words[index], words[index]))
            index += 1
    return result


def compare(prompt, text):
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        raise ValueError('Enter between 1 and 2000 characters of recognized text')
    expected = [ALPHABET[letter] for letter in prompt]
    spoken = spoken_tokens(text)
    if not spoken or len(spoken) > 100:
        raise ValueError('Answer must contain between 1 and 100 words')
    # Edit-distance alignment keeps later correct words aligned after omissions.
    rows, columns = len(expected), len(spoken)
    costs = [[0] * (columns + 1) for _ in range(rows + 1)]
    for i in range(rows + 1):
        costs[i][0] = i
    for j in range(columns + 1):
        costs[0][j] = j
    for i in range(1, rows + 1):
        for j in range(1, columns + 1):
            costs[i][j] = min(costs[i - 1][j] + 1, costs[i][j - 1] + 1,
                              costs[i - 1][j - 1] + (expected[i - 1] != spoken[j - 1]))
    feedback = []
    i, j = rows, columns
    while i or j:
        if i and j and costs[i][j] == costs[i - 1][j - 1] + (expected[i - 1] != spoken[j - 1]):
            feedback.append(dict(letter=prompt[i - 1], expected=expected[i - 1],
                                 heard=spoken[j - 1],
                                 state='correct' if expected[i - 1] == spoken[j - 1] else 'wrong'))
            i, j = i - 1, j - 1
        elif i and costs[i][j] == costs[i - 1][j] + 1:
            feedback.append(dict(letter=prompt[i - 1], expected=expected[i - 1], heard='', state='missing'))
            i -= 1
        else:
            feedback.append(dict(letter='', expected='', heard=spoken[j - 1], state='extra'))
            j -= 1
    feedback.reverse()
    correct = sum(item['state'] == 'correct' for item in feedback)
    return dict(passed=costs[rows][columns] == 0, correct=correct, total=rows,
                expected=expected, spoken=spoken, feedback=feedback,
                score=round(100 * correct / max(rows, columns)))


class Trainer:
    def __init__(self):
        self.tasks = collections.OrderedDict()
        self.lock = threading.Lock()

    def new(self, mode):
        if mode == 'letter':
            prompt = secrets.choice(string.ascii_uppercase)
        elif mode == 'word':
            prompt = secrets.choice(WORDS)
        elif mode == 'challenge':
            prompt = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(10))
        elif mode == 'sequence':
            prompt = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(4))
        else:
            raise ValueError('Choose letter, word or sequence')
        task = dict(id=uuid.uuid4().hex, mode=mode, prompt=prompt)
        with self.lock:
            self.tasks[task['id']] = task
            if len(self.tasks) > 200:
                self.tasks.popitem(last=False)
        return task

    def check(self, task_id, text):
        if not isinstance(task_id, str):
            raise ValueError('A task identifier is required')
        with self.lock:
            task = self.tasks.get(task_id)
        if task is None:
            raise ValueError('This exercise has expired; request a new exercise')
        return compare(task['prompt'], text)
