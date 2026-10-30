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
                podman_opts += ["--storage-opt", f"overlay.mount_program={program}"]
                print("Azurefin: preserving FUSE whiteouts for shared image store")
''')
