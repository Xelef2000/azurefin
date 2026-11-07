"""Boot integration contract checks; the VM also validates systemd's real graph."""
import configparser
from pathlib import Path
import unittest

UNITS = Path(__file__).parent / 'systemd'


def unit(name):
    result = configparser.ConfigParser(interpolation=None)
    result.read(UNITS / name)
    return result


class UnitsTests(unittest.TestCase):
    def test_only_timer_has_enablement(self):
        for path in UNITS.iterdir():
            with self.subTest(unit=path.name):
                self.assertEqual('Install' in unit(path.name), path.suffix == '.timer')

    def test_async_timer_and_live_guard(self):
        timer = unit('azurefin-nix-ready.timer')
        self.assertEqual(timer['Timer']['OnBootSec'], '30s')
        self.assertEqual(timer['Install']['WantedBy'], 'timers.target')
        for path in UNITS.iterdir():
            self.assertEqual(unit(path.name)['Unit']['ConditionKernelCommandLine'], '!rd.live.image')

    def test_dependency_chain(self):
        for name, parent in (
            ('nix.mount', 'azurefin-nix-directory.service'),
            ('azurefin-nix-initialize.service', 'nix.mount'),
            ('nix-daemon.service', 'azurefin-nix-initialize.service'),
            ('azurefin-nix-ready.service', 'nix-daemon.service'),
        ):
            with self.subTest(unit=name):
                config = unit(name)['Unit']
                self.assertEqual(config['Requires'], parent)
                self.assertIn(parent, config['After'].split())

    def test_no_automatic_retry_of_partial_install(self):
        config = unit('azurefin-nix-initialize.service')
        self.assertNotIn('Restart', config['Service'])
        self.assertNotIn('ConditionFirstBoot', config['Unit'])


if __name__ == '__main__':
    unittest.main()
