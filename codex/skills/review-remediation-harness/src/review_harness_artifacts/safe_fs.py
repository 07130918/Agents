"""POSIX run-store path confinement and durable file primitives."""

from __future__ import annotations

import contextlib
import fcntl
import os
import platform
import stat
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from .contract import (
    validate_identifier,
    validate_repository_id,
    validate_run_relative_path,
)
from .errors import ArtifactError, fail

DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
CREATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
_CAPABILITY_PROBE_FILES = (
    "writer.lock",
    "source",
    "linked",
    "existing",
    "replacement",
)


def require_supported_platform() -> None:
    system = platform.system()
    if system not in {"Darwin", "Linux"}:
        fail(
            artifact_id=None,
            field="platform",
            invariant="artifact_store_requires_posix_durability",
            detail=f"Unsupported platform: {system}",
        )
    if not hasattr(os, "O_NOFOLLOW"):
        fail(
            artifact_id=None,
            field="platform.O_NOFOLLOW",
            invariant="artifact_store_requires_nofollow",
            detail="O_NOFOLLOW is unavailable",
        )


@dataclass(frozen=True, slots=True)
class StoreLocation:
    state_root: Path
    state_root_identity: tuple[int, int]
    repository_id: str
    run_id: str
    run_root: Path
    candidate_identity: tuple[int, int] | None

    @classmethod
    def resolve(
        cls,
        *,
        state_root: Path,
        repository_id: str,
        run_id: str,
        candidate_worktree: Path | None = None,
        create_state_root: bool = False,
    ) -> StoreLocation:
        require_supported_platform()
        validate_repository_id(repository_id)
        validate_identifier(run_id, field="run_id")
        expanded = state_root.expanduser()
        prospective_root = expanded.resolve(strict=False)
        candidate_realpath: Path | None = None
        candidate_identity: tuple[int, int] | None = None
        if candidate_worktree is not None:
            try:
                candidate_realpath = candidate_worktree.expanduser().resolve(
                    strict=True
                )
            except OSError as error:
                raise ArtifactError(
                    artifact_id=None,
                    field="candidate_worktree",
                    invariant="candidate_worktree_must_exist_and_resolve",
                    detail=str(error),
                ) from error
            if not candidate_realpath.is_dir():
                fail(
                    artifact_id=None,
                    field="candidate_worktree",
                    invariant="candidate_worktree_must_be_directory",
                    detail=f"Not a directory: {candidate_realpath}",
                )
            candidate_identity = _filesystem_identity(candidate_realpath)
            _reject_candidate_store_overlap(
                candidate_realpath=candidate_realpath,
                run_root=(prospective_root / "review-harness" / repository_id / run_id),
                recovery_report_root=(
                    prospective_root / "recovery-reports" / repository_id / run_id
                ),
            )
        if create_state_root:
            try:
                _create_absolute_directory_durably(
                    prospective_root,
                    forbidden_identity=candidate_identity,
                )
            except OSError as error:
                raise ArtifactError(
                    artifact_id=None,
                    field="state_root",
                    invariant="state_root_must_be_creatable",
                    detail=str(error),
                ) from error
        try:
            resolved_root = expanded.resolve(strict=True)
        except OSError as error:
            raise ArtifactError(
                artifact_id=None,
                field="state_root",
                invariant="state_root_must_exist_and_resolve",
                detail=str(error),
            ) from error
        if not resolved_root.is_dir():
            fail(
                artifact_id=None,
                field="state_root",
                invariant="state_root_must_be_directory",
                detail=f"Not a directory: {resolved_root}",
            )
        run_root = resolved_root / "review-harness" / repository_id / run_id
        recovery_report_root = (
            resolved_root / "recovery-reports" / repository_id / run_id
        )
        if candidate_realpath is not None:
            _reject_candidate_store_overlap(
                candidate_realpath=candidate_realpath,
                run_root=run_root,
                recovery_report_root=recovery_report_root,
            )
        return cls(
            state_root=resolved_root,
            state_root_identity=_filesystem_identity(
                resolved_root,
                field="state_root",
                invariant="state_root_identity_must_be_observable",
            ),
            repository_id=repository_id,
            run_id=run_id,
            run_root=run_root,
            candidate_identity=candidate_identity,
        )


def _reject_candidate_store_overlap(
    *,
    candidate_realpath: Path,
    run_root: Path,
    recovery_report_root: Path,
) -> None:
    for target_name, target_path in (
        ("run store", run_root),
        ("recovery report store", recovery_report_root),
    ):
        try:
            common = Path(
                os.path.commonpath((str(target_path), str(candidate_realpath)))
            )
        except ValueError as error:
            raise ArtifactError(
                artifact_id=None,
                field="candidate_worktree",
                invariant="candidate_and_store_paths_must_be_comparable",
                detail=str(error),
            ) from error
        overlaps = common in {candidate_realpath, target_path}
        if not overlaps:
            overlaps = _paths_overlap_by_filesystem_identity(
                candidate_realpath, target_path
            )
        if overlaps:
            fail(
                artifact_id=None,
                field="state_root",
                invariant=(
                    "run_store_must_be_outside_candidate_worktree"
                    if target_name == "run store"
                    else "recovery_reports_must_be_outside_candidate_worktree"
                ),
                detail=(
                    f"{target_name} {target_path} overlaps candidate worktree "
                    f"{candidate_realpath}"
                ),
            )


def _paths_overlap_by_filesystem_identity(
    candidate_realpath: Path,
    target_path: Path,
) -> bool:
    candidate_identity = _filesystem_identity(candidate_realpath)
    candidate_ancestors = _ancestor_identities(candidate_realpath)
    target_anchor, target_identity, target_exists = _nearest_existing_ancestor(
        target_path
    )
    target_ancestors = _ancestor_identities(target_anchor)
    return candidate_identity in target_ancestors or (
        target_exists and target_identity in candidate_ancestors
    )


def _filesystem_identity(
    path: Path,
    *,
    field: str = "candidate_worktree",
    invariant: str = "candidate_and_store_paths_must_be_comparable",
) -> tuple[int, int]:
    try:
        metadata = path.stat()
    except OSError as error:
        raise ArtifactError(
            artifact_id=None,
            field=field,
            invariant=invariant,
            detail=str(error),
        ) from error
    return metadata.st_dev, metadata.st_ino


def _ancestor_identities(path: Path) -> set[tuple[int, int]]:
    identities: set[tuple[int, int]] = set()
    current = path
    while True:
        identities.add(_filesystem_identity(current))
        parent = current.parent
        if parent == current:
            return identities
        current = parent


def _nearest_existing_ancestor(
    path: Path,
) -> tuple[Path, tuple[int, int], bool]:
    current = path
    path_exists = True
    while True:
        try:
            metadata = current.stat()
        except FileNotFoundError:
            path_exists = False
            parent = current.parent
            if parent == current:
                return current, _filesystem_identity(current), path_exists
            current = parent
            continue
        except OSError as error:
            raise ArtifactError(
                artifact_id=None,
                field="candidate_worktree",
                invariant="candidate_and_store_paths_must_be_comparable",
                detail=str(error),
            ) from error
        return current, (metadata.st_dev, metadata.st_ino), path_exists


def _open_directory(path: Path) -> int:
    if not path.is_absolute():
        fail(
            artifact_id=None,
            field=str(path),
            invariant="directory_path_must_be_absolute",
            detail="Safe directory roots must be absolute paths",
        )
    descriptor = os.open("/", DIRECTORY_FLAGS)
    try:
        for segment in path.parts[1:]:
            next_descriptor = os.open(segment, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
    except OSError as error:
        os.close(descriptor)
        raise ArtifactError(
            artifact_id=None,
            field=str(path),
            invariant="directory_must_open_without_following_symlink",
            detail=str(error),
        ) from error
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        fail(
            artifact_id=None,
            field=str(path),
            invariant="opened_path_must_be_directory",
            detail="Opened path is not a directory",
        )
    return descriptor


def _create_absolute_directory_durably(
    path: Path,
    *,
    forbidden_identity: tuple[int, int] | None = None,
) -> None:
    """Create every missing component and durably publish each directory entry."""

    if not path.is_absolute():
        raise OSError(f"State root must resolve to an absolute path: {path}")
    descriptor = os.open("/", DIRECTORY_FLAGS)
    try:
        _reject_directory_identity(
            descriptor,
            path=path,
            forbidden_identity=forbidden_identity,
        )
        for segment in path.parts[1:]:
            try:
                next_descriptor = os.open(segment, DIRECTORY_FLAGS, dir_fd=descriptor)
            except FileNotFoundError:
                try:
                    os.mkdir(segment, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                next_descriptor = os.open(segment, DIRECTORY_FLAGS, dir_fd=descriptor)
            try:
                _reject_directory_identity(
                    next_descriptor,
                    path=path,
                    forbidden_identity=forbidden_identity,
                )
            except ArtifactError:
                os.close(next_descriptor)
                raise
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _reject_directory_identity(
    descriptor: int,
    *,
    path: Path,
    forbidden_identity: tuple[int, int] | None,
) -> None:
    if forbidden_identity is None:
        return
    metadata = os.fstat(descriptor)
    if (metadata.st_dev, metadata.st_ino) == forbidden_identity:
        fail(
            artifact_id=None,
            field=str(path),
            invariant="state_root_creation_must_not_enter_candidate_worktree_identity",
            detail="State-root creation entered the resolved candidate worktree inode",
        )


class SafeDirectory:
    """A directory descriptor used for nofollow traversal below one fixed root."""

    def __init__(
        self,
        path: Path,
        *,
        descriptor: int | None = None,
        expected_identity: tuple[int, int] | None = None,
        forbidden_identity: tuple[int, int] | None = None,
    ) -> None:
        self.path = path
        self.fd = _open_directory(path) if descriptor is None else descriptor
        self.forbidden_identity = forbidden_identity
        try:
            self._verify_directory_identity(
                self.fd,
                expected_identity=expected_identity,
            )
        except ArtifactError:
            os.close(self.fd)
            self.fd = -1
            raise

    def _verify_directory_identity(
        self,
        descriptor: int,
        *,
        expected_identity: tuple[int, int] | None = None,
    ) -> None:
        metadata = os.fstat(descriptor)
        identity = (metadata.st_dev, metadata.st_ino)
        if expected_identity is not None and identity != expected_identity:
            fail(
                artifact_id=None,
                field=str(self.path),
                invariant="state_root_identity_must_match_resolution",
                detail="State root was replaced after path resolution",
            )
        if self.forbidden_identity is not None and identity == self.forbidden_identity:
            fail(
                artifact_id=None,
                field=str(self.path),
                invariant="store_must_not_enter_candidate_worktree_identity",
                detail="Store traversal entered the resolved candidate worktree inode",
            )

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    @staticmethod
    def _segments(relative_path: str) -> list[str]:
        validate_run_relative_path(relative_path, artifact_id=None, field="path")
        return relative_path.split("/")

    def _open_child_directory(self, parent_fd: int, name: str, *, create: bool) -> int:
        try:
            descriptor = os.open(name, DIRECTORY_FLAGS, dir_fd=parent_fd)
        except FileNotFoundError:
            if not create:
                raise
            try:
                os.mkdir(name, mode=0o700, dir_fd=parent_fd)
            except FileExistsError:
                pass
            descriptor = os.open(name, DIRECTORY_FLAGS, dir_fd=parent_fd)
        try:
            self._verify_directory_identity(descriptor)
        except ArtifactError:
            os.close(descriptor)
            raise
        if create:
            os.fsync(parent_fd)
        return descriptor

    @contextlib.contextmanager
    def open_parent(
        self, relative_path: str, *, create: bool = False
    ) -> Iterator[tuple[int, str]]:
        segments = self._segments(relative_path)
        current = os.dup(self.fd)
        try:
            for segment in segments[:-1]:
                next_fd = self._open_child_directory(current, segment, create=create)
                os.close(current)
                current = next_fd
            yield current, segments[-1]
        except OSError as error:
            raise ArtifactError(
                artifact_id=None,
                field=relative_path,
                invariant="path_components_must_be_real_directories",
                detail=str(error),
            ) from error
        finally:
            os.close(current)

    def ensure_directory(self, relative_path: str) -> None:
        validate_run_relative_path(relative_path, artifact_id=None, field="path")
        current = os.dup(self.fd)
        try:
            for segment in relative_path.split("/"):
                next_fd = self._open_child_directory(current, segment, create=True)
                os.close(current)
                current = next_fd
            os.fsync(current)
        except OSError as error:
            raise ArtifactError(
                artifact_id=None,
                field=relative_path,
                invariant="directory_tree_must_be_creatable_without_symlinks",
                detail=str(error),
            ) from error
        finally:
            os.close(current)

    def open_subdirectory(self, relative_path: str, *, create: bool) -> SafeDirectory:
        validate_run_relative_path(relative_path, artifact_id=None, field="path")
        current = os.dup(self.fd)
        try:
            for segment in relative_path.split("/"):
                next_fd = self._open_child_directory(current, segment, create=create)
                os.close(current)
                current = next_fd
            if create:
                os.fsync(current)
            descriptor = current
            current = -1
            return SafeDirectory(
                self.path / relative_path,
                descriptor=descriptor,
                forbidden_identity=self.forbidden_identity,
            )
        except FileNotFoundError as error:
            raise ArtifactError(
                artifact_id=None,
                field=relative_path,
                invariant="run_store_directory_must_exist",
                detail=str(error),
            ) from error
        except OSError as error:
            raise ArtifactError(
                artifact_id=None,
                field=relative_path,
                invariant="directory_tree_must_be_openable_without_symlinks",
                detail=str(error),
            ) from error
        finally:
            if current >= 0:
                os.close(current)

    def read_bytes(self, relative_path: str) -> bytes:
        with self.open_parent(relative_path) as (parent_fd, name):
            try:
                descriptor = os.open(name, READ_FLAGS, dir_fd=parent_fd)
            except OSError as error:
                raise ArtifactError(
                    artifact_id=None,
                    field=relative_path,
                    invariant="file_must_open_without_following_symlink",
                    detail=str(error),
                ) from error
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode):
                    fail(
                        artifact_id=None,
                        field=relative_path,
                        invariant="run_store_object_must_be_regular_file",
                        detail="Opened path is not a regular file",
                    )
                chunks: list[bytes] = []
                while True:
                    chunk = os.read(descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                return b"".join(chunks)
            finally:
                os.close(descriptor)

    def exists(self, relative_path: str) -> bool:
        try:
            with self.open_parent(relative_path) as (parent_fd, name):
                metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except ArtifactError as error:
            if isinstance(error.__cause__, (FileNotFoundError, NotADirectoryError)):
                return False
            raise
        if stat.S_ISLNK(metadata.st_mode):
            fail(
                artifact_id=None,
                field=relative_path,
                invariant="run_store_path_must_not_be_symlink",
                detail="Symlink found in run store",
            )
        return True

    def write_exclusive(
        self, relative_path: str, content: bytes, *, mode: int = 0o600
    ) -> None:
        with self.open_parent(relative_path, create=True) as (parent_fd, name):
            try:
                descriptor = os.open(name, CREATE_FLAGS, mode, dir_fd=parent_fd)
            except OSError as error:
                raise ArtifactError(
                    artifact_id=None,
                    field=relative_path,
                    invariant="file_must_be_created_exclusively",
                    detail=str(error),
                ) from error
            try:
                view = memoryview(content)
                while view:
                    written = os.write(descriptor, view)
                    view = view[written:]
                durable_sync(descriptor)
            finally:
                os.close(descriptor)
            os.fsync(parent_fd)

    def hard_link_no_replace(self, source: str, destination: str) -> None:
        with (
            self.open_parent(source) as (source_parent, source_name),
            self.open_parent(destination, create=True) as (
                destination_parent,
                destination_name,
            ),
        ):
            try:
                os.link(
                    source_name,
                    destination_name,
                    src_dir_fd=source_parent,
                    dst_dir_fd=destination_parent,
                    follow_symlinks=False,
                )
                os.fsync(destination_parent)
            except FileExistsError:
                source_bytes = self.read_bytes(source)
                destination_bytes = self.read_bytes(destination)
                if source_bytes != destination_bytes:
                    fail(
                        artifact_id=None,
                        field=destination,
                        invariant="existing_destination_must_have_exact_same_bytes",
                        detail="No-replace destination already exists with different bytes",
                    )
                os.fsync(destination_parent)
            except OSError as error:
                raise ArtifactError(
                    artifact_id=None,
                    field=destination,
                    invariant="atomic_no_replace_install_must_succeed",
                    detail=str(error),
                ) from error

    def replace(self, source: str, destination: str) -> None:
        with (
            self.open_parent(source) as (source_parent, source_name),
            self.open_parent(destination, create=True) as (
                destination_parent,
                destination_name,
            ),
        ):
            try:
                os.replace(
                    source_name,
                    destination_name,
                    src_dir_fd=source_parent,
                    dst_dir_fd=destination_parent,
                )
                os.fsync(source_parent)
                os.fsync(destination_parent)
            except OSError as error:
                raise ArtifactError(
                    artifact_id=None,
                    field=destination,
                    invariant="atomic_replace_must_succeed",
                    detail=str(error),
                ) from error

    def sync_file(self, relative_path: str) -> None:
        with self.open_parent(relative_path) as (parent_fd, name):
            try:
                descriptor = os.open(name, READ_FLAGS, dir_fd=parent_fd)
            except OSError as error:
                raise ArtifactError(
                    artifact_id=None,
                    field=relative_path,
                    invariant="file_must_open_for_durable_sync",
                    detail=str(error),
                ) from error
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode):
                    fail(
                        artifact_id=None,
                        field=relative_path,
                        invariant="durable_sync_target_must_be_regular_file",
                        detail="Sync target is not a regular file",
                    )
                durable_sync(descriptor)
            finally:
                os.close(descriptor)
            os.fsync(parent_fd)

    def sync_root(self) -> None:
        os.fsync(self.fd)

    def list_names(self, relative_path: str | None = None) -> list[str]:
        descriptor = os.dup(self.fd)
        try:
            if relative_path is not None:
                validate_run_relative_path(
                    relative_path, artifact_id=None, field="path"
                )
                for segment in relative_path.split("/"):
                    next_fd = self._open_child_directory(
                        descriptor, segment, create=False
                    )
                    os.close(descriptor)
                    descriptor = next_fd
            names = sorted(os.listdir(descriptor))
            for name in names:
                metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                if stat.S_ISLNK(metadata.st_mode):
                    fail(
                        artifact_id=None,
                        field=f"{relative_path or '.'}/{name}",
                        invariant="run_store_path_must_not_be_symlink",
                        detail="Symlink found while enumerating run store",
                    )
            return names
        except FileNotFoundError:
            return []
        except OSError as error:
            raise ArtifactError(
                artifact_id=None,
                field=relative_path or ".",
                invariant="directory_must_be_readable",
                detail=str(error),
            ) from error
        finally:
            os.close(descriptor)

    @contextlib.contextmanager
    def exclusive_lock(self, relative_path: str = "writer.lock") -> Iterator[None]:
        with self.open_parent(relative_path, create=True) as (parent_fd, name):
            try:
                descriptor = os.open(
                    name,
                    os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                    dir_fd=parent_fd,
                )
            except OSError as error:
                raise ArtifactError(
                    artifact_id=None,
                    field=relative_path,
                    invariant="writer_lock_must_open_without_symlink",
                    detail=str(error),
                ) from error
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode):
                    fail(
                        artifact_id=None,
                        field=relative_path,
                        invariant="writer_lock_must_be_regular_file",
                        detail="Writer lock is not a regular file",
                    )
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)


def durable_sync(descriptor: int) -> None:
    """Flush one file and request full durability on Darwin when available."""

    try:
        os.fsync(descriptor)
        full_sync = getattr(fcntl, "F_FULLFSYNC", None)
        if platform.system() == "Darwin" and full_sync is not None:
            fcntl.fcntl(descriptor, full_sync)
    except OSError as error:
        raise ArtifactError(
            artifact_id=None,
            field="filesystem",
            invariant="filesystem_must_support_durable_sync",
            detail=str(error),
        ) from error


def _cleanup_capability_probe(root: SafeDirectory, probe_name: str) -> None:
    try:
        probe_descriptor = os.open(
            probe_name,
            DIRECTORY_FLAGS,
            dir_fd=root.fd,
        )
    except FileNotFoundError:
        return
    try:
        root._verify_directory_identity(probe_descriptor)
        for name in _CAPABILITY_PROBE_FILES:
            try:
                os.unlink(name, dir_fd=probe_descriptor)
            except FileNotFoundError:
                pass
    finally:
        os.close(probe_descriptor)
    os.rmdir(probe_name, dir_fd=root.fd)
    os.fsync(root.fd)


def _preflight_filesystem_capabilities(root: SafeDirectory) -> None:
    probe_name = f"capability-probe-{uuid.uuid4().hex}"
    created = False
    failure: ArtifactError | OSError | None = None
    cleanup_failure: ArtifactError | OSError | None = None
    try:
        os.mkdir(probe_name, mode=0o700, dir_fd=root.fd)
        created = True
        os.fsync(root.fd)
        probe_descriptor = os.open(
            probe_name,
            DIRECTORY_FLAGS,
            dir_fd=root.fd,
        )
        with SafeDirectory(
            root.path / probe_name,
            descriptor=probe_descriptor,
            forbidden_identity=root.forbidden_identity,
        ) as probe:
            with probe.exclusive_lock():
                pass
            probe.write_exclusive("source", b"source")
            probe.hard_link_no_replace("source", "linked")
            probe.write_exclusive("existing", b"existing")
            try:
                probe.hard_link_no_replace("source", "existing")
            except ArtifactError as error:
                if error.invariant != "existing_destination_must_have_exact_same_bytes":
                    raise
            else:
                fail(
                    artifact_id=None,
                    field="filesystem.capabilities.hard_link",
                    invariant="hard_link_probe_must_not_replace_existing_file",
                    detail="Hard-link install replaced an existing probe file",
                )
            if probe.read_bytes("existing") != b"existing":
                fail(
                    artifact_id=None,
                    field="filesystem.capabilities.hard_link",
                    invariant="hard_link_probe_must_preserve_existing_file",
                    detail="Hard-link install changed existing probe bytes",
                )
            probe.write_exclusive("replacement", b"replacement")
            probe.replace("replacement", "linked")
            if probe.read_bytes("linked") != b"replacement":
                fail(
                    artifact_id=None,
                    field="filesystem.capabilities.atomic_replace",
                    invariant="atomic_replace_probe_must_publish_source",
                    detail="Atomic replace did not publish the probe source bytes",
                )
    except (ArtifactError, OSError) as error:
        failure = error
    finally:
        if created:
            try:
                _cleanup_capability_probe(root, probe_name)
            except (ArtifactError, OSError) as error:
                cleanup_failure = error
    if failure is not None or cleanup_failure is not None:
        detail = str(failure or cleanup_failure)
        if failure is not None and cleanup_failure is not None:
            detail = f"{detail}; cleanup failed: {cleanup_failure}"
        raise ArtifactError(
            artifact_id=None,
            field="filesystem.capabilities",
            invariant="capability_unavailable",
            detail=detail,
        ) from failure or cleanup_failure


def open_state_root(location: StoreLocation) -> SafeDirectory:
    """Open the same state-root inode resolved at command intake."""

    return SafeDirectory(
        location.state_root,
        expected_identity=location.state_root_identity,
        forbidden_identity=location.candidate_identity,
    )


def create_run_store(location: StoreLocation) -> SafeDirectory:
    """Create the run path component-by-component below a fixed real state root."""

    with open_state_root(location) as root:
        _preflight_filesystem_capabilities(root)
        return root.open_subdirectory(
            f"review-harness/{location.repository_id}/{location.run_id}",
            create=True,
        )


def open_run_store(location: StoreLocation) -> SafeDirectory:
    with open_state_root(location) as root:
        return root.open_subdirectory(
            f"review-harness/{location.repository_id}/{location.run_id}",
            create=False,
        )
