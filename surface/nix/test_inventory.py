import io
import json
import struct
import tarfile
import unittest

from inventory_payload import inventory, split_payload


class InventoryTests(unittest.TestCase):
    def test_trailer(self):
        meta = {"nix_version": "1", "nix_store_path": "/nix/store/a", "cacert_store_path": "/nix/store/b"}
        encoded = json.dumps(meta).encode()
        data = b"x" * 20 + b"payload" + encoded + struct.pack("<IQ", len(encoded), 7) + b"NIXINST1"
        self.assertEqual(split_payload(data), (b"payload", meta))

    def test_bad_trailers(self):
        for data in (b"", b"x" * 20, struct.pack("<IQ", 100, 100) + b"NIXINST1"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                split_payload(data)

    def archive(self, names):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            for name in names:
                item = tarfile.TarInfo(name)
                item.size = 1
                archive.addfile(item, io.BytesIO(b"x"))
        stream.seek(0)
        return stream

    def test_inventory(self):
        output = "0" * 32 + "-example-1"
        result = inventory(self.archive(["nix/.reginfo", f"nix/store/{output}/LICENSE"]))
        self.assertEqual(result["store_outputs"], ["/nix/store/" + output])
        self.assertEqual(result["notice_paths"], [f"nix/store/{output}/LICENSE"])

    def test_missing_registration_and_unsafe_paths(self):
        for names in ([], ["../file"], ["/absolute"], ["nix/.reginfo", "nix/.reginfo"]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                inventory(self.archive(names))
