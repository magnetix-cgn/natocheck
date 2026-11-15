# NatoCheck

A small NATO spelling game by Eventhacker. Play at:
**https://natocheck.eventhacker.de/**. This is an experimental training game.

## Play

- Free training: single letters, words or four-letter sequences.
- Challenge: click **Spiel starten**, allow the microphone and follow a three-second
  countdown. Ten letters appear one after another at the selected pace: 1, 2, 3
  or 5 seconds per letter. The default is 3 seconds.
- One continuous recording covers the entire challenge. Recording stops after
  the tenth letter's time slot; only then is the audio transcribed and compared.
- The prominent final result shows correct letters out of ten and a percentage,
  followed by the complete transcript and per-letter comparison.
- Aborting a challenge discards the recording without grading it.
- Free training supports manual recording, typed answers and transcript correction.
- The **NATO-Alphabet einblenden** button opens the reference table.

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
busy handling, HTTP exercise flow, origin checks and a ten-letter challenge task.
For browser acceptance, verify the countdown, each selected pace, one continuous
recording, cancellation, delayed transcription and the prominent final result.

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
