# Dependency supply chain

The release branch installs external components from `dependencies.lock.json`. The lock records canonical upstream URLs, versions, licenses, platform assets, exact byte sizes, SHA-256 digests, expected archive paths, and ownership boundaries.

## Current coverage

The lock currently covers:

- Metamod:Source 2.0.0.1411 for Linux and Windows. This is an upstream pre-release from the CS2-capable 2.0 line; the separate 1.12 line does not provide the CS2 loader payload used here.
- CounterStrikeSharp 1.0.373 for Linux and Windows, with and without the bundled .NET 10 runtime.
- CS2-CustomVotes 1.1.4 for Linux and Windows.

Other plugin binaries still present under `game/csgo` are not yet covered. They remain migration inputs, not provenance-complete release artifacts. Do not describe or publish this branch as production-ready until every advertised mode dependency is either locked and validated or its mode is disabled.

Deployment entry points currently require a `gamemode-manager` lock entry and fail before installing dependencies because the clean 1.0.126 artifact has not yet been published at an immutable URL. This deliberately prevents the stale snapshot binary from being installed or mistaken for 1.0.126. Once the reviewed producer release is published, record its exact URL, byte size, and SHA-256 in the lock before removing this release gate.

## Validation and staging

The dependency manager uses only the Python standard library:

```text
python3 scripts/dependency_manager.py validate
python3 scripts/dependency_manager.py fetch counterstrikesharp --platform linux-x64 --variant with-runtime
python3 scripts/dependency_manager.py stage counterstrikesharp --platform linux-x64 --variant with-runtime --output /tmp/css-stage
```

`fetch` accepts HTTPS URLs from the lock's allowlist only, follows at most five allowlisted HTTPS redirects, enforces the locked byte count while streaming, and verifies SHA-256 before making a cache entry visible.

`stage` accepts locked ZIP and gzip-compressed TAR assets. It rejects absolute paths, parent traversal, backslashes, links, devices, duplicate output files, excessive entry counts, missing expected files, and archives over the expanded-size limit.

## Transactional installation

```text
python3 scripts/dependency_manager.py install counterstrikesharp \
  --platform linux-x64 \
  --variant with-runtime \
  --target /home/steam/cs2/game/csgo \
  --keep-backup
```

The dependency manager extracts and validates inside the target filesystem, then replaces only `managedPaths`. Existing `seedPaths` are never overwritten by the manager. If a managed replacement raises an ordinary process exception, prior managed paths and newly created seed files are rolled back.

The manager creates `.cs2-dependencies/install.lock` in the target. A second installer fails closed. Transactions are exception-safe, not yet crash-safe: a power loss or uncatchable process kill can leave a transaction directory and a partially moved managed set. Do not remove a stale lock and start the server blindly; first stop all installers, inspect the transaction directory named under `.cs2-dependencies`, and restore its `backup` paths as needed. Durable journaled recovery is required before this branch can be called production-ready.

With `--keep-backup`, replaced files remain in the reported transaction backup directory. Without it, successful transaction material is removed.

### Protected operator state

The CounterStrikeSharp dependency transaction deliberately does not manage:

- `addons/counterstrikesharp/configs`
- `addons/counterstrikesharp/plugins`
- `addons/counterstrikesharp/shared`
- Workshop content, databases, logs, and server cfg overrides

Core API/native/gamedata/runtime paths are replaced as one rollback-capable transaction. Config examples are seeded only when absent. Custom files are merged after locked dependencies so explicit operator overrides remain authoritative.

Metamod's `bin` directory, loader VDFs, and packaged README are manager-owned. `addons/metamod/metaplugins.ini` is seed-only: an existing operator plugin list is preserved.

The historical distribution overlay that runs before dependency installation still uses recursive copies and can overwrite files that it owns. Its remaining plugin/config trees are not covered by the guarantees above. Ownership-aware migration and stale-file cleanup remain release blockers.

## Remote distribution archives

Running `install.sh` from a complete checkout or extracted release uses local files. Running a standalone downloaded script requires both:

- `MOD_ARCHIVE_URL`, restricted to `https://github.com/...`
- `MOD_ARCHIVE_SHA256`, the expected lowercase SHA-256 of that exact archive

A remote mutable branch archive without a supplied digest is rejected. Versioned release documentation must publish the archive digest alongside the asset.

## Updating a lock entry

1. Select the correct official release line for the target game, record prerelease status when applicable, and review its license.
2. Record the exact release asset URL, upstream-provided or independently verified digest, and byte size.
3. Inspect the archive and define the smallest correct managed boundary.
4. Add expected paths that prove native, API, runtime, and/or plugin payload identity.
5. Run unit tests and real asset staging for every platform/variant.
6. Test clean install, upgrade preservation, tamper rejection, injected failure rollback, and concurrent-install rejection.
7. Update notices, compatibility documentation, and mode availability before enabling the dependency.

Never edit generated `.deps.json` files to claim compatibility. Upgrade or rebuild the producing project instead.
