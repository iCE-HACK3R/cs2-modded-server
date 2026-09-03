#!/usr/bin/env python3
"""Validate, fetch, stage, and transactionally install locked server assets."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

CHUNK_SIZE = 1024 * 1024
MAX_REDIRECTS = 5
MAX_ARCHIVE_ENTRIES = 10_000
WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


class DependencyError(RuntimeError):
    """A safe, actionable dependency operation failure."""


def load_lock(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DependencyError(f"cannot read lock file {path}: {exc}") from exc
    validate_lock(data)
    return data


def require_keys(value: dict[str, Any], required: set[str], allowed: set[str], context: str) -> None:
    missing = required - value.keys()
    extra = value.keys() - allowed
    if missing:
        raise DependencyError(f"{context}: missing fields: {', '.join(sorted(missing))}")
    if extra:
        raise DependencyError(f"{context}: unknown fields: {', '.join(sorted(extra))}")


def is_safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or value == "." or "\\" in value or "\x00" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value:
        return False
    for part in path.parts:
        stem = part.split(".", 1)[0].casefold()
        if (
            part in ("", ".", "..")
            or part.endswith((".", " "))
            or any(ord(character) < 32 or character in ':<>"|?*' for character in part)
            or stem in WINDOWS_RESERVED_NAMES
        ):
            return False
    return True


def validate_paths(values: object, context: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(values, list) or (not values and not allow_empty):
        raise DependencyError(f"{context}: expected {'a' if allow_empty else 'a non-empty'} path array")
    if len(values) != len(set(values)):
        raise DependencyError(f"{context}: duplicate paths are not allowed")
    if not all(is_safe_relative_path(value) for value in values):
        raise DependencyError(f"{context}: paths must be normalized, relative POSIX paths")
    return values


def validate_lock(lock: object) -> None:
    if not isinstance(lock, dict):
        raise DependencyError("lock root must be an object")
    require_keys(
        lock,
        {"schemaVersion", "allowedHosts", "dependencies"},
        {"$schema", "schemaVersion", "allowedHosts", "dependencies"},
        "lock",
    )
    if lock["schemaVersion"] != 1:
        raise DependencyError(f"unsupported schemaVersion: {lock['schemaVersion']!r}")
    hosts = lock["allowedHosts"]
    if not isinstance(hosts, list) or not hosts or len(hosts) != len(set(hosts)):
        raise DependencyError("allowedHosts must be a non-empty unique array")
    for host in hosts:
        if not isinstance(host, str) or host != host.lower() or not host or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for c in host):
            raise DependencyError(f"invalid allowed host: {host!r}")

    dependencies = lock["dependencies"]
    if not isinstance(dependencies, list) or not dependencies:
        raise DependencyError("dependencies must be a non-empty array")
    seen_ids: set[str] = set()
    for index, dependency in enumerate(dependencies):
        context = f"dependencies[{index}]"
        if not isinstance(dependency, dict):
            raise DependencyError(f"{context}: expected object")
        fields = {"id", "name", "version", "upstream", "license", "required", "modes", "assets"}
        require_keys(dependency, fields, fields, context)
        dep_id = dependency["id"]
        if not isinstance(dep_id, str) or not dep_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for c in dep_id):
            raise DependencyError(f"{context}.id: invalid identifier")
        if dep_id in seen_ids:
            raise DependencyError(f"duplicate dependency id: {dep_id}")
        seen_ids.add(dep_id)
        for field in ("name", "version"):
            if not isinstance(dependency[field], str) or not dependency[field]:
                raise DependencyError(f"{context}.{field}: expected non-empty string")
        validate_https_url(dependency["upstream"], hosts, f"{context}.upstream")
        if not isinstance(dependency["required"], bool):
            raise DependencyError(f"{context}.required: expected boolean")
        modes = dependency["modes"]
        if not isinstance(modes, list) or len(modes) != len(set(modes)) or not all(isinstance(mode, str) and mode for mode in modes):
            raise DependencyError(f"{context}.modes: expected unique non-empty strings")
        license_info = dependency["license"]
        if not isinstance(license_info, dict):
            raise DependencyError(f"{context}.license: expected object")
        license_fields = {"spdx", "url", "notice"}
        require_keys(license_info, license_fields, license_fields, f"{context}.license")
        if not isinstance(license_info["spdx"], str) or not license_info["spdx"]:
            raise DependencyError(f"{context}.license.spdx: expected non-empty string")
        if not isinstance(license_info["notice"], str) or not license_info["notice"]:
            raise DependencyError(f"{context}.license.notice: expected non-empty string")
        validate_https_url(license_info["url"], hosts, f"{context}.license.url")

        assets = dependency["assets"]
        if not isinstance(assets, list) or not assets:
            raise DependencyError(f"{context}.assets: expected non-empty array")
        seen_assets: set[tuple[str, str]] = set()
        for asset_index, asset in enumerate(assets):
            asset_context = f"{context}.assets[{asset_index}]"
            validate_asset(asset, hosts, asset_context)
            key = (asset["platform"], asset["variant"])
            if key in seen_assets:
                raise DependencyError(f"{asset_context}: duplicate platform/variant {key}")
            seen_assets.add(key)


def validate_asset(asset: object, hosts: list[str], context: str) -> None:
    if not isinstance(asset, dict):
        raise DependencyError(f"{context}: expected object")
    fields = {
        "platform", "variant", "url", "sha256", "size", "archive",
        "expandedSizeLimit", "expectedPaths", "managedPaths", "seedPaths",
    }
    require_keys(asset, fields, fields, context)
    if asset["platform"] not in ("linux-x64", "windows-x64"):
        raise DependencyError(f"{context}.platform: unsupported value")
    if asset["variant"] not in ("framework-dependent", "with-runtime"):
        raise DependencyError(f"{context}.variant: unsupported value")
    validate_https_url(asset["url"], hosts, f"{context}.url")
    digest = asset["sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise DependencyError(f"{context}.sha256: expected lowercase SHA-256")
    for field in ("size", "expandedSizeLimit"):
        if not isinstance(asset[field], int) or isinstance(asset[field], bool) or asset[field] < 1:
            raise DependencyError(f"{context}.{field}: expected positive integer")
    if asset["archive"] not in ("zip", "tar.gz"):
        raise DependencyError(f"{context}.archive: supported values are zip and tar.gz")
    expected = validate_paths(asset["expectedPaths"], f"{context}.expectedPaths")
    managed = validate_paths(asset["managedPaths"], f"{context}.managedPaths")
    seeds = validate_paths(asset["seedPaths"], f"{context}.seedPaths", allow_empty=True)
    for index, path in enumerate(managed):
        if any(paths_overlap(path, other) for other in managed[index + 1:]):
            raise DependencyError(f"{context}: managed paths overlap: {path}")
    for index, path in enumerate(seeds):
        if any(paths_overlap(path, other) for other in seeds[index + 1:]):
            raise DependencyError(f"{context}: seed paths overlap: {path}")
    for seed in seeds:
        if any(paths_overlap(seed, path) for path in managed):
            raise DependencyError(f"{context}: seed path overlaps managed path: {seed}")
    for path in expected:
        if not any(path == managed_path or path.startswith(managed_path + "/") for managed_path in managed):
            raise DependencyError(f"{context}: expected path is outside managed paths: {path}")


def validate_https_url(value: object, allowed_hosts: list[str], context: str) -> urllib.parse.ParseResult:
    if not isinstance(value, str):
        raise DependencyError(f"{context}: expected HTTPS URL")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in allowed_hosts:
        raise DependencyError(f"{context}: URL must use HTTPS and an allowed host")
    if parsed.username or parsed.password or parsed.fragment:
        raise DependencyError(f"{context}: credentials and fragments are not allowed")
    return parsed


def paths_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def select_asset(lock: dict[str, Any], dependency_id: str, platform: str, variant: str) -> tuple[dict[str, Any], dict[str, Any]]:
    dependency = next((item for item in lock["dependencies"] if item["id"] == dependency_id), None)
    if dependency is None:
        raise DependencyError(f"unknown dependency: {dependency_id}")
    asset = next((item for item in dependency["assets"] if item["platform"] == platform and item["variant"] == variant), None)
    if asset is None:
        raise DependencyError(f"no asset for {dependency_id} on {platform} ({variant})")
    return dependency, asset


def cache_path(cache_dir: Path, dependency: dict[str, Any], asset: dict[str, Any]) -> Path:
    suffix = Path(urllib.parse.urlparse(asset["url"]).path).suffix or ".zip"
    return cache_dir / f"{dependency['id']}-{dependency['version']}-{asset['platform']}-{asset['variant']}{suffix}"


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: list[str]) -> None:
        super().__init__()
        self.allowed_hosts = allowed_hosts
        self.redirects = 0

    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> urllib.request.Request:
        self.redirects += 1
        if self.redirects > MAX_REDIRECTS:
            raise DependencyError(f"download exceeded {MAX_REDIRECTS} redirects")
        validate_https_url(newurl, self.allowed_hosts, "redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def verify_archive(path: Path, asset: dict[str, Any]) -> None:
    actual_hash, actual_size = hash_file(path)
    if actual_size != asset["size"]:
        raise DependencyError(f"size mismatch for {path.name}: expected {asset['size']}, got {actual_size}")
    if actual_hash != asset["sha256"]:
        raise DependencyError(f"SHA-256 mismatch for {path.name}: expected {asset['sha256']}, got {actual_hash}")


def fetch_asset(lock: dict[str, Any], dependency: dict[str, Any], asset: dict[str, Any], cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_path(cache_dir, dependency, asset)
    if destination.exists():
        verify_archive(destination, asset)
        return destination

    handler = SafeRedirectHandler(lock["allowedHosts"])
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(asset["url"], headers={"User-Agent": "cs2-modded-server-dependency-manager/1"})
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=destination.name + ".", suffix=".part", dir=cache_dir, delete=False) as output:
            temporary = Path(output.name)
            with opener.open(request, timeout=60) as response:
                final_url = response.geturl()
                validate_https_url(final_url, lock["allowedHosts"], "final download URL")
                content_length = response.headers.get("Content-Length")
                if content_length is not None and int(content_length) != asset["size"]:
                    raise DependencyError(f"Content-Length mismatch: expected {asset['size']}, got {content_length}")
                written = 0
                while chunk := response.read(CHUNK_SIZE):
                    written += len(chunk)
                    if written > asset["size"]:
                        raise DependencyError("download exceeded locked size")
                    output.write(chunk)
        verify_archive(temporary, asset)
        os.replace(temporary, destination)
        temporary = None
        return destination
    except (OSError, urllib.error.URLError, zipfile.BadZipFile, ValueError) as exc:
        if isinstance(exc, DependencyError):
            raise
        raise DependencyError(f"download failed for {dependency['id']}: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def safe_extract_zip(archive: Path, destination: Path, expanded_size_limit: int) -> None:
    total_size = 0
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if len(members) > MAX_ARCHIVE_ENTRIES:
            raise DependencyError(f"archive exceeds entry limit of {MAX_ARCHIVE_ENTRIES}")
        for info in members:
            name = info.filename.rstrip("/")
            if not name:
                continue
            if not is_safe_relative_path(name):
                raise DependencyError(f"unsafe archive path: {info.filename!r}")
            mode = (info.external_attr >> 16) & 0xFFFF
            file_type = stat.S_IFMT(mode)
            if file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise DependencyError(f"archive links/devices are not allowed: {info.filename}")
            total_size += info.file_size
            if total_size > expanded_size_limit:
                raise DependencyError(f"archive exceeds expanded size limit of {expanded_size_limit} bytes")
            target = destination.joinpath(*PurePosixPath(name).parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info, "r") as input_stream, target.open("xb") as output_stream:
                shutil.copyfileobj(input_stream, output_stream, CHUNK_SIZE)
            if mode & 0o111:
                target.chmod(target.stat().st_mode | 0o111)


def safe_extract_tar_gz(archive: Path, destination: Path, expanded_size_limit: int) -> None:
    total_size = 0
    with tarfile.open(archive, mode="r:gz") as source:
        members = source.getmembers()
        if len(members) > MAX_ARCHIVE_ENTRIES:
            raise DependencyError(f"archive exceeds entry limit of {MAX_ARCHIVE_ENTRIES}")
        for info in members:
            name = info.name.rstrip("/")
            if not name:
                continue
            if not is_safe_relative_path(name):
                raise DependencyError(f"unsafe archive path: {info.name!r}")
            if not (info.isfile() or info.isdir()):
                raise DependencyError(f"archive links/devices are not allowed: {info.name}")
            total_size += info.size
            if total_size > expanded_size_limit:
                raise DependencyError(f"archive exceeds expanded size limit of {expanded_size_limit} bytes")
            target = destination.joinpath(*PurePosixPath(name).parts)
            if info.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            input_stream = source.extractfile(info)
            if input_stream is None:
                raise DependencyError(f"cannot read archive member: {info.name}")
            with input_stream, target.open("xb") as output_stream:
                shutil.copyfileobj(input_stream, output_stream, CHUNK_SIZE)
            if info.mode & 0o111:
                target.chmod(target.stat().st_mode | 0o111)


def safe_extract(archive: Path, destination: Path, expanded_size_limit: int, archive_type: str = "zip") -> None:
    destination.mkdir(parents=True, exist_ok=False)
    try:
        if archive_type == "zip":
            safe_extract_zip(archive, destination, expanded_size_limit)
        elif archive_type == "tar.gz":
            safe_extract_tar_gz(archive, destination, expanded_size_limit)
        else:
            raise DependencyError(f"unsupported archive type: {archive_type}")
    except DependencyError:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    except (OSError, zipfile.BadZipFile, tarfile.TarError) as exc:
        shutil.rmtree(destination, ignore_errors=True)
        raise DependencyError(f"invalid {archive_type} archive: {exc}") from exc


def validate_layout(extracted: Path, asset: dict[str, Any]) -> None:
    for relative in asset["expectedPaths"]:
        if not extracted.joinpath(*PurePosixPath(relative).parts).is_file():
            raise DependencyError(f"archive is missing expected file: {relative}")
    for relative in asset["managedPaths"]:
        if not extracted.joinpath(*PurePosixPath(relative).parts).exists():
            raise DependencyError(f"archive is missing declared path: {relative}")
    for relative in asset["seedPaths"]:
        if not extracted.joinpath(*PurePosixPath(relative).parts).is_file():
            raise DependencyError(f"archive seed path must be a file: {relative}")


def stage_asset(archive: Path, destination: Path, asset: dict[str, Any]) -> None:
    verify_archive(archive, asset)
    if destination.exists():
        raise DependencyError(f"stage destination already exists: {destination}")
    safe_extract(archive, destination, asset["expandedSizeLimit"], asset["archive"])
    try:
        validate_layout(destination, asset)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def reject_link_components(path: Path, context: str) -> None:
    absolute = lexical_absolute(path)
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if is_link_like(current):
            raise DependencyError(f"{context} contains a symlink or junction: {current}")


def open_absolute_directory_nofollow(path: Path) -> int:
    absolute = lexical_absolute(path)
    descriptor = os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in absolute.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def copy_seed(source: Path, target: Path, journal: list[tuple[Path, int, int]]) -> bool:
    if target.exists() or is_link_like(target):
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(tempfile.mkdtemp(prefix=".cs2-seed-", dir=target.parent))
    staged = temporary_root / "value"
    try:
        if source.is_dir():
            shutil.copytree(source, staged)
        else:
            shutil.copy2(source, staged)
        if target.exists() or is_link_like(target):
            return False
        metadata = staged.stat()
        record = (target, metadata.st_dev, metadata.st_ino)
        journal.append(record)
        try:
            os.link(staged, target, follow_symlinks=False)
            return True
        except FileExistsError:
            journal.remove(record)
            return False
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def reject_symlink_ancestors(target_root: Path, relative: str) -> None:
    current = target_root
    for part in PurePosixPath(relative).parts:
        current /= part
        if is_link_like(current):
            raise DependencyError(f"target path contains a symlink or junction: {current}")


@contextlib.contextmanager
def open_directory_at(root_fd: int, parts: tuple[str, ...], *, create: bool = False) -> Any:
    descriptor = os.dup(root_fd)
    try:
        for part in parts:
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, 0o755, dir_fd=descriptor)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def entry_exists_at(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def remove_entry_at(parent_fd: int, name: str) -> None:
    try:
        metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISDIR(metadata.st_mode):
        with open_directory_at(parent_fd, (name,)) as directory_fd:
            for child in os.listdir(directory_fd):
                remove_entry_at(directory_fd, child)
        os.rmdir(name, dir_fd=parent_fd)
    else:
        os.unlink(name, dir_fd=parent_fd)


def move_relative_at(source_root_fd: int, destination_root_fd: int, relative: str, *, destination_create: bool) -> None:
    parts = PurePosixPath(relative).parts
    with open_directory_at(source_root_fd, parts[:-1]) as source_parent_fd:
        with open_directory_at(destination_root_fd, parts[:-1], create=destination_create) as destination_parent_fd:
            os.rename(parts[-1], parts[-1], src_dir_fd=source_parent_fd, dst_dir_fd=destination_parent_fd)


def relative_exists_at(root_fd: int, relative: str) -> bool:
    parts = PurePosixPath(relative).parts
    try:
        with open_directory_at(root_fd, parts[:-1]) as parent_fd:
            return entry_exists_at(parent_fd, parts[-1])
    except FileNotFoundError:
        return False


def create_seed_at(source: Path, target_root_fd: int, relative: str, journal: list[tuple[str, int, int]]) -> bool:
    parts = PurePosixPath(relative).parts
    with open_directory_at(target_root_fd, parts[:-1], create=True) as parent_fd:
        if entry_exists_at(parent_fd, parts[-1]):
            return False
        temporary = f".cs2-seed-{os.getpid()}-{os.urandom(8).hex()}"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        try:
            try:
                with source.open("rb") as input_stream, os.fdopen(descriptor, "wb", closefd=False) as output_stream:
                    shutil.copyfileobj(input_stream, output_stream, CHUNK_SIZE)
                    output_stream.flush()
                    os.fsync(output_stream.fileno())
                os.fchmod(descriptor, source.stat().st_mode & 0o777)
                metadata = os.fstat(descriptor)
            finally:
                os.close(descriptor)
            record = (relative, metadata.st_dev, metadata.st_ino)
            journal.append(record)
            try:
                os.link(temporary, parts[-1], src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
                return True
            except FileExistsError:
                journal.remove(record)
                return False
        finally:
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except FileNotFoundError:
                pass


def install_asset_locked_posix(archive: Path, target_root: Path, state_root: Path, dependency: dict[str, Any], asset: dict[str, Any], keep_backup: bool) -> Path | None:
    transaction_name = f"{dependency['id']}-{os.getpid()}-{os.urandom(8).hex()}"
    replaced: list[tuple[str, bool]] = []
    created_seeds: list[tuple[str, int, int]] = []
    committed = False
    preserve_transaction = False
    target_fd = open_absolute_directory_nofollow(target_root)
    try:
        with open_directory_at(target_fd, (".cs2-dependencies",), create=True) as state_fd:
            os.mkdir(transaction_name, 0o700, dir_fd=state_fd)
            transaction_fd = os.open(transaction_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=state_fd)
            try:
                transaction_root = Path(f"/proc/self/fd/{transaction_fd}")
                extracted = transaction_root / "extracted"
                backup = transaction_root / "backup"
                stage_asset(archive, extracted, asset)
                os.mkdir("backup", 0o700, dir_fd=transaction_fd)
                with (
                    open_directory_at(transaction_fd, ("extracted",)) as extracted_fd,
                    open_directory_at(transaction_fd, ("backup",)) as backup_fd,
                ):
                    try:
                        for relative in asset["seedPaths"]:
                            create_seed_at(extracted.joinpath(*PurePosixPath(relative).parts), target_fd, relative, created_seeds)
                        for relative in asset["managedPaths"]:
                            parts = PurePosixPath(relative).parts
                            with open_directory_at(target_fd, parts[:-1], create=True) as target_parent_fd:
                                existed = entry_exists_at(target_parent_fd, parts[-1])
                            replaced.append((relative, existed))
                            if existed:
                                move_relative_at(target_fd, backup_fd, relative, destination_create=True)
                            move_relative_at(extracted_fd, target_fd, relative, destination_create=True)
                    except BaseException as exc:
                        rollback_errors: list[str] = []
                        for relative, existed in reversed(replaced):
                            try:
                                parts = PurePosixPath(relative).parts
                                if existed:
                                    backed_up = relative_exists_at(backup_fd, relative)
                                    if backed_up:
                                        with open_directory_at(target_fd, parts[:-1], create=True) as parent_fd:
                                            remove_entry_at(parent_fd, parts[-1])
                                        move_relative_at(backup_fd, target_fd, relative, destination_create=True)
                                else:
                                    with open_directory_at(target_fd, parts[:-1], create=True) as parent_fd:
                                        remove_entry_at(parent_fd, parts[-1])
                            except BaseException as rollback_exc:
                                rollback_errors.append(f"{relative}: {type(rollback_exc).__name__}: {rollback_exc}")
                        for relative, device, inode in reversed(created_seeds):
                            try:
                                parts = PurePosixPath(relative).parts
                                with open_directory_at(target_fd, parts[:-1]) as parent_fd:
                                    try:
                                        metadata = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
                                    except FileNotFoundError:
                                        continue
                                    if (metadata.st_dev, metadata.st_ino) == (device, inode):
                                        remove_entry_at(parent_fd, parts[-1])
                            except BaseException as rollback_exc:
                                rollback_errors.append(f"{relative}: {type(rollback_exc).__name__}: {rollback_exc}")
                        if rollback_errors:
                            preserve_transaction = True
                            raise DependencyError(f"install failed ({exc}); rollback also failed: {'; '.join(rollback_errors)}") from exc
                        if isinstance(exc, Exception):
                            raise DependencyError(f"install failed and was rolled back: {exc}") from exc
                        raise
                committed = True
                if keep_backup:
                    remove_entry_at(transaction_fd, "extracted")
                    return state_root / transaction_name / "backup"
                remove_entry_at(state_fd, transaction_name)
                return None
            finally:
                os.close(transaction_fd)
                if (not committed or not keep_backup) and not preserve_transaction:
                    remove_entry_at(state_fd, transaction_name)
    finally:
        os.close(target_fd)


@contextlib.contextmanager
def exclusive_install_lock(state_root: Path) -> Any:
    lock_path = state_root / "install.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        owner = "unknown"
        try:
            owner = lock_path.read_text(encoding="ascii").strip() or owner
        except OSError:
            pass
        raise DependencyError(f"another dependency transaction is active (lock owner PID: {owner}); remove {lock_path} only after confirming no installer is running") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        yield
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        lock_path.unlink(missing_ok=True)


def install_asset(archive: Path, target_root: Path, dependency: dict[str, Any], asset: dict[str, Any], keep_backup: bool) -> Path | None:
    target_root = lexical_absolute(target_root)
    reject_link_components(target_root, "target root")
    target_root.mkdir(parents=True, exist_ok=True)
    state_root = target_root / ".cs2-dependencies"
    if is_link_like(state_root):
        raise DependencyError(f"dependency state path must not be a symlink or junction: {state_root}")
    state_root.mkdir(exist_ok=True)
    with exclusive_install_lock(state_root):
        return install_asset_locked(archive, target_root, state_root, dependency, asset, keep_backup)


def install_asset_locked(archive: Path, target_root: Path, state_root: Path, dependency: dict[str, Any], asset: dict[str, Any], keep_backup: bool) -> Path | None:
    if os.name == "posix" and all(hasattr(os, feature) for feature in ("O_DIRECTORY", "O_NOFOLLOW")):
        return install_asset_locked_posix(archive, target_root, state_root, dependency, asset, keep_backup)
    transaction_root = Path(tempfile.mkdtemp(prefix=f"{dependency['id']}-", dir=state_root))
    extracted = transaction_root / "extracted"
    backup = transaction_root / "backup"
    replaced: list[tuple[Path, Path, bool]] = []
    created_seeds: list[tuple[Path, int, int]] = []
    committed = False
    preserve_transaction = False
    try:
        stage_asset(archive, extracted, asset)
        for relative in asset["seedPaths"]:
            reject_symlink_ancestors(target_root, relative)
            parts = PurePosixPath(relative).parts
            target = target_root.joinpath(*parts)
            copy_seed(extracted.joinpath(*parts), target, created_seeds)

        backup.mkdir()
        for relative in asset["managedPaths"]:
            reject_symlink_ancestors(target_root, relative)
            parts = PurePosixPath(relative).parts
            source = extracted.joinpath(*parts)
            target = target_root.joinpath(*parts)
            saved = backup.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            existed = target.exists() or target.is_symlink()
            replaced.append((target, saved, existed))
            if existed:
                saved.parent.mkdir(parents=True, exist_ok=True)
                os.replace(target, saved)
            os.replace(source, target)
        committed = True
        if keep_backup:
            shutil.rmtree(extracted, ignore_errors=True)
            return backup
        shutil.rmtree(transaction_root, ignore_errors=True)
        return None
    except BaseException as exc:
        rollback_errors: list[str] = []
        for target, saved, existed in reversed(replaced):
            try:
                if saved.exists() or saved.is_symlink():
                    if target.is_dir() and not target.is_symlink():
                        shutil.rmtree(target)
                    elif target.exists() or target.is_symlink():
                        target.unlink()
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(saved, target)
                elif not existed:
                    if target.is_dir() and not target.is_symlink():
                        shutil.rmtree(target)
                    elif target.exists() or target.is_symlink():
                        target.unlink()
            except BaseException as rollback_exc:
                rollback_errors.append(f"{target}: {type(rollback_exc).__name__}: {rollback_exc}")
        for target, device, inode in reversed(created_seeds):
            try:
                try:
                    metadata = target.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if (metadata.st_dev, metadata.st_ino) == (device, inode):
                    target.unlink()
            except BaseException as rollback_exc:
                rollback_errors.append(f"{target}: {type(rollback_exc).__name__}: {rollback_exc}")
        if rollback_errors:
            preserve_transaction = True
            raise DependencyError(f"install failed ({exc}); rollback also failed: {'; '.join(rollback_errors)}") from exc
        if isinstance(exc, Exception):
            raise DependencyError(f"install failed and was rolled back: {exc}") from exc
        raise
    finally:
        if (not committed or not keep_backup) and not preserve_transaction:
            shutil.rmtree(transaction_root, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=Path(__file__).resolve().parents[1] / "dependencies.lock.json")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate lock structure and invariants")

    for command in ("fetch", "stage", "install"):
        child = subparsers.add_parser(command)
        child.add_argument("dependency")
        child.add_argument("--platform", required=True, choices=("linux-x64", "windows-x64"))
        child.add_argument("--variant", default="framework-dependent", choices=("framework-dependent", "with-runtime"))
        child.add_argument("--cache", type=Path, default=Path(".cache/dependencies"))
        if command == "stage":
            child.add_argument("--output", type=Path, required=True)
        if command == "install":
            child.add_argument("--target", type=Path, required=True, help="CS2 game/csgo directory")
            child.add_argument("--keep-backup", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        lock = load_lock(args.lock.resolve())
        if args.command == "validate":
            print(f"lock valid: {len(lock['dependencies'])} dependencies")
            return 0
        dependency, asset = select_asset(lock, args.dependency, args.platform, args.variant)
        archive = fetch_asset(lock, dependency, asset, args.cache.resolve())
        if args.command == "fetch":
            print(f"verified: {archive}")
        elif args.command == "stage":
            stage_asset(archive, args.output.resolve(), asset)
            print(f"staged: {args.output.resolve()}")
        elif args.command == "install":
            target = lexical_absolute(args.target)
            backup = install_asset(archive, target, dependency, asset, args.keep_backup)
            print(f"installed {dependency['name']} {dependency['version']} into {target}")
            if backup is not None:
                print(f"backup retained: {backup}")
        return 0
    except DependencyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
