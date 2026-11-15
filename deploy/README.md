# Proposed NatoCheck deployment

Status: templates prepared; initial setup has not been performed or approved.

## Verified discovery

- Selected repository: `https://github.com/magnetix-cgn/natocheck`.
- Selected hostname: `natocheck.eventhacker.de` (allowed by the central whitelist).
- Existing Eventhacker host: SSH alias `ai`; main domain A record `94.130.7.235`.
- No NatoCheck A/AAAA record or `/var/www/natocheck` checkout was found.
- The existing SSH account is `magnetix`, not root. No privileged access is assumed.
- The host has ffmpeg, two CPUs and approximately 8 GB RAM. Python/Whisper
  dependencies, model availability, Apache proxy modules and certificate access
  still need privileged verification. No service or TLS availability is claimed.

## Initial setup requiring approval

Proposed DNS change: add only `A natocheck.eventhacker.de -> 94.130.7.235`.
Do not add an AAAA record without verifying a working IPv6 path. Back up the DNS
RRSet with the hosting skill before changing it.

Recommended layout:

- Checkout: `/var/www/natocheck`, release branch `main`.
- Dedicated non-login service account: `natocheck`.
- Server-only Python environment: `/var/www/natocheck/xvx-venv/`.
  This is a deployment environment on `ai`, not a second XvX workspace environment.
- State: `/var/lib/natocheck`, owned by the service account, mode `0700`.
- Existing/provisioned Whisper base model: `/var/lib/natocheck/models/base.pt`.
  Install an approved model separately; do not download at request time.
- Loopback upstream: `127.0.0.1:8767` behind Apache HTTPS.

An authorized administrator must first verify the proposed paths and port,
Python/ffmpeg compatibility, model and module availability, and repository read
access. Install locked Python requirements into the server environment. Keep
service source read-only to the service account and writable only to the release
operator. Do not reuse or modify another application's environment.

The committed templates are `natocheck.service` and
`natocheck.eventhacker.de.conf`. Install them from the reviewed checkout rather
than editing application code on the server. Root-only operations must be run
by an explicitly authorized operator:

```sh
# execute as root
install -m 0644 deploy/natocheck.service /etc/systemd/system/natocheck.service
```

Stage only the HTTP ACME host until the new certificate exists. Obtain the
certificate through the existing ACME workflow, then enable the committed HTTPS
host. Validate Apache configuration before reload. Install and enable the service
only after its account, paths, environment and model are ready.

The existing SSH account needs a narrowly scoped authorized service restart
mechanism before the release script can run unattended. The script invokes
`systemctl restart natocheck`; it does not assume sudo. An authorized operator
may supply `NATOCHECK_SSH_TARGET` for an account already permitted to perform the
release. Do not change privilege policy or enable root login implicitly.

## Subsequent releases

Develop and verify locally, commit and push to `origin/main`, then run from that
clean release checkout:

```sh
bash scripts/deploy-to-ai.sh
```

The script checks clean local and remote worktrees, exact remote release SHA,
fast-forward history and dependency changes. Dependency changes require an
explicit installation step before deployment. After installing the reviewed
requirements, set `NATOCHECK_DEPENDENCIES_READY` to the exact release SHA to
acknowledge that step. `NATOCHECK_PYTHON` selects an existing local Python; in
the XvX checkout it defaults to `../../xvx-venv/bin/python`. It serializes releases, restarts
the service, records revisions and status, and verifies HTTPS and a live exercise.
It never installs infrastructure, changes DNS, installs dependencies or runs
migrations automatically. Preserve unknown changes; never reset or clean them.

If restart or live validation fails after fast-forward, the new code may already
be checked out. Review `.git/deploy.log` and service logs. Prepare and push a
revert commit locally, then deploy it using the same path. No atomic rollback is
claimed.

## Acceptance

Verify HTTPS at `https://natocheck.eventhacker.de/`, a generated exercise and its
answer comparison, and an actual microphone in Chromium. Check that the browser
permission prompt is shown only after clicking record, Whisper does not consume
the game timer and transient recordings are removed. Send the accurate completion
notification through the localmail skill after live verification.
