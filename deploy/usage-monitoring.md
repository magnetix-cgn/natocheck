# NatoCheck usage monitoring

Status: prepared locally; initial monitoring installation requires approval.

This document covers the proposed Grafana request board. The public facts card
described in the main README instead uses persistent aggregate challenge counters
inside the existing app. It does not infer game totals from requests and does not
install this monitoring service, timer or dashboard.

The proposed board is `NatoCheck Usage` (UID `natocheck-usage`) at
`https://monitor.eventhacker.de/d/natocheck-usage/natocheck-usage`.
It uses the verified existing `prometheus-local` datasource and the existing
node exporter's textfile directory. No database or new Python package is needed.

## Meaning and limits

The exporter reads the existing current and rotated Apache NatoCheck access logs,
including gzip rotations. It publishes aggregate request counts for rolling
one-hour, 24-hour and seven-day windows, grouped by a fixed event and HTTP status
class. Metrics are gauges: do not apply `rate` or `increase` to them.

Successful page loads, exercise generations, answer checks and accepted uploads
are separate events. They do not measure unique visitors, unique completed games,
recognition success or recognition duration. Repeated checks, bots, release
acceptance and other test traffic are included. Aborted browser recordings are
not submitted and cannot be counted. Seven-day values may be incomplete when
less log history is retained. Existing logs permit a current rolling snapshot;
they do not backfill Prometheus history. Charts start after installation.

Only fixed event/status labels and aggregate values are exported. No IP address,
user agent, request body, audio, transcript or task identifier is exported. The
oldest retained request and exporter timestamp expose retention and freshness.
No matching logs or an unreadable/corrupt rotation causes failure before atomic
replacement, preserving the previous metric file. The board hides usage values
after three minutes without a successful export. Malformed lines are skipped
and reported. Log rotation concurrent with a scan can affect a single snapshot;
the next minute rescans available files. Request logs have second resolution.

The oneshot runs as root because the existing Apache logs are protected. Its
filesystem is read-only except for the existing textfile directory. The timer
runs once per minute with a 50-second execution limit; it does not restart the
NatoCheck recognizer. No Python dependencies or existing monitoring configuration
are modified. Grafana's existing file provider imports the new JSON automatically.

## Proposed initial release procedure

Approve this new monitoring installation mechanism before executing it, as required
by https://htki.de/rules/ (Local development and controlled deployment / External
repositories). Commit and push the reviewed changes to this repository's main
branch, then run the existing `scripts/deploy-to-ai.sh` release workflow from the
clean exact release checkout. Its normal live speech acceptance still applies.

After that release, use the existing authorized root SSH release connection:

```sh
# execute as root
ssh root@ai 'cd /var/www/natocheck && bash scripts/install-usage-monitoring.sh'
```

The installer verifies the exact clean main release, serializes with the existing
deployment lock, validates units and usage tests, and refuses existing monitoring
artifacts. It only creates the new service, timer, dashboard and metrics file.
Its log distinguishes installation from live verification. A partial failure
requires inspection; it never deletes or overwrites existing installation files.

Wait for the existing Grafana provider and Prometheus scrape. Verify
`natocheck_usage_export_timestamp_seconds{job="node"}` is recent and successful
request metrics exist in Prometheus. Authenticate through the existing protected
Grafana credentials without printing them and verify dashboard UID, all targets,
panel rendering and absence of query errors. Check public HTTPS. Send the required
completion email through the localmail skill only after verifying the actual
release and board. Never claim historical chart backfill or unique-person usage.

## Rollback

An authorized operator can stop and disable only `natocheck-usage.timer`, stop its
oneshot, and remove only the four newly created files named by the installer.
Reload systemd afterwards. Grafana's existing provider removes the board when its
file disappears. Existing historical Prometheus samples follow normal retention.
Do not remove any shared directory, alter the existing provider or reset source
checkouts. Future changes must use a reviewed, committed release and preserve any
operator changes to monitoring assets.
