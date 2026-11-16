#!/usr/bin/env bash
# execute as root inside a new Debian guest; never run this on the Xen host.
set -Eeuo pipefail
export LANG=C.UTF-8 LC_ALL=C.UTF-8

apply=false
domain=''
model=''
wheelhouse=''
email=''
threads=2
workspace=/opt/xvx
repo_url=https://github.com/magnetix-cgn/natocheck.git
source_dir="$(cd "$(dirname "$0")/.." && pwd)"
log() { printf '[natocheck-bootstrap] %s\n' "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }
usage() {
    cat <<'EOF'
Usage: bash scripts/bootstrap-debian.sh [options]

Default: print a plan without changing the system or accessing the network.
  --apply                  Install on a fresh Debian 13 amd64 guest (root required)
  --domain HOST            Public hostname, approved by the central whitelist
  --model FILE             Existing Whisper base.pt; its official checksum is checked
  --email ADDRESS          Certificate registration email
  --threads N              Whisper CPU threads (default: 2; cannot exceed vCPUs)
  --wheelhouse DIRECTORY   Install Python packages offline instead of using PyPI
  --help                   Show this help

Fixed target paths: /opt/xvx/xvx-venv, /opt/xvx/externals/natocheck,
/var/lib/natocheck, /etc/systemd/system/natocheck.service.
Existing application/runtime/service/vhost paths are refused. SSH, firewall,
DNS, disks and the Xen hypervisor are not reconfigured.
EOF
}
while (($#)); do
    case "$1" in
        --apply) apply=true; shift ;;
        --domain|--model|--email|--threads|--wheelhouse)
            (($# >= 2)) || die "Missing value for $1"
            case "$1" in
                --domain) domain="$2" ;;
                --model) model="$2" ;;
                --email) email="$2" ;;
                --threads) threads="$2" ;;
                --wheelhouse) wheelhouse="$2" ;;
            esac
            shift 2 ;;
        --help) usage; exit 0 ;;
        *) die "Unknown option: $1" ;;
    esac
done
[[ "$threads" =~ ^[1-9][0-9]*$ ]] || die 'Threads must be a positive integer.'
log "Plan: Debian 13 amd64 guest, domain=${domain:-NOT_SET}, CPU threads=$threads"
log "Install FFmpeg, Apache, Certbot, Python build tools and XvX runtime at $workspace/xvx-venv."
log "Install committed NatoCheck source, checked Whisper model, isolated systemd service and HTTPS."
if [[ -n "$wheelhouse" ]]; then
    log "Python package source: local wheelhouse $wheelhouse"
else
    log 'Python package source: PyPI (requires central approval for pypi.org and files.pythonhosted.org).'
fi
$apply || { log 'Plan only. Add --apply and supply --domain, --model and --email to install.'; exit 0; }
[[ $EUID -eq 0 ]] || die 'Run as root inside the Debian guest.'
[[ "$domain" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ && "$domain" == *.* && "$domain" != *..* ]] || die 'Supply a lowercase DNS hostname, without a scheme or path.'
[[ "$email" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || die 'Supply a certificate registration email.'
[[ -f "$model" && ! -L "$model" ]] || die 'Supply an existing regular Whisper base model file.'
[[ -z "$wheelhouse" || -d "$wheelhouse" ]] || die 'Wheelhouse directory does not exist.'
for tool in curl git python3 sha256sum systemctl; do command -v "$tool" >/dev/null || die "Install prerequisite: $tool"; done
# shellcheck disable=SC1091
source /etc/os-release
[[ "$ID" == debian && "$VERSION_ID" == 13 ]] || die 'This installer targets Debian 13 only.'
[[ "$(dpkg --print-architecture)" == amd64 ]] || die 'This installer targets amd64 only.'
[[ "$threads" -le "$(nproc)" ]] || die 'Thread count exceeds available vCPUs.'
[[ -d /run/systemd/system ]] || die 'A booted systemd guest is required.'
[[ "$(awk '/MemTotal:/ {print $2}' /proc/meminfo)" -ge 3500000 ]] || die 'At least 4 GB RAM is required.'
[[ "$(df -Pk /opt | awk 'NR==2 {print $4}')" -ge 20000000 ]] || die 'At least 20 GB free space on /opt is required.'
for path in "$workspace/xvx-venv" "$workspace/externals/natocheck" /var/lib/natocheck /etc/systemd/system/natocheck.service /etc/apache2/sites-available/natocheck.conf; do
    [[ ! -e "$path" && ! -L "$path" ]] || die "Existing path must be reviewed first: $path"
done
! id natocheck >/dev/null 2>&1 || die 'Existing natocheck account must be reviewed first.'
[[ -z "$(git -C "$source_dir" status --porcelain)" ]] || die 'Run from a clean committed release checkout.'
release="$(git -C "$source_dir" rev-parse HEAD)"
work="$(mktemp -d)"
trap 'rm -f "$work/rules.html" "$work/domains.json"; rmdir "$work"' EXIT
trap 'log "Installation failed at line $LINENO. Existing completed steps are preserved; inspect before retrying." >&2' ERR
curl --proto '=https' --tlsv1.2 --fail --silent --show-error https://htki.de/rules/ -o "$work/rules.html"
[[ -s "$work/rules.html" ]] || die 'HOLD: canonical rules could not be checked.'
log 'Review the current canonical instructions at https://htki.de/rules/ before installation.'
curl --proto '=https' --tlsv1.2 --fail --silent --show-error https://htki.de/rules/domain-whitelist.json -o "$work/domains.json"
python3 - "$work/domains.json" "$domain" "$wheelhouse" <<'PY'
import json, sys
entries = json.load(open(sys.argv[1], encoding='utf-8'))['domains']
domains = [sys.argv[2], 'github.com', 'deb.debian.org', 'security.debian.org', 'acme-v02.api.letsencrypt.org']
if not sys.argv[3]:
    domains += ['pypi.org', 'files.pythonhosted.org']
for domain in domains:
    if not any(domain == e['domain'] or (e.get('include_subdomains') and domain.endswith('.' + e['domain'])) for e in entries):
        raise SystemExit(f'HOLD: domain is not approved by the central whitelist: {domain}')
PY
# Debian repositories are the only permitted APT sources for this installer.
python3 - <<'PY'
from pathlib import Path
from urllib.parse import urlsplit
import re
paths = [Path('/etc/apt/sources.list'), *Path('/etc/apt/sources.list.d').glob('*.list'), *Path('/etc/apt/sources.list.d').glob('*.sources')]
for path in paths:
    if not path.exists():
        continue
    text = '\n'.join(line.split('#', 1)[0] for line in path.read_text().splitlines())
    for url in re.findall(r'https?://[^\s]+', text):
        host = urlsplit(url).hostname or ''
        if host != 'debian.org' and not host.endswith('.debian.org'):
            raise SystemExit(f'HOLD: review non-Debian APT source in {path}')
PY
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git joe openssh-server \
    python3 python3-venv python3-dev build-essential ffmpeg apache2 certbot python3-certbot-apache
install -d -m 0755 "$workspace/externals"
python3 -m venv "$workspace/xvx-venv"
python="$workspace/xvx-venv/bin/python"
if [[ -n "$wheelhouse" ]]; then
    PIP_CONFIG_FILE=/dev/null "$python" -m pip --isolated install --no-index --find-links "$wheelhouse" 'torch==2.8.0' -r "$source_dir/requirements.txt"
else
    PIP_CONFIG_FILE=/dev/null "$python" -m pip --isolated install --index-url https://pypi.org/simple 'torch==2.8.0' -r "$source_dir/requirements.txt"
fi
"$python" -m pip check
model_sha="$("$python" -c 'import whisper; print(whisper._MODELS["base"].split("/")[-2])')"
[[ "$(sha256sum "$model" | cut -d' ' -f1)" == "$model_sha" ]] || die 'Whisper base model checksum mismatch.'
git clone --no-local "$source_dir" "$workspace/externals/natocheck"
git -C "$workspace/externals/natocheck" remote set-url origin "$repo_url"
[[ "$(git -C "$workspace/externals/natocheck" rev-parse HEAD)" == "$release" ]] || die 'Cloned release mismatch.'
(cd "$workspace/externals/natocheck" && "$python" -m unittest discover -v)
useradd --system --user-group --home-dir /var/lib/natocheck --shell /usr/sbin/nologin natocheck
install -d -o natocheck -g natocheck -m 0700 /var/lib/natocheck /var/lib/natocheck/models
install -o natocheck -g natocheck -m 0440 "$model" /var/lib/natocheck/models/base.pt
sed -e "s|/home/magnetix/projects/xvx/xvx-venv|$workspace/xvx-venv|g" \
    -e "s|/var/www/natocheck|$workspace/externals/natocheck|g" \
    -e "s|NATOCHECK_ALLOWED_HOSTS=natocheck.eventhacker.de|NATOCHECK_ALLOWED_HOSTS=$domain|" \
    -e "s|OMP_NUM_THREADS=2|OMP_NUM_THREADS=$threads|" \
    "$source_dir/deploy/natocheck.service" > /etc/systemd/system/natocheck.service
install -d -m 0755 /var/www/letsencrypt/.well-known/acme-challenge
a2enmod proxy proxy_http headers ssl
sed "s/natocheck.eventhacker.de/$domain/g" "$source_dir/deploy/natocheck-http.conf" > /etc/apache2/sites-available/natocheck.conf
a2ensite natocheck.conf
apache2ctl configtest
systemctl enable --now apache2
systemctl reload apache2
systemctl daemon-reload
systemctl enable --now natocheck
curl --fail --silent --show-error --retry 10 --retry-connrefused --retry-delay 1 http://127.0.0.1:8767/ >/dev/null
certbot certonly --webroot -w /var/www/letsencrypt --non-interactive --agree-tos \
    --email "$email" --cert-name "$domain" -d "$domain" \
    --server https://acme-v02.api.letsencrypt.org/directory
sed "s/natocheck.eventhacker.de/$domain/g" "$source_dir/deploy/natocheck.eventhacker.de.conf" > /etc/apache2/sites-available/natocheck.conf
apache2ctl configtest
systemctl reload apache2
install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\napache2ctl configtest && systemctl reload apache2\n' > /etc/letsencrypt/renewal-hooks/deploy/natocheck-reload
chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/natocheck-reload
systemctl enable --now certbot.timer
curl --fail --silent --show-error "https://$domain/" >/dev/null
curl --fail --silent --show-error -H 'Content-Type: application/json' --data '{"mode":"challenge"}' "https://$domain/api/trainer/task" \
    | "$python" -c 'import json,sys; task=json.load(sys.stdin); assert len(task["prompt"]) == 10 and task["id"]'
printf '%s target=%s status=guest-install-completed\n' "$(date -u +%FT%TZ)" "$release" >> "$workspace/externals/natocheck/.git/deploy.log"
log "Installed release $release at https://$domain/"
log 'Next: test one spoken challenge in Chromium and review the recognition time.'
