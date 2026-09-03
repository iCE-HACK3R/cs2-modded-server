from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dependency_manager.py"
SPEC = importlib.util.spec_from_file_location("dependency_manager", MODULE_PATH)
assert SPEC and SPEC.loader
manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manager)
LOCK_PATH = Path(__file__).resolve().parents[1] / "dependencies.lock.json"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "dependencies-lock.schema.json"
WINDOWS_INSTALLER_PATH = Path(__file__).resolve().parents[1] / "win.bat"
LINUX_INSTALLER_PATH = Path(__file__).resolve().parents[1] / "install.sh"
DOCKER_INSTALLER_PATH = Path(__file__).resolve().parents[1] / "install_docker.sh"


class DependencyManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))

    def test_repository_lock_is_valid(self) -> None:
        manager.validate_lock(self.lock)

    def test_unlocked_required_dependency_fails_closed(self) -> None:
        with self.assertRaisesRegex(manager.DependencyError, "required dependencies are not locked: gamemode-manager"):
            manager.validate_required_dependencies(self.lock, ["metamod-source", "gamemode-manager"])

        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--lock", str(LOCK_PATH), "validate", "--require", "gamemode-manager"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("required dependencies are not locked: gamemode-manager", result.stderr)

    def test_repository_schema_is_valid_json(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_windows_installer_uses_locked_dependencies_before_custom_overlays(self) -> None:
        installer = WINDOWS_INSTALLER_PATH.read_text(encoding="utf-8").lower()
        readiness = installer.index("validate --require gamemode-manager")
        destructive_copy = installer.index(":: deleting addons folder")
        metamod_install = installer.index("dependency_manager.py\" install metamod-source")
        css_install = installer.index("dependency_manager.py\" install counterstrikesharp")
        custom_votes_install = installer.index("dependency_manager.py\" install cs2-customvotes")
        manager_install = installer.index("dependency_manager.py\" install gamemode-manager")
        custom_overlay = installer.index(":: merge your custom files in")
        self.assertLess(readiness, destructive_copy)
        self.assertLess(metamod_install, css_install)
        self.assertLess(css_install, custom_votes_install)
        self.assertLess(custom_votes_install, manager_install)
        self.assertLess(manager_install, custom_overlay)

    def test_linux_installers_gate_before_snapshot_and_install_locked_orchestrator(self) -> None:
        for path, snapshot_marker, overlay_marker in (
            (LINUX_INSTALLER_PATH, "install -m 0755", 'echo "merging in custom files'),
            (DOCKER_INSTALLER_PATH, 'echo "installing mods"', 'echo "merging in custom files"'),
        ):
            with self.subTest(installer=path.name):
                installer = path.read_text(encoding="utf-8").lower()
                readiness = installer.index("validate --require gamemode-manager")
                snapshot_copy = installer.index(snapshot_marker)
                manager_install = installer.index("install gamemode-manager")
                custom_overlay = installer.index(overlay_marker)
                self.assertLess(readiness, snapshot_copy)
                self.assertLess(manager_install, custom_overlay)

    def test_schema_and_runtime_reject_same_unsafe_path_samples(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        path_schema = schema["$defs"]["relativePath"]
        unsafe_paths = (
            ".", "addons//plugin", "addons/./plugin", "addons/../plugin", "addons/plugin/",
            "addons/plugin.", "addons/plugin ", "addons/CON", "addons/com1.dll",
            "addons/file:name", "addons/file\tname", "addons\\plugin",
        )
        for unsafe in unsafe_paths:
            with self.subTest(path=repr(unsafe)):
                schema_accepts = bool(re.fullmatch(path_schema["pattern"], unsafe)) and not bool(
                    re.search(path_schema["not"]["pattern"], unsafe)
                )
                self.assertFalse(manager.is_safe_relative_path(unsafe))
                self.assertFalse(schema_accepts)

    def test_unknown_lock_field_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.lock)
        candidate["surprise"] = True
        with self.assertRaisesRegex(manager.DependencyError, "unknown fields"):
            manager.validate_lock(candidate)

    def test_duplicate_platform_variant_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.lock)
        dependency = next(item for item in candidate["dependencies"] if item["id"] == "counterstrikesharp")
        dependency["assets"].append(copy.deepcopy(dependency["assets"][0]))
        with self.assertRaisesRegex(manager.DependencyError, "duplicate platform/variant"):
            manager.validate_lock(candidate)

    def test_seed_managed_overlap_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.lock)
        dependency = next(item for item in candidate["dependencies"] if item["id"] == "counterstrikesharp")
        dependency["assets"][0]["seedPaths"] = ["addons/counterstrikesharp/api/seed.json"]
        with self.assertRaisesRegex(manager.DependencyError, "seed path overlaps managed path"):
            manager.validate_lock(candidate)

    def test_overlapping_managed_paths_are_rejected(self) -> None:
        candidate = copy.deepcopy(self.lock)
        dependency = next(item for item in candidate["dependencies"] if item["id"] == "counterstrikesharp")
        dependency["assets"][0]["managedPaths"] = [
            "addons/counterstrikesharp/api",
            "addons/counterstrikesharp/api/CounterStrikeSharp.API.dll",
        ]
        with self.assertRaisesRegex(manager.DependencyError, "managed paths overlap"):
            manager.validate_lock(candidate)

    def test_noncanonical_and_windows_unsafe_paths_are_rejected(self) -> None:
        for unsafe in (".", "addons//plugin", "addons/./plugin", "addons/plugin.", "addons/CON", "addons/file:name"):
            with self.subTest(path=unsafe):
                candidate = copy.deepcopy(self.lock)
                dependency = next(item for item in candidate["dependencies"] if item["id"] == "counterstrikesharp")
                dependency["assets"][0]["managedPaths"] = [unsafe]
                with self.assertRaisesRegex(manager.DependencyError, "normalized, relative POSIX paths"):
                    manager.validate_lock(candidate)

    def test_archive_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("../escape.txt", "bad")
            with self.assertRaisesRegex(manager.DependencyError, "unsafe archive path"):
                manager.safe_extract(archive, root / "out", 1024)
            self.assertFalse((root / "escape.txt").exists())

    def test_archive_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "link.zip"
            info = zipfile.ZipInfo("link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr(info, "target")
            with self.assertRaisesRegex(manager.DependencyError, "links/devices"):
                manager.safe_extract(archive, root / "out", 1024)

    def test_expanded_size_limit_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "large.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("large.bin", b"x" * 1025)
            with self.assertRaisesRegex(manager.DependencyError, "expanded size limit"):
                manager.safe_extract(archive, root / "out", 1024)

    def test_tar_gz_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "bad.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                info = tarfile.TarInfo("../escape.txt")
                info.size = 3
                output.addfile(info, io.BytesIO(b"bad"))
            with self.assertRaisesRegex(manager.DependencyError, "unsafe archive path"):
                manager.safe_extract(archive, root / "out", 1024, "tar.gz")
            self.assertFalse((root / "escape.txt").exists())

    def test_tar_gz_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "link.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                info = tarfile.TarInfo("link")
                info.type = tarfile.SYMTYPE
                info.linkname = "target"
                output.addfile(info)
            with self.assertRaisesRegex(manager.DependencyError, "links/devices"):
                manager.safe_extract(archive, root / "out", 1024, "tar.gz")

    def test_tar_gz_expanded_size_limit_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "large.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                info = tarfile.TarInfo("large.bin")
                info.size = 1025
                output.addfile(info, io.BytesIO(b"x" * 1025))
            with self.assertRaisesRegex(manager.DependencyError, "expanded size limit"):
                manager.safe_extract(archive, root / "out", 1024, "tar.gz")

    def test_checksum_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "asset.zip"
            archive.write_bytes(b"not the locked bytes")
            asset = {"size": archive.stat().st_size, "sha256": "0" * 64}
            with self.assertRaisesRegex(manager.DependencyError, "SHA-256 mismatch"):
                manager.verify_archive(archive, asset)

    def test_install_replaces_managed_and_preserves_existing_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, asset = self.make_archive(root)
            target = root / "target"
            (target / "managed").mkdir(parents=True)
            (target / "managed" / "old.txt").write_text("old", encoding="utf-8")
            (target / "config").mkdir()
            (target / "config" / "settings.json").write_text("operator", encoding="utf-8")
            dependency = {"id": "test", "name": "Test", "version": "1"}

            manager.install_asset(archive, target, dependency, asset, keep_backup=False)

            self.assertEqual((target / "managed" / "new.txt").read_text(encoding="utf-8"), "new")
            self.assertFalse((target / "managed" / "old.txt").exists())
            self.assertEqual((target / "config" / "settings.json").read_text(encoding="utf-8"), "operator")

    def test_install_is_repeatable_and_cleans_transaction_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, asset = self.make_archive(root)
            target = root / "target"
            dependency = {"id": "test", "name": "Test", "version": "1"}

            manager.install_asset(archive, target, dependency, asset, keep_backup=False)
            (target / "managed" / "new.txt").write_text("locally changed", encoding="utf-8")
            manager.install_asset(archive, target, dependency, asset, keep_backup=False)

            self.assertEqual((target / "managed" / "new.txt").read_text(encoding="utf-8"), "new")
            self.assertEqual((target / "config" / "settings.json").read_text(encoding="utf-8"), "default")
            self.assertEqual(list((target / ".cs2-dependencies").iterdir()), [])

    def test_keep_backup_retains_old_managed_content_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, asset = self.make_archive(root)
            target = root / "target"
            (target / "managed").mkdir(parents=True)
            (target / "managed" / "old.txt").write_text("old", encoding="utf-8")
            dependency = {"id": "test", "name": "Test", "version": "1"}

            backup = manager.install_asset(archive, target, dependency, asset, keep_backup=True)

            self.assertIsNotNone(backup)
            assert backup is not None
            self.assertEqual((backup / "managed" / "old.txt").read_text(encoding="utf-8"), "old")
            self.assertFalse((backup.parent / "extracted").exists())
            self.assertFalse((backup / "config").exists())

    def test_partial_seed_copy_is_cleaned_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, asset = self.make_archive(root)
            target = root / "target"
            dependency = {"id": "test", "name": "Test", "version": "1"}

            copy_primitive = "copyfileobj" if manager.os.name == "posix" else "copy2"
            real_copy = getattr(manager.shutil, copy_primitive)

            def failing_copy(source: object, destination: object, *args: object) -> None:
                if manager.os.name == "posix":
                    if not isinstance(getattr(destination, "name", None), int):
                        real_copy(source, destination, *args)
                        return
                    destination.write(b"partial")  # type: ignore[union-attr]
                else:
                    Path(destination).write_text("partial", encoding="utf-8")  # type: ignore[arg-type]
                raise OSError("injected seed copy failure")

            with mock.patch.object(manager.shutil, copy_primitive, side_effect=failing_copy):
                with self.assertRaisesRegex(manager.DependencyError, "rolled back"):
                    manager.install_asset(archive, target, dependency, asset, keep_backup=False)

            self.assertFalse((target / "config" / "settings.json").exists())
            self.assertEqual(list((target / "config").glob(".cs2-seed-*")), [])

    @unittest.skipIf(not hasattr(Path, "symlink_to"), "symlinks unsupported")
    def test_symlink_ancestor_cannot_escape_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, asset = self.make_archive(root)
            target = root / "target"
            outside = root / "outside"
            outside.mkdir()
            target.mkdir()
            try:
                (target / "config").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"cannot create symlink: {exc}")
            dependency = {"id": "test", "name": "Test", "version": "1"}

            with self.assertRaisesRegex(manager.DependencyError, "symlink or junction"):
                manager.install_asset(archive, target, dependency, asset, keep_backup=False)

            self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipIf(not hasattr(Path, "symlink_to"), "symlinks unsupported")
    def test_dangling_seed_symlink_is_preserved_and_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, asset = self.make_archive(root)
            target = root / "target"
            (target / "config").mkdir(parents=True)
            outside = root / "outside.json"
            link = target / "config" / "settings.json"
            try:
                link.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"cannot create symlink: {exc}")
            dependency = {"id": "test", "name": "Test", "version": "1"}

            with self.assertRaisesRegex(manager.DependencyError, "symlink or junction"):
                manager.install_asset(archive, target, dependency, asset, keep_backup=False)

            self.assertTrue(link.is_symlink())
            self.assertFalse(outside.exists())

    @unittest.skipIf(not hasattr(Path, "symlink_to"), "symlinks unsupported")
    def test_target_root_symlink_is_rejected_without_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, asset = self.make_archive(root)
            real_target = root / "real-target"
            real_target.mkdir()
            target_link = root / "target-link"
            try:
                target_link.symlink_to(real_target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"cannot create symlink: {exc}")
            dependency = {"id": "test", "name": "Test", "version": "1"}

            with self.assertRaisesRegex(manager.DependencyError, "target root contains"):
                manager.install_asset(archive, target_link, dependency, asset, keep_backup=False)

            self.assertEqual(list(real_target.iterdir()), [])

    def test_install_failure_rolls_back_prior_managed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, asset = self.make_archive(root, two_managed=True)
            target = root / "target"
            for name in ("managed", "managed-two"):
                (target / name).mkdir(parents=True)
                (target / name / "old.txt").write_text(name, encoding="utf-8")
            dependency = {"id": "test", "name": "Test", "version": "1"}
            mutation = manager.move_relative_at if manager.os.name == "posix" else manager.os.replace
            calls = 0

            def failing_mutation(*args: object, **kwargs: object) -> None:
                nonlocal calls
                calls += 1
                if calls == 4:
                    raise OSError("injected replacement failure")
                mutation(*args, **kwargs)

            patched = mock.patch.object(manager, "move_relative_at", side_effect=failing_mutation) if manager.os.name == "posix" else mock.patch.object(manager.os, "replace", side_effect=failing_mutation)
            with patched:
                with self.assertRaisesRegex(manager.DependencyError, "rolled back"):
                    manager.install_asset(archive, target, dependency, asset, keep_backup=False)

            self.assertEqual((target / "managed" / "old.txt").read_text(encoding="utf-8"), "managed")
            self.assertEqual((target / "managed-two" / "old.txt").read_text(encoding="utf-8"), "managed-two")
            self.assertFalse((target / "config" / "settings.json").exists())

    def test_keyboard_interrupt_rolls_back_prior_managed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, asset = self.make_archive(root, two_managed=True)
            target = root / "target"
            for name in ("managed", "managed-two"):
                (target / name).mkdir(parents=True)
                (target / name / "old.txt").write_text(name, encoding="utf-8")
            dependency = {"id": "test", "name": "Test", "version": "1"}
            mutation = manager.move_relative_at if manager.os.name == "posix" else manager.os.replace
            calls = 0

            def interrupting_mutation(*args: object, **kwargs: object) -> None:
                nonlocal calls
                calls += 1
                if calls == 4:
                    raise KeyboardInterrupt()
                mutation(*args, **kwargs)

            patched = mock.patch.object(manager, "move_relative_at", side_effect=interrupting_mutation) if manager.os.name == "posix" else mock.patch.object(manager.os, "replace", side_effect=interrupting_mutation)
            with patched:
                with self.assertRaises(KeyboardInterrupt):
                    manager.install_asset(archive, target, dependency, asset, keep_backup=False)

            self.assertEqual((target / "managed" / "old.txt").read_text(encoding="utf-8"), "managed")
            self.assertEqual((target / "managed-two" / "old.txt").read_text(encoding="utf-8"), "managed-two")
            self.assertFalse((target / "config" / "settings.json").exists())

    def test_concurrent_install_lock_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_root = Path(temp)
            lock_path = state_root / "install.lock"
            lock_path.write_text("4242", encoding="ascii")
            with self.assertRaisesRegex(manager.DependencyError, "lock owner PID: 4242"):
                with manager.exclusive_install_lock(state_root):
                    self.fail("lock should not have been acquired")
            self.assertEqual(lock_path.read_text(encoding="ascii"), "4242")

    @staticmethod
    def make_archive(root: Path, two_managed: bool = False) -> tuple[Path, dict[str, object]]:
        archive = root / "asset.zip"
        files = {
            "managed/new.txt": b"new",
            "config/settings.json": b"default",
        }
        managed_paths = ["managed"]
        expected_paths = ["managed/new.txt"]
        if two_managed:
            files["managed-two/new.txt"] = b"new-two"
            managed_paths.append("managed-two")
            expected_paths.append("managed-two/new.txt")
        with zipfile.ZipFile(archive, "w") as output:
            for name, content in files.items():
                output.writestr(name, content)
        payload = archive.read_bytes()
        asset = {
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "archive": "zip",
            "expandedSizeLimit": 4096,
            "expectedPaths": expected_paths,
            "managedPaths": managed_paths,
            "seedPaths": ["config/settings.json"],
        }
        return archive, asset


if __name__ == "__main__":
    unittest.main()
