"""Filesystem simulation for the disposable account-test container only.

Not used by the live-boot service. Account tests simulate the live command line
and systemd manager already; this maps Podman's FUSE overlay to the live root's
native overlay after checking the container marker and actual filesystem type.
"""


def simulated_live_fstype(actual, *, podman_container):
    if not podman_container:
        raise RuntimeError('Disposable Podman container required')
    actual = actual.strip()
    if actual not in ('overlay', 'tmpfs', 'fuse.fuse-overlayfs'):
        raise RuntimeError(f'Refusing account-test root filesystem: {actual}')
    return 'overlay\n' if actual == 'fuse.fuse-overlayfs' else actual + '\n'
