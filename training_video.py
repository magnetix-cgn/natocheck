"""Serve one verified training asset with bounded streaming and byte ranges."""
import json
from pathlib import Path
import re

VIDEO = json.loads((Path(__file__).resolve().parent / 'training-video.json').read_text(encoding='utf-8'))
assert re.fullmatch(r'[a-f0-9]{64}', VIDEO['sha256'])
VIDEO_FILENAME = VIDEO['sha256'] + '.mp4'
VIDEO_URL = '/training/' + VIDEO_FILENAME


def serve_training_video(request, source, *, head=False):
    """Serve only the pinned runtime file, never arbitrary paths or share URLs."""
    try:
        media = source.open('rb')
    except OSError:
        return request.send(503, {'error': 'Training video is temporarily unavailable'})
    with media:
        size = media.seek(0, 2)
        if size != VIDEO['bytes']:
            return request.send(503, {'error': 'Training video is temporarily unavailable'})
        etag = '"' + VIDEO['sha256'] + '"'
        start, end, status = 0, size - 1, 200
        byte_range = request.headers.get('Range') if not head else None
        if request.headers.get('If-Range', etag) != etag:
            byte_range = None
        if byte_range:
            match = re.fullmatch(r'bytes=(\d{0,20})-(\d{0,20})', byte_range)
            valid = match and any(match.groups())
            if valid:
                left, right = match.groups()
                if left:
                    start = int(left)
                    end = min(int(right), size - 1) if right else size - 1
                elif int(right) > 0:
                    start = max(0, size - int(right))
                else:
                    valid = False
                valid = valid and 0 <= start <= end < size
            if not valid:
                request.send_response(416)
                request.send_header('Content-Range', f'bytes */{size}')
                request.send_header('Content-Length', '0')
                request.end_headers()
                return
            status = 206
        request.send_response(status)
        request.send_header('Content-Type', 'video/mp4')
        request.send_header('Content-Length', str(end - start + 1))
        request.send_header('Accept-Ranges', 'bytes')
        request.send_header('ETag', etag)
        request.send_header('Cache-Control', 'public, max-age=31536000, immutable')
        request.send_header('X-Content-Type-Options', 'nosniff')
        if status == 206:
            request.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        request.end_headers()
        if head:
            return
        media.seek(start)
        remaining = end - start + 1
        try:
            while remaining:
                data = media.read(min(256 * 1024, remaining))
                if not data:
                    break
                request.wfile.write(data)
                remaining -= len(data)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            # Browsers cancel a previous range when seeking or closing the player.
            return
