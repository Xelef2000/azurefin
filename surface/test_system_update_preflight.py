import copy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import firmware_bundle
import system_update_preflight as preflight

ROOT = Path(__file__).resolve().parent


class SystemUpdateTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT / 'update-contract.json').read_text())
        self.state = {'status': {'booted': {'image': {'image': {
            'image': self.contract['channel'], 'signature': 'containerPolicy', 'transport': 'registry'
        }}}}}

    def test_signed_channel_is_accepted(self):
        preflight.validate_status(self.state, self.contract)

    def test_version_guard(self):
        for current, target, accepted in (
            ('v0.0.16-alpha', 'v0.0.14-alpha', False),
            ('v0.0.16-alpha', 'v0.0.17-alpha', True),
            ('v0.0.17-alpha', 'v0.0.17-alpha', True),
            ('v0.0.9-alpha', 'v0.0.10-alpha', True),
            ('v0.0.17', 'v0.0.17-alpha', False),
            ('v0.0.17-alpha', 'v0.0.17', True),
            (None, 'v0.0.17-alpha', False),
            ('v0.0.17-alpha', None, False),
        ):
            with self.subTest(current=current, target=target):
                state = copy.deepcopy(self.state)
                state['status']['booted']['image']['version'] = current
                config = {'config': {'Labels': {'org.opencontainers.image.version': target}}}
                if accepted:
                    preflight.validate_version(state, config)
                else:
                    with self.assertRaises(ValueError):
                        preflight.validate_version(state, config)

    def test_unsafe_states_rejected(self):
        for field in ('staged', 'rollbackQueued', 'usrOverlay'):
            state = copy.deepcopy(self.state)
            state['status'][field] = True
            with self.assertRaises(ValueError):
                preflight.validate_status(state, self.contract)
        for field, value in (('signature', None), ('transport', 'oci'), ('image', 'other:testing')):
            state = copy.deepcopy(self.state)
            state['status']['booted']['image']['image'][field] = value
            with self.assertRaises(ValueError):
                preflight.validate_status(state, self.contract)
        with self.assertRaises(ValueError):
            preflight.validate_status({}, self.contract)

    def test_target_requires_exact_firmware_and_loader(self):
        labels = {'org.azurefin.firmware-bundle': self.contract['firmware_bundle'],
                  'org.azurefin.firmware-loader-abi': self.contract['firmware_loader_abi']}
        preflight.validate_target({'config': {'Labels': labels}}, self.contract)
        for key in labels:
            bad = dict(labels, **{key: 'changed'})
            with self.assertRaises(ValueError):
                preflight.validate_target({'config': {'Labels': bad}}, self.contract)
        with self.assertRaises(ValueError):
            preflight.validate_target({}, self.contract)

    def test_contract_matches_policy_and_build_labels(self):
        manifest = firmware_bundle.manifest(json.loads((ROOT / 'firmware-policy.json').read_text()))
        self.assertEqual(hashlib.sha256(manifest).hexdigest(), self.contract['firmware_bundle'])
        recipe = (ROOT.parent / 'Containerfile.romulus').read_text()
        for label, field in (('firmware-bundle', 'firmware_bundle'), ('firmware-loader-abi', 'firmware_loader_abi')):
            self.assertIn(f'LABEL org.azurefin.{label}="{self.contract[field]}"', recipe)

    def test_runtime_guards_stop_before_registry_access(self):
        manifest = firmware_bundle.manifest(json.loads((ROOT / 'firmware-policy.json').read_text()))
        cases = (
            ('live session', 'rd.live.image', 0, manifest, 20 * 1024**3),
            ('firmware store', '', 1, manifest, 20 * 1024**3),
            ('firmware contract', '', 0, b'wrong manifest', 20 * 1024**3),
            ('Insufficient space', '', 0, manifest, 0),
        )
        for message, cmdline, firmware_result, contents, available in cases:
            with self.subTest(message=message), ExitStack() as stack:
                stack.enter_context(patch.object(preflight.os, 'geteuid', return_value=0))
                stack.enter_context(patch.object(preflight.Path, 'read_text',
                                                side_effect=[json.dumps(self.contract), cmdline]))
                stack.enter_context(patch.object(preflight.Path, 'read_bytes', return_value=contents))
                stack.enter_context(patch.object(preflight.firmware_preflight, 'main',
                                                return_value=firmware_result))
                stack.enter_context(patch.object(preflight.os, 'statvfs',
                                                return_value=SimpleNamespace(f_bavail=available, f_frsize=1)))
                command = stack.enter_context(patch.object(preflight.subprocess, 'check_output',
                                                            return_value=json.dumps(self.state)))
                with self.assertRaisesRegex(ValueError, message):
                    preflight.main()
                self.assertTrue(all(call.args[0][0] == 'bootc' for call in command.call_args_list))
                for call in command.call_args_list:
                    self.assertEqual(call.kwargs['stderr'], preflight.subprocess.PIPE)


if __name__ == '__main__':
    unittest.main()
