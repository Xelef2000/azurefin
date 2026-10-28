#!/usr/bin/env python3
"""Offline native sigstore policy tests; disposable keys, no system changes.

Requires skopeo with sigstore support. Fixtures are non-bootable empty images.
Temporary keys and images are removed on exit; no registry is contacted.
"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile


def run(*args, rejection=False):
    result = subprocess.run(args, text=True, capture_output=True, timeout=60)
    if rejection:
        if result.returncode == 0 or "Source image rejected" not in result.stderr:
            raise RuntimeError(f"Expected policy rejection: {args}\n{result.stderr}")
    elif result.returncode:
        raise RuntimeError(f"Command failed: {args}\n{result.stderr}")
    return result


def write_json(path, data):
    path.write_text(json.dumps(data))


def main():
    with tempfile.TemporaryDirectory(prefix="azurefin-native-signatures-") as directory:
        root = pathlib.Path(directory)
        password = root / "password"
        password.write_text("disposable-test-only\n")
        password.chmod(0o600)
        for key in ("trusted", "wrong"):
            run("skopeo", "generate-sigstore-key", "--output-prefix", str(root / key),
                "--passphrase-file", str(password))
        source = root / "unsigned"
        source.mkdir()
        config = json.dumps({"architecture": "arm64", "os": "linux",
                             "rootfs": {"type": "layers", "diff_ids": []},
                             "config": {}}).encode()
        digest = hashlib.sha256(config).hexdigest()
        (source / digest).write_bytes(config)
        write_json(source / "manifest.json", {
            "schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {"mediaType": "application/vnd.oci.image.config.v1+json",
                       "digest": f"sha256:{digest}", "size": len(config)}, "layers": []})
        allow = root / "fixture-only.json"
        write_json(allow, {"default": [{"type": "insecureAcceptAnything"}]})
        repository = 'ghcr.io/xelef2000/azurefin'
        identity = repository + ':test'
        for name, key, signed_identity in (
            ("valid", "trusted", identity),
            ("wrong-key", "wrong", identity),
            ("wrong-repository", "trusted", "example.invalid/other/image:test"),
        ):
            run("skopeo", "--policy", str(allow), "copy",
                "--sign-by-sigstore-private-key", str(root / f"{key}.private"),
                "--sign-passphrase-file", str(password), "--sign-identity", signed_identity,
                f"dir:{source}", f"dir:{root / name}")
        policy = root / "verify.json"
        # Exercise the shipped signature requirement using disposable keys and
        # local fixtures. No production private key or host policy is touched.
        shipped = json.loads((pathlib.Path(__file__).resolve().parent.parent /
                              'surface/native-ota/policy.json').read_text())
        requirements = shipped['transports']['docker'][repository]
        for requirement in requirements:
            requirement['keyPath'] = str(root / 'trusted.pub')
        write_json(policy, {"default": [{"type": "reject"}], "transports": {
            "dir": {str(root): requirements}}})
        for name in ("valid", "unsigned", "wrong-key", "wrong-repository"):
            run("skopeo", "--policy", str(policy), "copy", f"dir:{root / name}",
                f"dir:{root / ('result-' + name)}", rejection=name != "valid")
            print(f"PASS: {name} {'accepted' if name == 'valid' else 'rejected'}", flush=True)
        tampered = root / "tampered"
        shutil.copytree(root / "valid", tampered)
        manifest = json.loads((tampered / "manifest.json").read_text())
        manifest["annotations"] = {"test": "changed-after-signing"}
        write_json(tampered / "manifest.json", manifest)
        run("skopeo", "--policy", str(policy), "copy", f"dir:{tampered}",
            f"dir:{root / 'result-tampered'}", rejection=True)
        print("PASS: changed manifest rejected", flush=True)


if __name__ == "__main__":
    main()
