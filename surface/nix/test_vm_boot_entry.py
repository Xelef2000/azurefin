import unittest

from vm_boot_entry import select


def entry(index):
    digest = 'a' * 64
    return (f'title Fedora (ostree:{index})\n'
            f'options root=UUID=test ostree=/ostree/boot.0/default/{digest}/{index}\n'
            f'linux /boot/ostree/default-{digest}/vmlinuz-test\n'
            f'initrd /boot/ostree/default-{digest}/initramfs-test.img\n')


class BootEntryTests(unittest.TestCase):
    def test_filename_is_not_deployment_order(self):
        self.assertEqual(select({'ostree-1.conf': entry(1), 'ostree-2.conf': entry(0)}), entry(0))

    def test_single_initial_deployment(self):
        self.assertEqual(select({'ostree-1.conf': entry(0)}), entry(0))

    def test_ambiguous_or_absent_default_refused(self):
        for entries in ({}, {'a': entry(1)}, {'a': entry(0), 'b': entry(0)}):
            with self.assertRaises(ValueError):
                select(entries)

    def test_conflicting_title_or_duplicate_options_refused(self):
        for text in (entry(0).replace('(ostree:0)', '(ostree:1)'), entry(0) + 'options other\n'):
            with self.assertRaises(ValueError):
                select({'a': text})


if __name__ == '__main__':
    unittest.main()
