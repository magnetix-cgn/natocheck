#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
local_python="${NATOCHECK_PYTHON:-../../xvx-venv/bin/python}"
[[ -x "$local_python" ]] || { echo "Set NATOCHECK_PYTHON to the existing Python environment." >&2; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo 'Clean local checkout required.' >&2; exit 1; }
git fetch origin main
release_sha="$(git rev-parse HEAD)"
[[ "$release_sha" == "$(git rev-parse origin/main)" ]] || { echo 'Push and review origin/main before deploying.' >&2; exit 1; }
ssh -o BatchMode=yes -o ConnectTimeout=15 "${NATOCHECK_SSH_TARGET:-root@ai}" bash -s -- "$release_sha" "${NATOCHECK_DEPENDENCIES_READY:-}" <<'REMOTE'
set -euo pipefail
cd /var/www/natocheck
release_sha="$1"
dependencies_ready="${2:-}"
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
printf '%s previous=%s target=%s status=completed\n' "$(date -u +%FT%TZ)" "$previous_sha" "$release_sha" >> .git/deploy.log
REMOTE
verify_args=()
if [[ -n "${NATOCHECK_VERIFY_IP:-}" ]]; then
    verify_args=(--resolve "natocheck.eventhacker.de:443:${NATOCHECK_VERIFY_IP}")
fi
curl "${verify_args[@]}" --fail --silent --show-error --retry 3 --retry-delay 1 https://natocheck.eventhacker.de/ | grep -q 'NatoCheck'
curl "${verify_args[@]}" --fail --silent --show-error -H 'Content-Type: application/json' --data '{"mode":"letter"}' https://natocheck.eventhacker.de/api/trainer/task | "$local_python" -c 'import json,sys; task=json.load(sys.stdin); assert len(task["prompt"]) == 1 and task["id"]'
echo "HTTPS and exercise checks passed: $release_sha"
