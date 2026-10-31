"""Keep osbuild's temporary graphroot compatible with its shared image store."""


def patch_storage(source):
    anchor = 'podman_opts = [f"--root={storage_path_empty}", f"--imagestore={storage_path}"]'
    if source.count(anchor) != 1:
        raise ValueError('Unexpected osbuild shared-store implementation')
    return source.replace(anchor, anchor + '''
            # The temporary graphroot has no .has-mount-program marker of its
            # own. Native overlay cannot interpret a FUSE store's .wh.* files.
            # Preserve the shared store's whiteout semantics when mounting it.
            if os.path.exists(os.path.join(storage_path, "overlay", ".has-mount-program")):
                program = "/usr/bin/fuse-overlayfs"
                if not os.path.isfile(program):
                    raise RuntimeError("Shared FUSE image store requires fuse-overlayfs")
                try:
                    fd = os.open("/dev/fuse", os.O_RDWR)
                except OSError as error:
                    raise RuntimeError("Shared FUSE image store requires accessible /dev/fuse inside osbuild") from error
                else:
                    os.close(fd)
                podman_opts += ["--storage-opt", f"overlay.mount_program={program}"]
                print("Azurefin: preserving FUSE whiteouts for shared image store")
''')


def patch_buildroot(source):
    anchor = '            self._bind_dev(self.dev, "zero")'
    if source.count(anchor) != 1:
        raise ValueError('Unexpected osbuild device setup')
    # Bind only the existing host device; do not expose the entire host /dev.
    # Native-overlay builders without FUSE retain their existing behavior.
    return source.replace(anchor, anchor + '''
            if os.path.exists("/dev/fuse"):
                self._bind_dev(self.dev, "fuse")
''')
