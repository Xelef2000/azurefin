"""Publish the full-ISO link before removing temporary GitHub transport assets."""
import json
import re
import subprocess
import sys


def removable_assets(assets, tag):
    allowed = re.compile(re.escape(f'azurefin-{tag}-aarch64.iso.part-') + r'\d{3}')
    result = []
    for asset in assets:
        name = asset['name']
        if name == 'ISO-SHA256SUM':
            continue
        if name not in ('SHA256SUMS', 'BUILD-INFO.txt', 'iso-audit.log') and not allowed.fullmatch(name):
            raise ValueError(f'Refusing to delete unexpected release asset: {name}')
        result.append(asset)
    return result


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def main(repo, tag, project):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid repository')
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-alpha)?', tag):
        raise ValueError('Invalid release tag')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', project):
        raise ValueError('Invalid SourceForge project')
    release = json.loads(gh('api', f'repos/{repo}/releases/tags/{tag}'))
    assets = release['assets']
    remove = removable_assets(assets, tag)
    checksums = [a for a in assets if a['name'] == 'ISO-SHA256SUM']
    if len(checksums) != 1:
        raise ValueError('Expected exactly one ISO-SHA256SUM asset')
    checksum = gh('api', '-H', 'Accept: application/octet-stream',
                  f'repos/{repo}/releases/assets/{checksums[0]["id"]}')
    filename = f'azurefin-{tag}-aarch64.iso'
    if not re.fullmatch(r'[a-f0-9]{64}  ' + re.escape(filename) + r'\n?', checksum):
        raise ValueError('Invalid ISO checksum')
    base = f'https://downloads.sourceforge.net/project/{project}/{tag}'
    curl = ['curl', '--fail', '--silent', '--show-error', '--location',
            '--retry', '6', '--retry-all-errors', '--retry-delay', '10', '--max-time', '30']
    mirrored = subprocess.check_output([*curl, f'{base}/ISO-SHA256SUM'], text=True)
    if mirrored.strip() != checksum.strip():
        raise ValueError('SourceForge checksum does not match GitHub release')
    headers = subprocess.check_output([*curl, '--head', f'{base}/{filename}'], text=True)
    # Reject an HTML landing/error page masquerading as a successful download.
    final_headers = headers.strip().split('\n\n')[-1].lower()
    if 'text/html' in final_headers or not re.search(r'content-length: [1-9][0-9]*', final_headers):
        raise ValueError('Full ISO download is not ready; retaining all GitHub assets')
    body = (f'[Download the ARM64 ISO]({base}/{filename})\n\n'
            'Download the attached `ISO-SHA256SUM` and verify with '
            '`sha256sum -c ISO-SHA256SUM` before flashing.\n')
    gh('release', 'edit', tag, '--repo', repo, '--notes', body)
    for asset in remove:
        gh('api', '--method', 'DELETE', f'repos/{repo}/releases/assets/{asset["id"]}')
        print(f'Removed temporary GitHub asset: {asset["name"]}')
    print(f'Release finalized: {base}/{filename}')


if __name__ == '__main__':
    main(*sys.argv[1:])
