#!/usr/bin/env bash
# Execute as root after approval of the initial monitoring installation.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "$(id -u)" == 0 ]] || { echo 'An authorized root operator is required.' >&2; exit 1; }
[[ "$PWD" == /var/www/natocheck ]] || { echo 'Use the deployed production checkout.' >&2; exit 1; }
exec 9>.git/deploy.lock
flock -n 9 || { echo 'A deployment is already running.' >&2; exit 1; }
[[ -z "$(git status --porcelain)" ]]
[[ "$(git branch --show-current)" == main ]]
git fetch origin main
[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]]
test -d /var/lib/prometheus/node-exporter
test -d /var/lib/grafana/dashboards/xvx
test -r /var/log/apache2/natocheck-access.log
systemctl is-active --quiet prometheus-node-exporter grafana-server
for target in /etc/systemd/system/natocheck-usage.service /etc/systemd/system/natocheck-usage.timer /var/lib/grafana/dashboards/xvx/natocheck-usage.json /var/lib/prometheus/node-exporter/natocheck_usage.prom; do
    [[ ! -e "$target" ]] || { echo "Initial installation only; preserve existing $target" >&2; exit 1; }
done
systemd-analyze verify deploy/natocheck-usage.service deploy/natocheck-usage.timer
/home/magnetix/projects/xvx/xvx-venv/bin/python -m unittest test_usage -v
# Validate logs before installing anything; no raw request information is printed.
/home/magnetix/projects/xvx/xvx-venv/bin/python scripts/export-usage.py >/dev/null
printf '%s release=%s monitoring=started\n' "$(date -u +%FT%TZ)" "$(git rev-parse HEAD)" >> .git/deploy.log
trap 'echo "Monitoring installation failed; inspect installed files and .git/deploy.log before retrying." >&2' ERR
install -m 0644 deploy/natocheck-usage.service deploy/natocheck-usage.timer /etc/systemd/system/
install -m 0644 deploy/natocheck-usage.json /var/lib/grafana/dashboards/xvx/natocheck-usage.json
systemctl daemon-reload
systemctl start natocheck-usage.service
curl -fsS http://127.0.0.1:9100/metrics | /home/magnetix/projects/xvx/xvx-venv/bin/python -c 'import sys; assert "natocheck_usage_export_timestamp_seconds " in sys.stdin.read(), "Node exporter did not expose usage metrics"'
systemctl enable --now natocheck-usage.timer
printf '%s release=%s monitoring=installed_not_live_verified\n' "$(date -u +%FT%TZ)" "$(git rev-parse HEAD)" >> .git/deploy.log
echo 'Installed. Verify Prometheus samples, Grafana provisioning and public HTTPS before reporting live success.'
