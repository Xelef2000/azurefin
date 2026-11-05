"""Exercise the POSIX PATH fragment without changing the host's /nix."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class ShellTests(unittest.TestCase):
    def check_path(self, present, initial, xdg=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'home'
            state = root / 'state' if xdg else home / '.local/state'
            system = root / 'system/bin'
            paths = [home / '.nix-profile/bin', state / 'nix/profile/bin', system]
            for path in paths[:present]:
                path.mkdir(parents=True)
            # Relocate just the absolute system profile for this host-side test.
            script = Path(__file__).with_name('azurefin-nix.sh').read_text()
            script = script.replace('/nix/var/nix/profiles/default/bin', str(system))
            env = dict(os.environ, HOME=str(home), PATH=initial)
            env.pop('XDG_STATE_HOME', None)
            if xdg:
                env['XDG_STATE_HOME'] = str(state)
            for shell in ('/bin/sh', '/bin/bash'):
                result = subprocess.run(
                    [shell, '-c', script + '\n' + script + '\nprintf "%s" "$PATH"'],
                    env=env, capture_output=True, text=True, check=True)
                expected = ':'.join(([initial] if initial else []) +
                                    [str(p) for p in paths[:present]])
                self.assertEqual(result.stdout, expected)
                self.assertEqual(result.stderr, '')

    def test_absent_store_changes_nothing(self):
        self.check_path(0, '/home/linuxbrew/.linuxbrew/bin:/usr/bin')

    def test_profiles_append_once_preserving_homebrew(self):
        self.check_path(3, '/home/linuxbrew/.linuxbrew/bin:/usr/bin')

    def test_xdg_state_override(self):
        self.check_path(3, '/usr/bin', xdg=True)

    def test_empty_path_has_no_current_directory_entry(self):
        self.check_path(3, '')


if __name__ == '__main__':
    unittest.main()
