# Proposed NatoCheck deployment

Status: initial installation approved by the owner and completed on 15 November
2026. HTTPS, the exercise API and the bilingual contribution links were verified.

## Verified discovery

- Selected repository: `https://github.com/magnetix-cgn/natocheck`.
- Selected hostname: `natocheck.eventhacker.de` (allowed by the central whitelist).
- Existing Eventhacker host: SSH alias `ai`; main domain A record `94.130.7.235`.
- A new NatoCheck A record points to `94.130.7.235`; no AAAA record was added.
- Existing key-based `root@ai` access was verified for the authorized installation.
- The host has ffmpeg, two CPUs and approximately 8 GB RAM. The existing XvX Python 3.13 environment includes Whisper 20250625 and PyTorch,
  is readable by an unprivileged account, and will be reused without modification.
  Apache proxy, SSL and headers modules and an existing Whisper base model were verified.

## Approved initial setup

Installed DNS record: `A natocheck.eventhacker.de -> 94.130.7.235`.
Do not add an AAAA record without verifying a working IPv6 path. Back up the DNS
RRSet with the hosting skill before changing it.

Installed layout:

- Checkout: `/var/www/natocheck`, release branch `main`.
- Dedicated non-login service account: `natocheck`.
- Existing server interpreter: `/home/magnetix/projects/xvx/xvx-venv/bin/python`.
  The service reads this runtime without modifying it; no new environment is created.
- State: `/var/lib/natocheck`, owned by the service account, mode `0700`.
- Existing/provisioned Whisper base model: `/var/lib/natocheck/models/base.pt`.
  Install an approved model separately; do not download at request time.
- Loopback upstream: `127.0.0.1:8767` behind Apache HTTPS.

For a fresh installation, an authorized administrator must first verify the proposed paths and port,
Python/ffmpeg compatibility, model and module availability, and repository read
access. Verify the existing runtime against the pinned Whisper requirement. Do not modify
shared dependencies automatically. Keep
service source read-only to the service account and writable only to the release
operator. Do not modify the shared XvX environment during deployment.

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

The release uses the already available, verified `root@ai` key-based access.
It does not assume sudo or enable new root access. `NATOCHECK_SSH_TARGET` can
select another account already authorized to perform the release.

The reviewed installation entry point is `scripts/install-on-ai.sh`. It runs
through the existing authorized `root@ai` connection, refuses an existing
checkout or site configuration, clones the exact pushed release, verifies tests,
creates the dedicated service account, copies the existing local model, installs
the committed templates and obtains HTTPS through the existing Apache/Certbot
workflow. The owner explicitly approved the exact ACME endpoint, which was then
published in the central domain whitelist. No shared Python packages were changed.

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
acknowledge that step. If a desktop resolver still caches the pre-installation
NXDOMAIN answer, independently verify public DNS first, then set
`NATOCHECK_VERIFY_IP` to that verified address for HTTPS checks; certificate
validation still uses the public hostname. `NATOCHECK_PYTHON` selects an existing local Python; in
the XvX checkout it defaults to `../../xvx-venv/bin/python`. It serializes releases, restarts
the service, records revisions and status, and verifies HTTPS and a live exercise.
When the committed Apache host template changes, the release first requires the
active configuration to match the previous checkout. It backs up that configuration
under `.git/`, installs the reviewed template, validates Apache and reloads it.
A failed configuration test restores the previous configuration. This also enforces
the 2,000,000-byte request limit at the HTTPS proxy before forwarding uploads.
It never installs new infrastructure, changes DNS, installs dependencies or runs
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

## Mandatory post-deployment speech acceptance

Every release runs `scripts/check-live-speech.py` against the public HTTPS API.
It creates a fresh four-letter exercise, generates the expected English codewords
with the existing local XvX TTS skill, encodes both 128 kbit/s WebM/Opus and fragmented MP4/AAC, validates each,
uploads it without a language parameter, waits for real Whisper recognition and
requires a 100% ordered comparison for both formats. These generated fixtures do
not reproduce every Safari/iPhone MediaRecorder implementation. No recognition response is mocked. A failure
makes the deployment command fail; do not report that release as verified.
The deployment log distinguishes `restarted`, `live_failed` and `live_verified`.
Synthetic speech verifies the processing pipeline, not every human microphone/accent.

The release workstation needs its existing eSpeak and FFmpeg installations and
`../../skills-available/tts/speak.py`. Set `NATOCHECK_TTS_SCRIPT` to an existing
TTS skill path when needed. No tool, model or dependency is installed implicitly.
Generated speech and JSON reports remain in the TTS skill's `out.user.magnetics/`,
outside this repository. To rerun acceptance without deploying:

```sh
../../xvx-venv/bin/python scripts/check-live-speech.py
```
