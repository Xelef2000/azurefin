#!/usr/bin/python3
"""Verify a release base, rebuild private firmware, optionally stage; never reboot."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import postinstall_firmware as firmware

REPOSITORY = 'ghcr.io/xelef2000/azurefin'
WORKFLOW = 'https://github.com/Xelef2000/azurefin/.github/workflows/release-romulus.yml'
ISSUER = 'https://token.actions.githubusercontent.com'
RUNS = Path('/var/lib/azurefin/provisioning')


def release(value):
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-alpha)?', value):
        raise argparse.ArgumentTypeError('Expected vMAJOR.MINOR.PATCH[-alpha]')
    return value


def verified_manifest(version):
    release(version)
    # Resolve the tag once. Every later read uses the verified immutable digest.
    raw = subprocess.check_output(['skopeo', 'inspect', '--raw',
                                   f'docker://{REPOSITORY}:{version}-base'])
    manifest = json.loads(raw)
    if 'layers' not in manifest or 'config' not in manifest:
        raise RuntimeError('Expected a single ARM64 image, not a multi-platform index')
    reference = f'{REPOSITORY}@sha256:{hashlib.sha256(raw).hexdigest()}'
    subprocess.run(['cosign', 'verify', '--certificate-identity',
                    f'{WORKFLOW}@refs/tags/{version}',
                    '--certificate-oidc-issuer', ISSUER,
                    '-a', f'release={version}', '-a', 'component=base', reference], check=True)
    return reference, manifest


def fetch(work, reference, manifest):
    base = work / 'base-oci'
    subprocess.run(['skopeo', 'copy', '--preserve-digests',
                    f'docker://{reference}', f'oci:{base}'], check=True)
    index = json.loads((base / 'index.json').read_text())
    entries = index['manifests']
    digest = reference.split('@', 1)[1]
    if len(entries) != 1 or entries[0]['digest'] != digest:
        raise RuntimeError('Downloaded OCI manifest differs from verified digest')
    config_digest = manifest['config']['digest']
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', config_digest):
        raise RuntimeError('Invalid image config digest')
    config_raw = (base / 'blobs/sha256' / config_digest.split(':')[1]).read_bytes()
    if 'sha256:' + hashlib.sha256(config_raw).hexdigest() != config_digest:
        raise RuntimeError('Image config digest mismatch')
    config = json.loads(config_raw)
    if config.get('architecture') != 'arm64' or config.get('os') != 'linux':
        raise RuntimeError('Release is not Linux ARM64')
    (work / 'base-image-id').write_text(config_digest.split(':')[1] + '\n')
    return config_digest


def export_support(work, image_id):
    # Never execute the remote container. Copy provisioning tools from the
    # signature-verified release, not the stale installer seed on disk.
    podman = ['podman', '--root', str(work / 'storage'), '--runroot', str(work / 'run'),
              '--storage-driver', 'overlay']
    subprocess.run(podman + ['pull', f'oci:{work / "base-oci"}'], check=True)
    container = subprocess.check_output(podman + ['create', image_id, '/bin/true'], text=True).strip()
    if not re.fullmatch(r'[a-f0-9]{64}', container):
        raise RuntimeError('Unexpected container ID')
    try:
        subprocess.run(podman + ['cp', f'{container}:/usr/share/azurefin/update-support',
                                 str(work / 'support')], check=True)
    finally:
        subprocess.run(podman + ['rm', container], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', required=True, type=release)
    parser.add_argument('--check', action='store_true', help='verify signature only; do not fetch layers')
    parser.add_argument('--stage', action='store_true', help='stage verified, firmware-enabled result for next boot')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--msi', type=Path, help='supported local MSI; network still required for OS update')
    source.add_argument('--download', action='store_true', help='download firmware again using the new signed policy')
    args = parser.parse_args()
    if args.check and (args.stage or args.msi or args.download):
        parser.error('--check cannot prepare or stage a deployment')
    if not args.check and not (args.msi or args.download):
        parser.error('Choose --download or --msi for local firmware rebuilding')
    if not args.check and os.geteuid() != 0:
        parser.error('Run with sudo')
    for command in ('cosign', 'skopeo'):
        if not shutil.which(command):
            parser.error(f'Missing required verifier: {command}')
    if args.check:
        reference, _ = verified_manifest(args.release)
        print(f'VERIFIED: {reference}')
        return
    msi = args.msi.resolve(strict=True) if args.msi else None
    if msi is not None and not msi.is_file():
        parser.error('MSI must be a regular file')
    os.umask(0o077)
    RUNS.mkdir(parents=True, exist_ok=True)
    if RUNS.is_symlink():
        parser.error('Refusing a symlink workspace')
    with (RUNS / 'setup.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if shutil.disk_usage(RUNS).free < 60 * 1024**3:
            parser.error('At least 60 GiB free is required; failed runs are retained')
        subprocess.run(['bootc', 'status'], check=True)
        reference, manifest = verified_manifest(args.release)
        work = Path(tempfile.mkdtemp(prefix='azurefin-update.', dir=RUNS))
        print(f'Update workspace: {work}', flush=True)
        image_id = fetch(work, reference, manifest)
        export_support(work, image_id)
        payload = firmware.prepare(work, RUNS, msi)
        receipt = {'release': args.release, 'verified_base': reference, 'payload': str(payload),
                   'signer': f'{WORKFLOW}@refs/tags/{args.release}', 'issuer': ISSUER}
        (payload.parent / 'verified-update.json').write_text(json.dumps(receipt, indent=2) + '\n')
        if args.stage:
            subprocess.run(['bootc', 'switch', '--transport', 'oci', str(payload)], check=True)
            print('Signed-base firmware-enabled update staged. Reboot when ready.')
        else:
            print(f'Prepared only; no deployment changed. Payload: {payload}')
        print('Keep the workspace until boot is verified. No files were uploaded; no reboot requested.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
