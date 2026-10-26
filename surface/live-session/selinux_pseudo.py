#!/usr/bin/python3
"""Generate SquashFS xattrs from the guest policy without relabeling the host."""
import base64
import ctypes
import errno
from pathlib import Path
import os
import sys


class Option(ctypes.Structure):
    _fields_ = [('type', ctypes.c_int), ('value', ctypes.c_char_p)]


def generate(root, output):
    lib = ctypes.CDLL('libselinux.so.1', use_errno=True)
    lib.selabel_open.argtypes = [ctypes.c_uint, ctypes.POINTER(Option), ctypes.c_uint]
    lib.selabel_open.restype = ctypes.c_void_p
    lib.selabel_lookup_raw.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p),
                                     ctypes.c_char_p, ctypes.c_int]
    lib.freecon.argtypes = [ctypes.c_void_p]
    lib.selabel_close.argtypes = [ctypes.c_void_p]
    policy = root / 'etc/selinux/targeted/contexts/files/file_contexts'
    # SELABEL_CTX_FILE=0, SELABEL_OPT_PATH=3 (libselinux public API).
    options = (Option * 1)(Option(3, os.fsencode(policy)))
    handle = lib.selabel_open(0, options, 1)
    if not handle:
        raise OSError(ctypes.get_errno(), 'Cannot open guest file-context policy')
    count = 0
    try:
        with output.open('x') as stream:
            paths = [root]
            for directory, dirs, files in os.walk(root, followlinks=False):
                # OSTree's backing objects are hardlinked to /usr. They are
                # not part of a plain live root and have different path labels.
                if Path(directory) == root / 'sysroot':
                    dirs[:] = [name for name in dirs if name != 'ostree']
                paths.extend(Path(directory) / name for name in dirs + files)
            for path in paths:
                name = '/' + str(path.relative_to(root)) if path != root else '/'
                if '\n' in name or '\r' in name:
                    raise ValueError('Unsupported newline in filename')
                context = ctypes.c_char_p()
                if lib.selabel_lookup_raw(handle, ctypes.byref(context), os.fsencode(name),
                                          path.lstat().st_mode) != 0:
                    # Policy deliberately leaves volatile content to runtime.
                    if ctypes.get_errno() == errno.ENOENT and name.startswith(('/tmp/', '/run/', '/proc/', '/sys/', '/dev/')):
                        continue
                    raise OSError(ctypes.get_errno(), f'No SELinux context for {name}')
                value = base64.b64encode(context.value + b'\0').decode()
                lib.freecon(context)
                escaped = name.replace('\\', '\\\\').replace('"', '\\"')
                stream.write(f'"{escaped}" x security.selinux=0s{value}\n')
                count += 1
    finally:
        lib.selabel_close(handle)
    print(f'Generated {count} guest SELinux labels')


if __name__ == '__main__':
    generate(Path(sys.argv[1]).resolve(strict=True), Path(sys.argv[2]))
