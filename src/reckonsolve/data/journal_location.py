"""Fixed identity bootstrap and strict active-journal metadata.

These files are outside SQLite and outside presentation preferences. A missing
configured journal is an error, never an invitation to initialize another one.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from .location_native import (
    LocationError,
    RuntimeLease,
    atomic_json,
    validate_journal_file,
    validate_local_folder,
)

DATABASE_NAME = "reckonsolve.sqlite3"
TARGET_OWNER = "reckonsolve-journal.json"


def _present(path: Path) -> bool:
    """Distinguish absent metadata from inaccessible metadata; never fall back."""
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise LocationError(
            f"Journal location information is inaccessible: {path}"
        ) from error
    return True


def _unique_fields(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate location field")
        value[key] = item
    return value


def read_json(path: Path) -> dict:
    try:
        if path.is_symlink():
            raise ValueError("linked metadata")
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields
        )
        if not isinstance(value, dict):
            raise TypeError("expected an object")
        return value
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        raise LocationError(
            f"Journal location information could not be verified: {path}. Keep the existing files for recovery."
        ) from error


def require_uuid(value) -> str:
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("invalid journal/move identity")
    return value


class MoveRecoveryRequired(LocationError):
    def __init__(self, store: "LocationStore", state: dict) -> None:
        self.store, self.state = store, state
        super().__init__(
            f"A journal move needs recovery. No journal was opened. Location information: {store.move_file}"
        )


class LocationStore:
    def __init__(self, root: Path, identity: str) -> None:
        self.root = root.resolve()
        self.identity = identity
        self.identity_file = self.root / "journal-identity.json"
        self.locator_file = self.root / "journal-location.json"
        self.move_file = self.root / "journal-move.json"
        self.default = self.root / DATABASE_NAME

    def initialize(self) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        if not _present(self.identity_file):
            try:
                atomic_json(
                    self.identity_file,
                    {
                        "version": 1,
                        "identity": self.identity,
                        "journal_id": str(uuid4()),
                        "initialized": False,
                        "relocated": False,
                    },
                    replace=False,
                )
            except OSError:
                if not _present(self.identity_file):
                    raise
                # Another ordinary runtime may have atomically installed it.
        return self.owner()

    def owner(self) -> dict:
        value = read_json(self.identity_file)
        try:
            if set(value) != {
                "version",
                "identity",
                "journal_id",
                "initialized",
                "relocated",
            }:
                raise ValueError("unknown identity fields")
            if (
                type(value["version"]) is not int
                or value["version"] != 1
                or value["identity"] != self.identity
            ):
                raise ValueError("wrong identity")
            require_uuid(value["journal_id"])
            if (
                type(value["initialized"]) is not bool
                or type(value["relocated"]) is not bool
            ):
                raise ValueError("invalid identity state")
        except (KeyError, TypeError, ValueError) as error:
            raise LocationError(
                f"The journal identity could not be verified: {self.identity_file}"
            ) from error
        return value

    def locator(self, *, allow_missing: bool = False) -> dict | None:
        if not _present(self.locator_file):
            if self.owner()["relocated"] and not allow_missing:
                raise LocationError(
                    f"The active journal location record is missing: {self.locator_file}. No empty replacement was created."
                )
            return None
        value = read_json(self.locator_file)
        try:
            if set(value) != {"version", "identity", "journal_id", "move_id", "path"}:
                raise ValueError("unknown location fields")
            if (
                type(value["version"]) is not int
                or value["version"] != 1
                or value["identity"] != self.identity
                or value["journal_id"] != self.owner()["journal_id"]
            ):
                raise ValueError("wrong journal identity")
            require_uuid(value["move_id"])
            if (
                not isinstance(value["path"], str)
                or not Path(value["path"]).is_absolute()
            ):
                raise ValueError("invalid journal path")
        except (KeyError, TypeError, ValueError) as error:
            raise LocationError(
                f"The active journal location could not be verified: {self.locator_file}"
            ) from error
        return value

    def state(self) -> dict | None:
        if not _present(self.move_file):
            return None
        state = read_json(self.move_file)
        if (
            type(state.get("version")) is not int
            or state.get("version") != 1
            or state.get("identity") != self.identity
            or state.get("journal_id") != self.owner()["journal_id"]
            or state.get("status")
            not in ("idle", "preparing", "protected", "retired", "complete")
        ):
            raise LocationError(
                f"The journal move state is not recognized: {self.move_file}"
            )
        return state

    def resolve(self) -> Path:
        state = self.state()
        if state is not None and state["status"] not in {"idle", "complete"}:
            raise MoveRecoveryRequired(self, state)
        owner, locator = self.owner(), self.locator()
        if locator is None:
            path = self.default
            if owner["initialized"] and not path.is_file():
                raise LocationError(
                    f"The existing journal is missing: {path}. Restore its backup; no replacement was created."
                )
            self._check_target_owner(path.parent, allow_missing=True)
            if path.exists() or path.is_symlink():
                validate_journal_file(path)
            return path
        if (
            state is None
            or state["status"] != "complete"
            or state.get("move_id") != locator["move_id"]
        ):
            raise LocationError(
                "The journal location and completion record disagree. Keep all files for recovery."
            )
        return self._configured_path(locator)

    def verify_installed_path(self, move_id: str) -> Path:
        """Re-resolve a just-installed locator while the move lease is exclusive.

        Ordinary resolve still refuses the pending phase. Only the completing
        operation can verify the intended path before recording completion.
        """
        locator = self.locator()
        state = self.state()
        if (
            locator is None
            or state is None
            or locator["move_id"] != move_id
            or state.get("move_id") != move_id
            or state["status"] not in {"protected", "retired"}
        ):
            raise LocationError(
                "The installed journal location does not match the pending move."
            )
        return self._configured_path(locator)

    def _configured_path(self, locator: dict) -> Path:
        path = Path(locator["path"])
        validate_local_folder(path.parent)
        if not path.is_file():
            raise LocationError(
                f"The configured journal is unavailable: {path}. Reconnect its drive or restore its backup; no replacement was created."
            )
        self._check_target_owner(path.parent)
        if read_json(path.parent / TARGET_OWNER).get("move_id") != locator["move_id"]:
            raise LocationError(
                "The journal folder belongs to a different move. Keep the location files for recovery."
            )
        validate_journal_file(path)
        return path

    def _check_target_owner(self, folder: Path, *, allow_missing: bool = False) -> None:
        path = folder / TARGET_OWNER
        if allow_missing and not _present(path):
            return
        owner = read_json(path)
        if (
            set(owner) != {"version", "identity", "journal_id", "bootstrap", "move_id"}
            or type(owner.get("version")) is not int
            or owner.get("version") != 1
            or owner.get("identity") != self.identity
            or owner.get("journal_id") != self.owner()["journal_id"]
            or owner.get("bootstrap") != str(self.root)
        ):
            raise LocationError(
                f"This folder belongs to another journal or application identity: {folder}"
            )

    def mark_initialized(self) -> None:
        owner = self.owner()
        if not owner["initialized"]:
            atomic_json(self.identity_file, {**owner, "initialized": True})

    def save_state(self, state: dict) -> None:
        atomic_json(self.move_file, state)

    def base_state(self, status: str) -> dict:
        return {
            "version": 1,
            "identity": self.identity,
            "journal_id": self.owner()["journal_id"],
            "status": status,
        }


@dataclass(slots=True)
class RuntimeLocation:
    database_path: Path
    presentation_path: Path
    store: LocationStore | None = None
    lease: RuntimeLease | None = None
    allow_create: bool = True

    def close(self) -> None:
        if self.lease is not None:
            self.lease.close()
            self.lease = None

    def resume(self) -> None:
        if self.store is not None:
            self.lease = RuntimeLease(self.store.root)
            try:
                if self.store.resolve() != self.database_path:
                    raise LocationError(
                        "The active journal changed. Restart Reckonsolve before continuing."
                    )
            except BaseException:
                self.close()
                raise


def open_location(root: Path, identity: str) -> RuntimeLocation:
    store = LocationStore(root, identity)
    lease = RuntimeLease(store.root)
    try:
        store.initialize()
        path = store.resolve()
        return RuntimeLocation(
            path,
            store.root / "presentation.ini",
            store,
            lease,
            allow_create=not path.exists() and not store.owner()["initialized"],
        )
    except BaseException:
        lease.close()
        raise
