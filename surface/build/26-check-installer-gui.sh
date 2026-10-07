#!/usr/bin/env bash
# Run inside the installer root, including after Lorax runtime cleanup.
set -euo pipefail
for executable in /usr/bin/gnome-kiosk /usr/bin/anaconda /usr/libexec/anaconda/run-in-new-session; do
    [[ -x $executable ]] || { echo "Missing installer GUI executable: $executable" >&2; exit 1; }
done
linker_output=$(ldd /usr/bin/gnome-kiosk 2>&1) || {
    echo "$linker_output" >&2
    exit 1
}
if grep -q 'not found' <<< "$linker_output"; then
    echo "$linker_output" >&2
    exit 1
fi
python3 - <<'PY'
import gi
import importlib.util
import ctypes
from pathlib import Path
gi.require_version('Gtk', '3.0')
gi.require_version('AnacondaWidgets', '3.4')
from gi.repository import Gtk, AnacondaWidgets
assert Gtk.MAJOR_VERSION == 3
assert AnacondaWidgets is not None
# Do not instantiate GTK objects or require a display during image builds.
# Resolving a dotted module imports its parents, which initializes Blivet and
# probes the build chroot. Check the GUI entry point without that side effect.
package = importlib.util.find_spec('pyanaconda')
assert package is not None and package.origin is not None
assert (Path(package.origin).parent / 'ui/gui/__init__.py').is_file()
ctypes.CDLL('libudev.so.1')
PY
echo INSTALLER_GUI_RUNTIME_VERIFIED
