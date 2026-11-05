import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from inventory_vendor import inventory


class VendorTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.lock = self.root / "Cargo.lock"
        self.lock.write_text('''[[package]]
name = "example"
version = "1.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "crate-hash"
''')
        self.vendor = self.root / "vendor"
        self.crate = self.vendor / "example"
        self.crate.mkdir(parents=True)
        (self.crate / "Cargo.toml").write_text('''[package]
name = "example"
version = "1.0.0"
license = "MIT OR Apache-2.0"
''')
        (self.crate / "LICENSE").write_text("test notice")
        self.checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in self.crate.iterdir()}
        self.write_checksums()

    def write_checksums(self):
        (self.crate / ".cargo-checksum.json").write_text(json.dumps({
            "package": "crate-hash", "files": self.checksums}))

    def test_valid(self):
        result = inventory(self.lock, self.vendor)
        self.assertEqual(result["crates"][0]["license_expression"], "MIT OR Apache-2.0")
        self.assertEqual(result["crates"][0]["notice_files"][0]["path"], "LICENSE")
        self.assertFalse(result["complete_license_inventory"])

    def test_modified(self):
        (self.crate / "LICENSE").write_text("changed")
        with self.assertRaises(ValueError):
            inventory(self.lock, self.vendor)

    def test_missing_crate(self):
        with self.assertRaises(ValueError):
            inventory(self.lock, self.root / "empty")

    def test_unsafe_path(self):
        self.checksums["../outside"] = "invalid"
        self.write_checksums()
        with self.assertRaises(ValueError):
            inventory(self.lock, self.vendor)
