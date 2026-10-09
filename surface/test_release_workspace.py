import unittest
from release_workspace import candidates


class WorkspaceTests(unittest.TestCase):
    def device(self, **changes):
        part = dict(name='/dev/sda3', type='part', label='AZUREFIN_WORK',
                    fstype='ext4', mountpoints=[None])
        part.update(changes)
        return dict(name='/dev/sda', type='disk', tran='usb', children=[part])

    def test_existing_usb_workspace(self):
        self.assertEqual(candidates([self.device()]), [('/dev/sda3', 'sda')])

    def test_internal_and_mounted_disks_rejected(self):
        disk = self.device()
        disk['tran'] = 'nvme'
        self.assertEqual(candidates([disk]), [])
        for changes in ({'mountpoints': ['/mnt']}, {'fstype': 'vfat'},
                        {'label': 'OTHER'}, {'name': '/dev/../../etc/passwd'}):
            self.assertEqual(candidates([self.device(**changes)]), [])


if __name__ == '__main__':
    unittest.main()
