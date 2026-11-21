#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
local_python="${NATOCHECK_PYTHON:-../../xvx-venv/bin/python}"
[[ -x "$local_python" ]] || { echo "Set NATOCHECK_PYTHON to the existing Python environment." >&2; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo 'Clean local checkout required.' >&2; exit 1; }
tts_script="${NATOCHECK_TTS_SCRIPT:-../../skills-available/tts/speak.py}"
[[ -f "$tts_script" ]] || { echo 'Existing XvX TTS skill required; set NATOCHECK_TTS_SCRIPT.' >&2; exit 1; }
command -v ffmpeg >/dev/null
[[ -x /usr/bin/chromium ]] || { echo 'Existing Chromium required for MediaRecorder acceptance.' >&2; exit 1; }
"$local_python" -c 'import playwright.sync_api'
command -v espeak-ng >/dev/null || command -v espeak >/dev/null
git fetch origin main
release_sha="$(git rev-parse HEAD)"
[[ "$release_sha" == "$(git rev-parse origin/main)" ]] || { echo 'Push and review origin/main before deploying.' >&2; exit 1; }
training_upload=''
ssh_target="${NATOCHECK_SSH_TARGET:-root@ai}"
if [[ -n "${NATOCHECK_TRAINING_VIDEO:-}" ]]; then
    "$local_python" - "$NATOCHECK_TRAINING_VIDEO" <<'CHECK_MEDIA'
import hashlib, json, pathlib, sys
manifest = json.loads(pathlib.Path('training-video.json').read_text())
source = pathlib.Path(sys.argv[1])
with source.open('rb') as media:
    checksum = hashlib.file_digest(media, 'sha256').hexdigest()
assert source.stat().st_size == manifest['bytes'] and checksum == manifest['sha256'], 'Training media does not match the release manifest'
CHECK_MEDIA
    training_upload="$(ssh -o BatchMode=yes -o ConnectTimeout=15 "$ssh_target" 'mktemp /tmp/natocheck-training.XXXXXXXX.mp4')"
    [[ "$training_upload" =~ ^/tmp/natocheck-training\.[A-Za-z0-9]{8}\.mp4$ ]]
    trap 'ssh -o BatchMode=yes -o ConnectTimeout=15 "$ssh_target" "rm -f -- $training_upload"' EXIT
    scp -q "$NATOCHECK_TRAINING_VIDEO" "$ssh_target:$training_upload"
fi
# SSH joins arguments into a remote shell command; preserve optional positions.
ssh -o BatchMode=yes -o ConnectTimeout=15 "$ssh_target" bash -s -- "$release_sha" "${NATOCHECK_DEPENDENCIES_READY:--}" "${training_upload:--}" <<'REMOTE'
set -euo pipefail
cd /var/www/natocheck
release_sha="$1"
dependencies_ready="${2:-}"
training_upload="${3:-}"
[[ "$training_upload" != '-' ]] || training_upload=''
exec 9>.git/deploy.lock
flock -n 9 || { echo 'Another deployment is running.' >&2; exit 1; }
[[ "$(git branch --show-current)" == main ]]
[[ -z "$(git status --porcelain)" ]] || { echo 'Preserve and reconcile server changes first.' >&2; exit 1; }
git fetch origin main
[[ "$(git rev-parse origin/main)" == "$release_sha" ]] || { echo 'Remote release changed.' >&2; exit 1; }
previous_sha="$(git rev-parse HEAD)"
apache_changed=false
apache_config=/etc/apache2/sites-available/natocheck.eventhacker.de.conf
if ! git diff --quiet "$previous_sha" "$release_sha" -- deploy/natocheck.eventhacker.de.conf; then
    cmp --silent deploy/natocheck.eventhacker.de.conf "$apache_config" || {
        echo 'Preserve and reconcile untracked Apache configuration changes first.' >&2; exit 1;
    }
    apache2ctl configtest
    apache_changed=true
fi
git merge-base --is-ancestor HEAD "$release_sha"
if ! git diff --quiet "$previous_sha" "$release_sha" -- requirements.txt; then
    [[ "$dependencies_ready" == "$release_sha" ]] || { echo 'Install reviewed dependencies explicitly and set NATOCHECK_DEPENDENCIES_READY to the release SHA.' >&2; exit 1; }
fi
test -x /home/magnetix/projects/xvx/xvx-venv/bin/python
systemctl cat natocheck >/dev/null
printf '%s previous=%s target=%s status=started\n' "$(date -u +%FT%TZ)" "$previous_sha" "$release_sha" >> .git/deploy.log
trap 'printf "%s target=%s status=failed\n" "$(date -u +%FT%TZ)" "$release_sha" >> .git/deploy.log' ERR
git merge --ff-only "$release_sha"
/home/magnetix/projects/xvx/xvx-venv/bin/python -m unittest discover -v
# Install only verified runtime media; application source comes from Git above.
/home/magnetix/projects/xvx/xvx-venv/bin/python - "$training_upload" <<'INSTALL_MEDIA'
import grp, hashlib, json, os, pathlib, shutil, sys
manifest = json.loads(pathlib.Path('training-video.json').read_text())
folder = pathlib.Path('/var/lib/natocheck/recordings/training')
target = folder / (manifest['sha256'] + '.mp4')
def verify(path):
    with path.open('rb') as source:
        checksum = hashlib.file_digest(source, 'sha256').hexdigest()
    assert path.stat().st_size == manifest['bytes'] and checksum == manifest['sha256'], 'Training media checksum mismatch'
if target.exists():
    verify(target)
else:
    assert sys.argv[1], 'Provide the verified AgentUp readback with NATOCHECK_TRAINING_VIDEO'
    source = pathlib.Path(sys.argv[1])
    verify(source)
    folder.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(folder, 0, grp.getgrnam('natocheck').gr_gid)
    temporary = target.with_suffix('.tmp')
    shutil.copyfile(source, temporary)
    os.chmod(temporary, 0o640)
    os.chown(temporary, 0, grp.getgrnam('natocheck').gr_gid)
    verify(temporary)
    temporary.replace(target)
print('Pinned training media verified')
INSTALL_MEDIA
if [[ "$apache_changed" == true ]]; then
    # Execute as the already authorized root release operator.
    apache_backup=".git/apache-${previous_sha}.conf"
    cp -p "$apache_config" "$apache_backup"
    install -m 0644 deploy/natocheck.eventhacker.de.conf "$apache_config"
    if ! apache2ctl configtest; then
        cp -p "$apache_backup" "$apache_config"
        echo 'Apache validation failed; previous configuration restored.' >&2
        exit 1
    fi
    systemctl reload apache2
fi
systemctl restart natocheck
systemctl is-active --quiet natocheck
[[ -z "$(git status --porcelain)" ]]
printf '%s previous=%s target=%s status=restarted\n' "$(date -u +%FT%TZ)" "$previous_sha" "$release_sha" >> .git/deploy.log
REMOTE
verify_args=()
if [[ -n "${NATOCHECK_VERIFY_IP:-}" ]]; then
    verify_args=(--resolve "natocheck.eventhacker.de:443:${NATOCHECK_VERIFY_IP}")
fi
curl "${verify_args[@]}" --fail --silent --show-error --retry 3 --retry-delay 1 https://natocheck.eventhacker.de/ | grep -q 'NatoCheck'
curl "${verify_args[@]}" --fail --silent --show-error -H 'Content-Type: application/json' --data '{"mode":"letter"}' https://natocheck.eventhacker.de/api/trainer/task | "$local_python" -c 'import json,sys; task=json.load(sys.stdin); assert len(task["prompt"]) == 1 and task["id"]'
if "$local_python" scripts/check-live-speech.py --tts-script "$tts_script"; then
    live_status=live_verified
else
    live_status=live_failed
fi
ssh -o BatchMode=yes -o ConnectTimeout=15 "${NATOCHECK_SSH_TARGET:-root@ai}" bash -s -- "$release_sha" "$live_status" <<'LIVE_STATUS'
set -euo pipefail
cd /var/www/natocheck
[[ "$(git rev-parse HEAD)" == "$1" ]] || { echo 'Live release changed during acceptance.' >&2; exit 1; }
printf '%s target=%s status=%s\n' "$(date -u +%FT%TZ)" "$1" "$2" >> .git/deploy.log
LIVE_STATUS
[[ "$live_status" == live_verified ]] || { echo 'Deployment is not verified: live speech check failed.' >&2; exit 1; }
echo "HTTPS, exercise and live English speech checks passed: $release_sha"
