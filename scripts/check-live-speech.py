"""Verify live English speech generation, upload, recognition and scoring."""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from recording import MAX_UPLOAD_BYTES, validate_recording

URL = 'https://natocheck.eventhacker.de'
LEAD_IN_MS = 500


def request(path, payload=None, audio=None):
    command = ['curl', '--fail-with-body', '--silent', '--show-error', '--max-time', '30']
    if os.environ.get('NATOCHECK_VERIFY_IP'):
        command += ['--resolve', 'natocheck.eventhacker.de:443:' + os.environ['NATOCHECK_VERIFY_IP']]
    if audio:
        command += ['-H', 'Content-Type: ' + ('audio/mp4' if audio.suffix == '.m4a' else 'audio/webm'), '--data-binary', '@' + str(audio)]
    elif payload is not None:
        command += ['-H', 'Content-Type: application/json', '--data-binary', json.dumps(payload)]
    result = subprocess.run(command + [URL + path], capture_output=True, text=True, timeout=35)
    if result.returncode:
        raise RuntimeError('Live request failed: ' + result.stderr.strip() + ' ' + result.stdout[:300])
    return json.loads(result.stdout)


def record_browser_audio(wav, target):
    """Exercise actual MediaRecorder chunk timestamps instead of a clean FFmpeg mux."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path='/usr/bin/chromium', headless=True,
            args=['--no-sandbox', '--autoplay-policy=no-user-gesture-required'])
        try:
            page = browser.new_page()
            encoded = page.evaluate("""async ({encoded, leadInSeconds}) => {
                const context = new AudioContext();
                await context.resume();
                const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
                const buffer = await context.decodeAudioData(bytes.buffer);
                const source = context.createBufferSource();
                source.buffer = buffer;
                const destination = context.createMediaStreamDestination();
                source.connect(destination);
                const recorder = new MediaRecorder(destination.stream,
                    {mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: 128000});
                const chunks = [];
                const finished = new Promise((resolve, reject) => {
                    recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
                    recorder.onerror = reject;
                    recorder.onstop = async () => {
                        const data = new Uint8Array(await new Blob(chunks).arrayBuffer());
                        let binary = '';
                        for (const byte of data) binary += String.fromCharCode(byte);
                        resolve(btoa(binary));
                    };
                });
                recorder.start(1000);
                source.onended = () => recorder.stop();
                source.start(context.currentTime + leadInSeconds);
                const result = await finished;
                destination.stream.getTracks().forEach(track => track.stop());
                await context.close();
                return result;
            }""", {'encoded': base64.b64encode(wav.read_bytes()).decode('ascii'),
                    'leadInSeconds': LEAD_IN_MS / 1000})
            target.write_bytes(base64.b64decode(encoded))
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tts-script', type=Path, default=BASE.parents[1] / 'skills-available/tts/speak.py')
    args = parser.parse_args()
    tts_script = args.tts_script.resolve()
    if not tts_script.is_file():
        parser.error('Set --tts-script to the existing XvX TTS skill; speech checks are mandatory')
    output = tts_script.parent / 'out.user.magnetics'
    output.mkdir(parents=True, exist_ok=True)
    name = 'natocheck_live_' + uuid.uuid4().hex
    wav = output / (name + '.wav')
    webm = output / (name + '.webm')
    decoded = output / (name + '_decoded.wav')
    report = {'started': datetime.now(timezone.utc).isoformat(), 'url': URL, 'language': 'en',
              'lead_in_ms': LEAD_IN_MS, 'passed': False}
    try:
        task = request('/api/trainer/task', {'mode': 'sequence'})
        alphabet = request('/api/trainer/alphabet')
        words = [alphabet[letter] for letter in task['prompt']]
        report.update(prompt=task['prompt'], expected=words)
        subprocess.run([sys.executable, str(tts_script), '--language', 'en', '--speed', '135',
                        '--text', ', '.join(words) + '.', '--name', name], check=True, timeout=60)
        report['formats'] = []
        for suffix, encoding in (
                ('.webm', ['-c:a', 'libopus', '-b:a', '128k']),
                ('.m4a', ['-c:a', 'aac', '-b:a', '128k', '-movflags',
                          'frag_keyframe+empty_moov+default_base_moof', '-frag_duration', '1000000'])):
            webm = output / (name + suffix)
            if suffix == '.webm':
                record_browser_audio(wav, webm)
            else:
                subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(wav),
                                '-af', f'adelay={LEAD_IN_MS}:all=1',
                                *encoding, str(webm)], check=True, timeout=30)
            validate_recording(webm, decoded)
            format_result = {'format': suffix, 'upload_bytes': webm.stat().st_size}
            report['formats'].append(format_result)
            if not 0 < format_result['upload_bytes'] <= MAX_UPLOAD_BYTES:
                raise RuntimeError('Generated recording violates the upload limit')
            job = request('/api/transcribe', audio=webm)
            deadline = time.monotonic() + 330
            next_progress = time.monotonic() + 15
            while time.monotonic() < deadline:
                job = request('/api/transcriptions/' + job['id'])
                if job['state'] != 'busy':
                    break
                if time.monotonic() >= next_progress:
                    print('Waiting for live English recognition ...', flush=True)
                    next_progress = time.monotonic() + 15
                time.sleep(1)
            if job['state'] != 'done':
                raise RuntimeError('Live recognition failed: ' + job.get('error', 'timeout'))
            format_result['transcript'] = job['text']
            format_result['recognition_seconds'] = job.get('elapsed_seconds')
            result = request('/api/trainer/check', {'task_id': task['id'], 'text': job['text'], 'source': 'synthetic'})
            format_result['result'] = result
            if not result['passed'] or result['score'] != 100:
                raise RuntimeError('Live speech comparison failed: ' + job['text'])
            print('Live speech format passed: ' + suffix + ' -> ' + job['text'], flush=True)
        report['passed'] = True
        print('Live English speech check passed: ' + task['prompt'] + ' -> ' + job['text'] + ' (100%)', flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report['error'] = str(error)
        print(str(error), file=sys.stderr)
        return 1
    finally:
        decoded.unlink(missing_ok=True)
        report_path = output / (name + '.json')
        report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print('Speech check report: ' + str(report_path), flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
