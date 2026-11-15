# NatoCheck

A small NATO spelling game by Eventhacker. Play at:
**https://natocheck.eventhacker.de/**. This is an experimental training game.

## Play

- Free training: single letters, words or four-letter sequences.
- Challenge: ten rounds, three lives and 30 seconds per round. Rounds 1–3 use
  letters, 4–6 use sequences and 7–10 use words.
- Speak the NATO codewords, stop recording and inspect the recognized text and
  comparison. In the challenge, confirm the result before points or lives change.
- Recognition and review time do not consume the round timer. A recognition
  failure produces no graded answer; retry within the remaining speaking time.
- A correct unassisted round earns 100 points, plus 20 per preceding consecutive
  correct round and two per remaining whole second. Wrong answers or idle timeouts
  cost one life and reset the streak.
- The **NATO-Alphabet einblenden** button opens the reference table. Using it
  during a challenge round earns 50 points for a correct answer and no bonuses.
  Closing the table does not remove that round's assisted flag.
- Edit recognition mistakes in free training, or practice with typed answers.
  Manual answers are labeled and are unavailable during a challenge.
- The highscore stays in browser local storage. There is no account or leaderboard.

The comparison checks codewords and their order, including missing and extra
words. It accepts explicit transcription variants such as Alpha/Alfa,
Juliet/Juliett, Whisky/Whiskey, Fox Trot/Foxtrot and X Ray/X-ray. It does not
infer correct answers from similar words: Beta is not Bravo. This compares
recognized text; it does not assess pronunciation quality.

Reference: [Bundeswehr NATO alphabet](https://www.bundeswehr.de/de/auftrag/verteidigung/nato-alphabet).
The official codewords displayed include Alfa and Juliett.

## Run locally in XvX

Use the existing XvX environment. Do not create another environment in the XvX
workspace. The microphone requires Chromium on localhost or a valid HTTPS site.

```sh
cd /home/magnetix/projects/xvx/externals/natocheck
/home/magnetix/projects/xvx/xvx-venv/bin/python app.py
```

Open **http://127.0.0.1:8767/**. No Codex session, OpenAI API key or cloud
speech service is needed. Speech recognition needs `ffmpeg`, `ffprobe`, the
pinned `openai-whisper` package in `requirements.txt`, and an existing local
Whisper base model at `~/.cache/whisper/base.pt`. The recognizer receives the complete NATO vocabulary as context, never the
exercise or its expected answer. It uses deterministic beam decoding. The application never downloads
models during transcription. Model provisioning is a separate installation step.

Configuration:

| Variable | Default / purpose |
| --- | --- |
| `NATOCHECK_DATA_DIR` | `out.user.local/` beside the application; temporary uploads |
| `NATOCHECK_WHISPER_MODEL` | `~/.cache/whisper/base.pt`; existing model file |
| `NATOCHECK_ALLOWED_HOSTS` | Extra comma-separated HTTP Host values for a reverse proxy |
| `OMP_NUM_THREADS` | Two for each recognition subprocess unless configured otherwise |

In XvX, set `NATOCHECK_DATA_DIR` to a skill-local runtime directory, for example
`/home/magnetix/projects/xvx/skills/whisper/out.user.magnetix/natocheck`.
The app binds only to `127.0.0.1`; `--port` defaults to 8767.

Browser recordings are uploaded to the app server. Conversion, audio and text
files are removed after recognition, including failed recognition. Recognition
jobs and their texts stay only in bounded process memory (up to 100 jobs) until
eviction or restart; access requires an unguessable job identifier. A browser
preview remains until the next recording, exercise or page close. No recording
is sent to an external speech service or a chat. Uploads support WebM, Ogg and MP4,
up to 12 MB and 60 seconds. Only one CPU transcription runs at a time.

Uncertain, non-speech and repetitive Whisper segments cause the whole answer to
be rejected rather than silently dropping answer words. This conservative
filter can reject valid speech. A human microphone/accent check is still needed;
synthetic fixtures do not prove accuracy for all speakers.

## Check

```sh
/home/magnetix/projects/xvx/xvx-venv/bin/python -m unittest discover -v
node --check trainer.js
```

Tests include ordered comparison, spelling variants, wrong/missing/extra words,
strict recognition confidence, recording cleanup, isolated transcription results,
busy handling, HTTP exercise flow and origin checks. Browser checks cover desktop
and mobile layouts, the ten-round game, increasing difficulty, score confirmation,
three lives, timeout, paused recognition time and reference-table scoring.

## Open source and contributions

NatoCheck is open source under the [MIT license](LICENSE). Want to change it?
[Send a task, bug report or change request](https://github.com/magnetix-cgn/natocheck/issues/new?template=change_request.yml).
German and English are welcome. Pull requests are welcome too; describe the
change and how you checked it. The app includes the same invitation in both
languages.

## Hosting

See [deploy/README.md](deploy/README.md). The initial DNS, HTTPS, service and release setup was approved and completed.
The HTTPS page and exercise API were verified. Future infrastructure changes
still require appropriate authorization.

## Origin

The recording pipeline and Eventhacker logo were reused from the owner's
`magnetix-cgn/gpt-gadgets` project. NatoCheck runs independently and contains no
Codex chat connection. No user transcripts, settings, models or credentials are
included.
