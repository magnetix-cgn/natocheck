"""Normalize browser recordings and transcribe with the existing local Whisper skill."""
import argparse
from array import array
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import wave


MAX_NO_SPEECH_PROBABILITY = 0.6
MIN_AVERAGE_LOG_PROBABILITY = -1.0
MAX_COMPRESSION_RATIO = 2.4


def recognized_text(result, strict=False):
    """Discard uncertain, non-speech and repetitive decoding segments."""
    accepted = []
    for segment in result.get('segments', []):
        metrics = [segment.get('no_speech_prob'), segment.get('avg_logprob'),
                   segment.get('compression_ratio')]
        if any(not isinstance(value, (int, float)) or not math.isfinite(value)
               for value in metrics):
            if strict:
                raise ValueError("Uncertain speech segment; please record again")
            continue
        no_speech, log_probability, compression = metrics
        if (no_speech >= MAX_NO_SPEECH_PROBABILITY
                or log_probability < MIN_AVERAGE_LOG_PROBABILITY
                or compression > MAX_COMPRESSION_RATIO):
            if strict and str(segment.get("text", "")).strip():
                raise ValueError("Uncertain speech segment; please record again")
            continue
        text = str(segment.get('text', '')).strip()
        if text:
            accepted.append(text)
    if not accepted:
        raise ValueError('No reliable speech recognized; check the microphone and try again')
    return ' '.join(accepted)


def transcribe(source, language, output, strict=False):
    if language not in ('de', 'en'):
        raise ValueError('Only German and English are supported')
    model_path = Path(os.environ.get('NATOCHECK_WHISPER_MODEL', str(Path.home() / '.cache/whisper/base.pt'))).expanduser()
    if not model_path.is_file():
        raise ValueError('Local Whisper base model is missing; no automatic download is performed')
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'json', str(source)], capture_output=True, text=True, timeout=20)
    if probe.returncode:
        raise ValueError('Invalid or unsupported audio recording')
    duration = json.loads(probe.stdout).get('format', {}).get('duration')
    if duration is not None and (not math.isfinite(float(duration)) or float(duration) > 65):
        raise ValueError('Recording exceeds the 60-second limit')
    wav_path = output.with_suffix('.wav')
    conversion = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(source),
                                '-t', '65', '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le',
                                str(wav_path)], capture_output=True, text=True, timeout=30)
    if conversion.returncode:
        raise ValueError('Recording could not be converted to WAV')
    with wave.open(str(wav_path), 'rb') as wav:
        samples = array('h', wav.readframes(wav.getnframes()))
    if not samples or math.sqrt(sum(s*s for s in samples)/len(samples)) < 80:
        raise ValueError('The recording is silent or too quiet; check the microphone')
    import whisper
    model = whisper.load_model(str(model_path), device='cpu')
    result = model.transcribe(
        str(wav_path), language=language, fp16=False, temperature=0,
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
    raise SystemExit(main())
