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
                                    [str(p) for p in paths])
                self.assertEqual(result.stdout, expected)
                self.assertEqual(result.stderr, '')

    def test_future_profiles_available_without_relogin(self):
        self.check_path(0, '/home/linuxbrew/.linuxbrew/bin:/usr/bin')

    def test_profiles_append_once_preserving_homebrew(self):
        self.check_path(3, '/home/linuxbrew/.linuxbrew/bin:/usr/bin')

    def test_xdg_state_override(self):
        self.check_path(3, '/usr/bin', xdg=True)

    def test_empty_path_has_no_current_directory_entry(self):
        self.check_path(3, '')

    def test_command_appearing_after_shell_start_is_found(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            system = root / 'system/bin'
            script = Path(__file__).with_name('azurefin-nix.sh').read_text().replace(
                '/nix/var/nix/profiles/default/bin', str(system))
            # The shell sources the hook while all profiles are absent. It then
            # observes a command installed later without sourcing the hook again.
            script += f'\n/bin/mkdir -p "{system}"\n'
            script += f'printf "#!/bin/sh\\nexit 0\\n" > "{system}/nix"\n'
            script += f'/bin/chmod 755 "{system}/nix"\ncommand -v nix\n'
            env = dict(os.environ, HOME=str(root / 'home'), PATH=str(root / 'absent-system'))
            env.pop('XDG_STATE_HOME', None)
            for shell in ('/bin/sh', '/bin/bash'):
                result = subprocess.run([shell, '-c', script], env=env,
                                        capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout.strip(), str(system / 'nix'))
                self.assertEqual(result.stderr, '')
                (system / 'nix').unlink()
                system.rmdir()


if __name__ == '__main__':
    unittest.main()
