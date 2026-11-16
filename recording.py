"""Normalize browser recordings and transcribe with the existing local Whisper skill."""
import argparse
from contextlib import redirect_stdout
from functools import lru_cache
from array import array
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import sys
import wave

from trainer import ALPHABET


LOG = logging.getLogger('natocheck.audio')

MAX_UPLOAD_BYTES = 2_000_000
MAX_RECORDING_SECONDS = 60
# Allow one second for browser stop scheduling and container timestamp rounding.
MAX_DECODED_SECONDS = MAX_RECORDING_SECONDS + 1
INPUT_FORMATS = {'.webm': ('matroska', {'opus', 'vorbis'}),
                 '.ogg': ('ogg', {'opus', 'vorbis'}),
                 '.m4a': ('mov', {'aac'})}

MAX_NO_SPEECH_PROBABILITY = 0.6
MIN_AVERAGE_LOG_PROBABILITY = -1.0
MAX_COMPRESSION_RATIO = 2.4


class UncertainSpeechError(ValueError):
    """Carry an ungraded transcript for explicit human review."""
    def __init__(self, text):
        super().__init__('Uncertain speech segment; review the transcript before grading')
        self.text = text


def recognized_text(result, strict=False):
    """Discard uncertain, non-speech and repetitive decoding segments."""
    accepted = []
    review_text = ' '.join(str(segment.get('text', '')).strip()
                           for segment in result.get('segments', [])).strip()
    def uncertain():
        if 0 < len(review_text) <= 2000:
            raise UncertainSpeechError(review_text)
        raise ValueError('No usable transcript; please record again')
    for segment in result.get('segments', []):
        metrics = [segment.get('no_speech_prob'), segment.get('avg_logprob'),
                   segment.get('compression_ratio')]
        if any(not isinstance(value, (int, float)) or not math.isfinite(value)
               for value in metrics):
            if strict:
                uncertain()
            continue
        no_speech, log_probability, compression = metrics
        if (no_speech >= MAX_NO_SPEECH_PROBABILITY
                or log_probability < MIN_AVERAGE_LOG_PROBABILITY
                or compression > MAX_COMPRESSION_RATIO):
            if strict and str(segment.get("text", "")).strip():
                uncertain()
            continue
        text = str(segment.get('text', '')).strip()
        if text:
            accepted.append(text)
    if not accepted:
        raise ValueError('No reliable speech recognized; check the microphone and try again')
    return ' '.join(accepted)


@lru_cache(maxsize=1)
def load_model(model_path):
    """Keep the CPU model resident for the lifetime of the recognition worker."""
    import whisper
    return whisper.load_model(model_path, device='cpu')


def configured_model_path():
    path = Path(os.environ.get('NATOCHECK_WHISPER_MODEL', str(Path.home() / '.cache/whisper/base.pt'))).expanduser()
    if not path.is_file():
        raise ValueError('Local Whisper base model is missing; no automatic download is performed')
    return str(path)


def serve_worker():
    """Preload once and exchange private job metadata over local pipes."""
    try:
        with redirect_stdout(sys.stderr):
            load_model(configured_model_path())
    except Exception as error:
        print(f'Model preload failed: {error}', file=sys.stderr)
    for line in sys.stdin:
        try:
            job = json.loads(line)
            with redirect_stdout(sys.stderr):
                transcribe(Path(job['source']), job['language'], Path(job['output']), strict=True)
            result = {'ok': True}
        except UncertainSpeechError as error:
            result = {'ok': False, 'review_text': error.text, 'error': str(error)}
        except Exception as error:
            result = {'ok': False, 'error': str(error)}
        print(json.dumps(result), flush=True)


def validate_recording(source, wav_path):
    """Inspect and boundedly decode untrusted audio before speech recognition."""
    if not 0 < source.stat().st_size <= MAX_UPLOAD_BYTES:
        raise ValueError('Recording exceeds the 2 MB upload limit or is empty')
    if source.suffix not in INPUT_FORMATS:
        raise ValueError('Unsupported recording container')
    demuxer, codecs = INPUT_FORMATS[source.suffix]
    input_args = ['-protocol_whitelist', 'file,pipe', '-f', demuxer, '-i', str(source)]
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', *input_args, '-show_entries',
         'format=duration:stream=codec_type,codec_name,channels,sample_rate', '-of', 'json'],
        capture_output=True, text=True, timeout=20)
    if probe.returncode or probe.stderr.strip():
        raise ValueError('Invalid or unsupported audio recording')
    metadata = json.loads(probe.stdout)
    streams = metadata.get('streams', [])
    if (len(streams) != 1 or streams[0].get('codec_type') != 'audio'
            or streams[0].get('codec_name') not in codecs
            or int(streams[0].get('channels', 0)) not in (1, 2)
            or not 8000 <= int(streams[0].get('sample_rate', 0)) <= 96000):
        raise ValueError('Recording must contain one supported mono or stereo audio stream')
    duration = metadata.get('format', {}).get('duration')
    if duration is not None and (not math.isfinite(float(duration))
            or not 0 < float(duration) <= MAX_DECODED_SECONDS):
        raise ValueError('Recording exceeds the 60-second limit or has invalid duration')
    conversion = subprocess.run(
        ['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-err_detect', 'explode', '-y',
         *input_args, '-t', str(MAX_DECODED_SECONDS + 1), '-map', '0:a:0',
         '-vn', '-ac', '1', '-af', 'aresample=16000,asetpts=N/SR/TB',
         '-ar', '16000', '-c:a', 'pcm_s16le', str(wav_path)],
        capture_output=True, text=True, timeout=30)
    if conversion.returncode or conversion.stderr.strip():
        LOG.warning('audio_decode_failed container=%s bytes=%s exit=%s detail=%s',
                    source.suffix, source.stat().st_size, conversion.returncode,
                    conversion.stderr.strip()[-2000:])
        raise ValueError('Recording is damaged or could not be decoded')
    with wave.open(str(wav_path), 'rb') as wav:
        if not 0 < wav.getnframes() / wav.getframerate() <= MAX_DECODED_SECONDS:
            raise ValueError('Recording exceeds the 60-second limit or is empty')
        samples = array('h', wav.readframes(wav.getnframes()))
    if not samples or math.sqrt(sum(s*s for s in samples)/len(samples)) < 80:
        raise ValueError('The recording is silent or too quiet; check the microphone')


def transcribe(source, language, output, strict=False):
    if language not in ('de', 'en'):
        raise ValueError('Only German and English are supported')
    wav_path = output.with_suffix('.wav')
    validate_recording(source, wav_path)
    model_path = configured_model_path()
    model = load_model(model_path)
    result = model.transcribe(
        str(wav_path), language=language, fp16=False, temperature=0, beam_size=5,
        initial_prompt="NATO phonetic alphabet: " + ", ".join(ALPHABET.values()) + ".",
        condition_on_previous_text=False,
        no_speech_threshold=MAX_NO_SPEECH_PROBABILITY,
        logprob_threshold=MIN_AVERAGE_LOG_PROBABILITY,
        compression_ratio_threshold=MAX_COMPRESSION_RATIO,
    )
    text = recognized_text(result, strict=strict)
    output.write_text(text + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', choices=('de', 'en'), default='de')
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        transcribe(args.input, args.language, args.output, strict=args.strict)
    except Exception as error:
        print(f'Transcription failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    if sys.argv[1:] == ['--worker']:
        serve_worker()
    else:
        raise SystemExit(main())
