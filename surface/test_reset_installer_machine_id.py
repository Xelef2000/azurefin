from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from reset_installer_machine_id import reset_machine_ids


class MachineIdTests(unittest.TestCase):
    def test_containerfile_patch_runs_without_external_helper(self):
        surface = Path(__file__).resolve().parent
        containerfile = (surface / 'Containerfile.iso-builder').read_text()
        start = containerfile.index("path = Path('/usr/lib/osbuild/stages/org.osbuild.lorax-script')")
        end = containerfile.index('# Correct the composer', start)
        patch = containerfile[start:end]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage = root / 'stage.py'
            stage.write_text(
                'from pathlib import Path\n'
                'import sys\n'
                'def main(tree, options):\n'
                '    def script():\n'
                '        (Path(tree) / "etc/machine-id").write_text("\\n")\n'
                '    script()\n'
                'main(sys.argv[1], {})\n'
            )
            paths = {
                '/usr/lib/osbuild/stages/org.osbuild.lorax-script': stage,
                '/usr/libexec/azurefin-reset-installer-machine-id.py':
                    surface / 'reset_installer_machine_id.py',
            }
            exec(compile(patch, 'Containerfile patch', 'exec'), {'Path': paths.__getitem__})
            tree = root / 'tree'
            (tree / 'etc').mkdir(parents=True)
            # Isolated Python cannot import the repository helper. The patched
            # stage must carry everything needed to clear the ID Lorax creates.
            subprocess.run([sys.executable, '-I', str(stage), str(tree)],
                           cwd=root, check=True, capture_output=True)
            self.assertEqual((tree / 'etc/machine-id').read_bytes(), b'')

    def test_clear_real_id_and_newline_without_removing_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, contents in (('etc/machine-id', b'1' * 32 + b'\n'),
                                   ('usr/etc/machine-id', b'\n'),
                                   ('var/lib/dbus/machine-id', b'old')):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(contents)
            reset_machine_ids(root)
            for path in root.rglob('machine-id'):
                self.assertEqual(path.read_bytes(), b'')
            reset_machine_ids(root)

    def test_symlink_never_changes_external_file(self):
        with tempfile.TemporaryDirectory() as temp:
            outer = Path(temp)
            root = outer / 'tree'
            (root / 'etc').mkdir(parents=True)
            outside = outer / 'machine-id'
            outside.write_text('preserve')
            (root / 'etc/machine-id').symlink_to(outside)
            reset_machine_ids(root)
            self.assertEqual(outside.read_text(), 'preserve')
            self.assertTrue((root / 'etc/machine-id').is_symlink())

    def test_parent_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            outer = Path(temp)
            root = outer / 'tree'
            root.mkdir()
            (outer / 'machine-id').write_text('preserve')
            (root / 'etc').symlink_to(outer)
            with self.assertRaises(ValueError):
                reset_machine_ids(root)
            self.assertEqual((outer / 'machine-id').read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
