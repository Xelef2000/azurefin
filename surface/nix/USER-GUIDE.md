# Nix on Azurefin (testing candidate)

This feature is being validated on the Nix integration branch. It is not yet
available in a published Azurefin OS release.

## First boot

On an installed system, initialization begins about 30 seconds after boot. The
pinned bootstrap is bundled in the image and needs no internet connection.
Installing additional packages normally requires network access. Live sessions
do not initialize Nix.

Check readiness with:

```sh
systemctl status azurefin-nix-ready.service
nix --version
```

The daemon serves ordinary users without making them trusted administrators.
Bash and POSIX login-shell PATH integration preserves existing system and
Homebrew precedence. Other shells may need their own PATH configuration.

## Packages and desktop applications

No legacy Nixpkgs channel is configured automatically. For example, use
`nix shell nixpkgs#ghex` to open a shell containing GHex. The traditional
`nix-shell -p ghex` requires a user-configured Nixpkgs channel or another
explicit source for `<nixpkgs>`.

For Home Manager on Azurefin, enable its non-NixOS integration:

```nix
targets.genericLinux.enable = true;
```

Apply your Home Manager configuration, then log out completely and log back
in. GNOME needs the profile's `share` directory in `XDG_DATA_DIRS` to discover
desktop launchers; adding executables to `PATH` alone is not sufficient.

The next image also includes Fedora's Zsh at `/usr/bin/zsh`. Prefer this
image-owned executable over a mutable Nix-profile path for an account's login
shell. Installing Zsh does not change your default shell or Home Manager
configuration. Home Manager can still manage your Zsh configuration.

## Configuration

Global settings live in `/etc/nix/nix.conf`, a regular administrator-editable
file. Updates do not replace it. A reference default is stored in
`/usr/share/azurefin/nix/nix.conf`. After changing daemon settings, wait for active
builds to finish, then run `sudo systemctl restart nix-daemon.service`.

Each user can configure client preferences in `~/.config/nix/nix.conf`.
Daemon-restricted settings still require administrator authorization.

Unfree packages are not enabled globally. A user can opt in through
`~/.config/nixpkgs/config.nix`:

```nix
{ allowUnfree = true; }
```

This applies to Nixpkgs evaluations that read that file. Pure flake evaluation
does not automatically use it; pass `config.allowUnfree = true` explicitly when
importing Nixpkgs in a project, or use a selective `allowUnfreePredicate`.

## Updates and rollback

The persistent store is `/var/lib/nix`, bind-mounted at `/nix`. OS upgrades and
supported rollbacks preserve packages, profiles, accounts and configuration.
Rolling back to an image without Nix integration makes Nix unavailable but
retains the data; boot the Nix-enabled deployment again to regain access.

OS updates maintain integration code and the bootstrap for new installations;
they do not automatically upgrade an already initialized Nix runtime. No
automatic garbage-collection or runtime-upgrade timer is installed. Runtime
security updates therefore require a separate administrator-managed upgrade;
do not assume installing an OS update has upgraded Nix itself.

## Failed or interrupted setup

Inspect the service logs:

```sh
sudo journalctl -b -u azurefin-nix-directory -u azurefin-nix-initialize -u azurefin-nix-ready -u nix-daemon
```

Existing foreign installations and uncertain partial installations are preserved
and require guided manual review. Do not delete the store, ownership metadata,
accounts or receipt; do not run the upstream uninstaller or replay an installer
plan. Keep `/etc/nix`, `/var/lib/nix` and `/var/lib/azurefin/nix` intact. Rebooting
or freeing disk space does not by itself make replay safe. Initialization failure
does not intentionally block desktop startup.

The pinned runtime's sources and dependency notices are available in the
[source-only release](https://github.com/Xelef2000/azurefin/releases/tag/nix-sources-2.35.4-r1).
Installed notice texts and indexes live in `/usr/share/licenses/azurefin-nix`.
