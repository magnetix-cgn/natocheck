# NatoCheck

A small NATO spelling game by Eventhacker. Play at:
**https://natocheck.eventhacker.de/**. This is an experimental training game.

## Interface languages

Use the DE / EN buttons in the header to switch the complete interface without
reloading or clearing entered answers or results. The selection is saved locally.
Direct links `/?lang=de` and `/?lang=en` select a language explicitly. German is
the default. Interface language does not change the English-only recognizer.

## Play

- The public interface shows the ten-letter challenge. Free training is hidden.
- Record in a quiet environment; preferably use a headset.
- Challenge: click **Spiel starten**, allow the microphone and follow a three-second
  countdown followed by **Go!**. Ten letters appear one after another at the selected pace: 1, 2, 3
  or 5 seconds per letter. The default is 3 seconds.
- One continuous recording covers the entire challenge. Recording stops after
  the tenth letter's time slot; only then is the audio transcribed and compared.
- A dedicated **Auswertung läuft** state is shown while the complete recording is processed.
- The prominent final result at the top of the page shows correct letters out of ten and a percentage,
  followed by the complete transcript and per-letter comparison.
- Aborting a challenge discards the recording without grading it.
- Free training supports manual recording, typed answers and transcript correction.
- Recording uses the default microphone and English recognition only. There is no
  microphone settings card or language selector; the server also enforces English.
- The **NATO-Alphabet einblenden** button opens the reference table.

The comparison checks codewords and their order, including missing and extra
words. It accepts explicit transcription variants such as Alpha/Alfa,
Juliet/Juliett, Whisky/Whiskey, Fox Trot/Foxtrot and X Ray/X-ray. It does not
infer correct answers from similar words: Beta is not Bravo. This compares
recognized text; it does not assess pronunciation quality.

Reference: [Bundeswehr NATO alphabet](https://www.bundeswehr.de/de/auftrag/verteidigung/nato-alphabet).
The official codewords displayed include Alfa and Juliett.

## Training video

Ron White's English video, *Memorize NATO Phonetic Alphabet in 7 minutes
(EASY!)* (7:44), appears directly on the page with its original thumbnail and a
large **Play video** button. Playback starts after clicking Play or **Training**.
The adjacent **YouTube**
button links to [the original](https://www.youtube.com/watch?v=j7GLe1XDSAE).
Starting a challenge pauses playback. Both interface
languages include the training controls and source attribution.

The original and a 720p H.264/AAC MP4 derivative are delivered through the
configured private Nextcloud AgentUp. Only a verified derivative is copied into
runtime storage, outside Git, and served through a fixed content-addressed URL
with byte-range support. Private intake links never enter the page or repository.
`training-video.json` pins the public source attribution, byte count and SHA-256.

The interface follows the Eventhacker profile palette (blue `#00AEEF`, deep black
`#0B0F14`, neutral gray `#2D2D33`, steel gray and white). The profile does not
bundle its licensed fonts, so the interface retains its local sans-serif fallback.

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
up to 2 MB (2,000,000 bytes) and 60 seconds. The browser requests 128 kbit/s
(about 0.96 MB per minute before container overhead), with room for encoder variation.
The browser rejects oversized blobs before upload; the server rejects oversized
Content-Length headers before reading the body (HTTP 413) and checks actual bytes.
Before Whisper sees an upload, forced local-only container parsing checks exactly
one supported mono/stereo audio stream (WebM/Ogg Opus or Vorbis, MP4 AAC), followed
by strict bounded decoding and measured PCM duration. One second of timing tolerance
is allowed; longer audio is rejected, including WebM without duration metadata.
Malformed, video-bearing, silent and unsupported recordings are rejected. Uploaded
files are treated only as audio data, never executed. Parser subprocesses have timeouts;
this validation is not a malware scanner or a guarantee against decoder vulnerabilities. Only one CPU transcription runs at a time. A persistent, isolated recognition worker
preloads the base model when the server starts and reuses it across recordings.
A 300-second job timeout terminates the worker process group; the next request
starts a fresh worker. Audio conversion and strict recognition checks are unchanged.
The result displays server recognition time (excluding upload and browser polling).

Uncertain Whisper segments produce an ungraded review state with the complete
transcript (up to 2,000 characters), rather than silently dropping words or
rejecting an otherwise readable recording. No score or expected answer is shown
until the user explicitly checks the corrected/confirmed text. The result is then
marked as manually corrected. Empty, oversized and unusable transcripts remain errors. A human microphone/accent check is still needed;
synthetic fixtures do not prove accuracy for all speakers.

The header displays the current Git release identity (`git describe --tags --always`),
including a dirty marker for local changes. Random sequences and challenges never
repeat a letter immediately; repeats with an intervening letter remain possible.
Training results appear directly above the input area and scroll into view after checking.

## Check

```sh
/home/magnetix/projects/xvx/xvx-venv/bin/python -m unittest discover -v
node --check trainer.js
node --check interface.js
```

Tests include ordered comparison, spelling variants, wrong/missing/extra words,
strict recognition confidence, recording cleanup, isolated transcription results,
busy handling, resident model reuse, worker crash/timeout recovery, HTTP exercise flow, origin checks and a ten-letter challenge task.
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

The proposed aggregate Grafana usage board, metric definitions and initial
installation approval gate are documented in [deploy/usage-monitoring.md](deploy/usage-monitoring.md).

## Fresh Debian / Xen guest

For a new Debian 13 VM with an XvX Python runtime, see
[the installation guide](deploy/debian-guest.md) and `scripts/bootstrap-debian.sh`.
The default invocation prints a plan; installation requires `--apply`.

## Origin

The recording pipeline and Eventhacker logo were reused from the owner's
`magnetix-cgn/gpt-gadgets` project. NatoCheck runs independently and contains no
Codex chat connection. No user transcripts, settings, models or credentials are
included.
