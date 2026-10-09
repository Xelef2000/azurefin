"""Offline orchestration tests; no containers, network or disks are modified."""
import os
import hashlib
import json
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("28-prepare-installer-payload.sh")
IMAGE = "a" * 64


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.oci = self.root / "source"
        self.oci.mkdir()
        for name in ("oci-layout", "index.json"):
            (self.oci / name).write_text("{}")
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        GITHUB_ACTIONS="false", TEST_IMAGE=IMAGE)
        self.tools = self.root / 'firmware-tools'
        source = Path(os.environ.get('AZUREFIN_FIRMWARE_TOOLS', SCRIPT.parent / 'firmware-tools'))
        shutil.copytree(source, self.tools)
        self.env['AZUREFIN_FIRMWARE_TOOLS'] = str(self.tools)
        self.stub("findmnt", "echo ext4")
        self.stub("df", "printf 'Avail\\n50000000\\n'")
        self.stub("podman", '''
while [ "${1#--}" != "$1" ]; do shift 2; done
case "$1" in
pull) exit 0 ;;
image) echo "$TEST_IMAGE" ;;
build)
    printf '%s\\n' "$@" > "$TEST_BUILD_ARGS"
    [ "${FAIL_BUILD:-0}" = 0 ] || exit 17
    while [ "$1" != --iidfile ]; do shift; done
    printf '%s\\n' "$TEST_IMAGE" > "$2" ;;
save)
    while [ "$1" != --output ]; do shift; done
    mkdir "$2"
    echo '{}' > "$2/index.json"
    echo '{}' > "$2/oci-layout" ;;
*) exit 99 ;;
esac
''')

    def stub(self, name, source):
        path = self.bin / name
        path.write_text("#!/bin/bash\nset -eu\n" + source + "\n")
        path.chmod(0o755)

    def run_script(self, image=IMAGE, msi=None):
        self.env['TEST_BUILD_ARGS'] = str(self.root / 'build-args')
        return subprocess.run(["bash", str(SCRIPT), str(self.oci), image,
                               str(self.root)] + ([str(msi)] if msi else []), env=self.env, text=True,
                              capture_output=True)

    def test_invalid_msi_rejected_before_import(self):
        msi = self.root / "wrong.msi"
        msi.write_text("not the pinned firmware")
        result = self.run_script(msi=msi)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum mismatch", result.stderr)
        self.assertEqual(list(self.root.glob("azurefin-provision.*")), [])

    def test_offline_uses_secret_and_disables_build_network(self):
        msi = self.root / "input with spaces.msi"
        msi.write_text("offline fixture")
        config = self.tools / 'firmware-policy.json'
        data = json.loads(config.read_text())
        data['msi']['sha512'] = hashlib.sha512(msi.read_bytes()).hexdigest()
        config.write_text(json.dumps(data))
        result = self.run_script(msi=msi)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        args = (self.root / 'build-args').read_text()
        self.assertIn('--network=none\n', args)
        self.assertIn('FIRMWARE_SOURCE=msi\n', args)
        self.assertIn('--secret=id=surface-msi,src=', args)
        self.assertNotIn('FIRMWARE_SOURCE=download', args)
        snapshot, = self.root.glob('azurefin-provision.*/context/firmware-tools/firmware-policy.json')
        self.assertEqual(snapshot.read_bytes(), config.read_bytes())

    def test_success_exports_ready_payload(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        args = (self.root / 'build-args').read_text()
        self.assertIn('--network=host\n', args)
        self.assertIn('FIRMWARE_SOURCE=download\n', args)
        self.assertNotIn('--network=none', args)
        ready, = self.root.glob("azurefin-provision.*/READY")
        self.assertTrue((Path(ready.read_text().strip()) / "index.json").is_file())

    def test_ram_workspace_rejected_before_build(self):
        self.stub("findmnt", "echo tmpfs")
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual(list(self.root.glob("azurefin-provision.*")), [])

    def test_low_space_rejected(self):
        self.stub("df", "printf 'Avail\\n1000\\n'")
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual(list(self.root.glob("azurefin-provision.*")), [])

    def test_failure_never_marks_ready(self):
        self.env["FAIL_BUILD"] = "1"
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual(list(self.root.glob("azurefin-provision.*/READY")), [])

    def test_wrong_base_never_marks_ready(self):
        self.env["TEST_IMAGE"] = "b" * 64
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual(list(self.root.glob("azurefin-provision.*/READY")), [])

    def test_invalid_id_rejected(self):
        self.assertNotEqual(self.run_script("moving-tag").returncode, 0)

    def test_ci_rejected(self):
        self.env["GITHUB_ACTIONS"] = "true"
        self.assertNotEqual(self.run_script().returncode, 0)


if __name__ == "__main__":
    unittest.main()
