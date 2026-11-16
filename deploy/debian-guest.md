# Fresh Debian guest installation

Run `scripts/bootstrap-debian.sh` inside a new Debian 13 amd64 guest with systemd.
It configures NatoCheck and an XvX Python runtime; it does not create the Xen VM,
partition disks or configure the hypervisor. A starting allocation is 4 vCPUs,
8 GB RAM and a 60 GB disk. The installer requires approximately 4 GB RAM and
20 GB free space. These are starting allocations, not latency guarantees.

## Prerequisites

The selected hostname must point to the guest and be on the central whitelist.
Public TCP ports 80 and 443 must reach Apache. SSH, DNS and firewall configuration
remain under the owner's control; the installer does not change them.

Review https://htki.de/rules/ before execution. Online Python installation requires
central approval for `pypi.org` and `files.pythonhosted.org`; the installer stops
before installation if these are missing. Alternatively, supply a local wheelhouse.
The installer does not modify the whitelist or download a Whisper model.

Inside the new guest:

```sh
# execute as root
apt-get update
apt-get install -y ca-certificates curl git python3
git clone https://github.com/magnetix-cgn/natocheck.git /root/natocheck-installer
cd /root/natocheck-installer
```

Use the reviewed release commit and a clean checkout. Transfer the existing
Whisper `base.pt` to `/root/base.pt`. Existing copies are available at
`~/.cache/whisper/base.pt` on the developer machine or
`/var/lib/natocheck/models/base.pt` on the AI server. Preserve the original.
The installer verifies its official SHA-256 from the pinned Whisper package.

## Plan and apply

The default prints a plan without fetching URLs or changing the system:

```sh
bash scripts/bootstrap-debian.sh --threads 4
```

Replace the uppercase placeholders with the approved hostname and certificate
registration email. The hostname must already resolve to this guest:

```sh
# execute as root
bash scripts/bootstrap-debian.sh --apply \
  --domain YOUR_APPROVED_HOSTNAME \
  --email YOUR_CERTIFICATE_EMAIL \
  --model /root/base.pt \
  --threads 4
```

For offline Python installation, add `--wheelhouse /root/natocheck-wheels`.
The directory must contain compatible Debian 13 amd64 / Python 3.13 wheels for
`torch==2.8.0`, `openai-whisper==20250625` and all transitive dependencies.
A CPU-only torch wheel is sufficient. Online PyPI torch packages can pull large
accelerator dependencies even though NatoCheck uses CPU inference. Debian package
installation, canonical rules checks and certificate issuance still need network.

## Installed components

- Python runtime: `/opt/xvx/xvx-venv/bin/python`.
- Source checkout: `/opt/xvx/externals/natocheck`, exact installer commit.
- FFmpeg, Apache HTTPS, Let's Encrypt certificate and automatic renewal.
- Unprivileged `natocheck` account and private state at `/var/lib/natocheck`.
- Hardened systemd service with a resident Whisper worker, listening on loopback.
- Tests, local HTTP, public HTTPS and a ten-letter challenge API acceptance check.

This installs the XvX environment needed by NatoCheck, not the entire XvX core
stack. Existing runtime, application, account, service, state and vhost paths are
refused. There is no automatic rollback of packages or completed installation
steps. Inspect partial installation after any failure before recovery.

## Verify and maintain

```sh
# execute as root
systemctl status natocheck --no-pager
journalctl -u natocheck -n 50 --no-pager
systemctl list-timers certbot.timer
```

Then test a spoken challenge in Chromium. An HTTPS check does not establish
microphone accuracy. The existing `deploy-to-ai.sh` targets the original AI server;
do not use it to update this guest. Future guest releases need a separately
reviewed deployment target.

The development checks cover shell syntax, argument validation, plan/help behavior
and embedded Python syntax. The agent has not executed installation on a fresh VM.
