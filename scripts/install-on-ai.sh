#!/usr/bin/env bash
# Execute through the already authorized root account on the existing host.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -z "$(git status --porcelain)" ]] || { echo 'Clean local checkout required.' >&2; exit 1; }
git fetch origin main
release_sha="$(git rev-parse HEAD)"
[[ "$release_sha" == "$(git rev-parse origin/main)" ]] || { echo 'Push the reviewed release first.' >&2; exit 1; }
ssh -o BatchMode=yes -o ConnectTimeout=15 root@ai bash -s -- "$release_sha" <<'REMOTE'
set -euo pipefail
release_sha="$1"
test ! -e /var/www/natocheck || { echo 'NatoCheck already exists; use the release workflow.' >&2; exit 1; }
test ! -e /etc/apache2/sites-available/natocheck.eventhacker.de.conf
runtime=/home/magnetix/projects/xvx/xvx-venv/bin/python
test -x "$runtime"
test -f /root/.cache/whisper/base.pt
"$runtime" -c 'import whisper; assert whisper.__version__ == "20250625"'
command -v ffmpeg >/dev/null
command -v certbot >/dev/null
git clone --branch main --single-branch https://github.com/magnetix-cgn/natocheck.git /var/www/natocheck
cd /var/www/natocheck
[[ "$(git rev-parse HEAD)" == "$release_sha" ]] || { echo 'Remote release changed.' >&2; exit 1; }
"$runtime" -m unittest discover -v
if ! id natocheck >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/natocheck --shell /usr/sbin/nologin natocheck
fi
install -d -o natocheck -g natocheck -m 0700 /var/lib/natocheck /var/lib/natocheck/models
install -o natocheck -g natocheck -m 0440 /root/.cache/whisper/base.pt /var/lib/natocheck/models/base.pt
install -m 0644 deploy/natocheck.service /etc/systemd/system/natocheck.service
install -m 0644 deploy/natocheck-http.conf /etc/apache2/sites-available/natocheck.eventhacker.de.conf
a2ensite natocheck.eventhacker.de.conf
apache2ctl configtest
systemctl reload apache2
systemctl daemon-reload
systemctl enable --now natocheck
systemctl is-active --quiet natocheck
certbot certonly --apache --non-interactive --cert-name natocheck.eventhacker.de -d natocheck.eventhacker.de
install -m 0644 deploy/natocheck.eventhacker.de.conf /etc/apache2/sites-available/natocheck.eventhacker.de.conf
apache2ctl configtest
systemctl reload apache2
printf '%s target=%s status=initial-install-completed\n' "$(date -u +%FT%TZ)" "$release_sha" >> .git/deploy.log
[[ -z "$(git status --porcelain)" ]]
echo "Initial service and HTTPS installation completed: $release_sha"
REMOTE
