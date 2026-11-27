"""Reviewed location changes with one recoverable authority at every phase.

The caller drains its reads/closes its SQLite connection and ordinary lease.
This operation then owns both modern-runtime exclusion and legacy file fencing.
No forecast, timestamp, score, migration or backup-success metadata is changed.
"""

import base64
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from reckonsolve.data.journal_location import (
    DATABASE_NAME,
    TARGET_OWNER,
    LocationStore,
    read_json,
    require_uuid,
)
from reckonsolve.data.location_native import (
    FileFence,
    LocationError,
    RuntimeLease,
    atomic_json,
    file_identity,
    validate_local_folder,
)
from reckonsolve.data.relocation_snapshot import (
    digest,
    snapshot,
    verify_image,
    write_image,
)
from reckonsolve.identity import DEVELOPMENT_APPLICATION, STABLE_APPLICATION


@dataclass(frozen=True, slots=True)
class MoveReview:
    source: Path
    destination: Path
    recovery: Path
    move_id: str
    source_identity: tuple[int, int]


@dataclass(frozen=True, slots=True)
class MoveResult:
    destination: Path
    recovery: Path


class RelocationService:
    def __init__(
        self, store: LocationStore, *, checkpoint: Callable[[str], None] | None = None
    ):
        self.store = store
        self.checkpoint = checkpoint or (lambda phase: None)

    def preview(self, folder: Path) -> MoveReview:
        source = self.store.resolve()
        validate_local_folder(source.parent)
        destination_folder = validate_local_folder(folder)
        reserved = (
            self.store.root,
            *(
                self.store.root.parent / identity.application_name
                for identity in (STABLE_APPLICATION, DEVELOPMENT_APPLICATION)
            ),
        )
        if any(destination_folder.is_relative_to(root.resolve()) for root in reserved):
            raise LocationError(
                "Choose a folder outside the application's stable/development settings folders."
            )
        if source.stat().st_file_attributes & 1:
            raise LocationError(
                "The current journal is read-only. Keep its files and resolve that before moving it."
            )
        destination = destination_folder / DATABASE_NAME
        self._unused_destination(destination)
        if shutil.disk_usage(destination_folder).free < source.stat().st_size + 65536:
            raise LocationError(
                "The destination does not have enough free space for the complete journal."
            )
        snapshot(
            source
        )  # Refuse unsupported/invalid archives before any move artifacts.
        move_id = str(uuid4())
        return MoveReview(
            source,
            destination,
            self.store.root / f"journal-recovery-{move_id}.sqlite3",
            move_id,
            file_identity(source),
        )

    @staticmethod
    def _unused_destination(destination: Path) -> None:
        names = [
            destination,
            destination.parent / TARGET_OWNER,
            *(
                Path(str(destination) + suffix)
                for suffix in ("-wal", "-shm", "-journal", ".moved.json")
            ),
        ]
        if any(path.exists() or path.is_symlink() for path in names):
            raise LocationError(
                "This folder contains a journal, prior move notice or reserved journal files. Choose an unused folder; nothing was overwritten."
            )

    def execute(self, review: MoveReview) -> MoveResult:
        with RuntimeLease(self.store.root, exclusive=True):
            # Revalidate reviewed locations after exclusion; do not trust stale UI.
            fresh = self.preview(review.destination.parent)
            if (
                fresh.source != review.source
                or fresh.source_identity != review.source_identity
            ):
                raise LocationError(
                    "The source journal changed since review. Choose the folder again."
                )
            try:
                self._move_locked(review)
            except BaseException:
                # Before durable source protection, authority never left the source.
                # Only reset metadata when fresh admission proves that safe. A
                # protected/ambiguous failure deliberately remains a recovery state.
                state = self.store.state()
                if (
                    state
                    and state.get("move_id") == review.move_id
                    and state["status"] not in {"idle", "complete"}
                    and not review.source.stat().st_file_attributes & 1
                ):
                    self._keep_locked(state)
                raise
        return MoveResult(review.destination, review.recovery)

    def _move_locked(self, review: MoveReview) -> None:
        with FileFence(review.source) as source_fence:
            if source_fence.identity != review.source_identity:
                raise LocationError(
                    "The reviewed source file was replaced. No move was performed."
                )
            image = snapshot(review.source)
            required = len(image) + 65536
            if (
                shutil.disk_usage(self.store.root).free < required
                or shutil.disk_usage(review.destination.parent).free < required * 2
            ):
                raise LocationError(
                    "There is not enough free space for the complete recovery and destination copies."
                )
            notice = self._notice(review)
            raw = review.source.read_bytes()
            state = {
                **self.store.base_state("preparing"),
                "move_id": review.move_id,
                "source": str(review.source),
                "destination": str(review.destination),
                "recovery": str(review.recovery),
                "source_identity": list(source_fence.identity),
                "prior_locator": self.store.locator(),
                "image_sha256": digest(image),
                "raw_sha256": digest(raw),
                "raw_prefix": base64.b64encode(raw[: len(notice)]).decode("ascii"),
                "notice": base64.b64encode(notice).decode("ascii"),
                "sidecars": self._sidecars(review.source),
                "target_identity": None,
            }
            self.store.save_state(state)
            self.checkpoint("preparing")
            claim = {
                "version": 1,
                "identity": self.store.identity,
                "journal_id": self.store.owner()["journal_id"],
                "bootstrap": str(self.store.root),
                "move_id": review.move_id,
            }
            atomic_json(review.destination.parent / TARGET_OWNER, claim, replace=False)
            write_image(review.recovery, image)
            self.checkpoint("recovery_verified")
            write_image(review.destination, image)
            with FileFence(review.destination) as target_fence:
                state.update(
                    status="protected", target_identity=list(target_fence.identity)
                )
                self.store.save_state(state)
                self.checkpoint("copies_verified")
                # The companion notice is installed before durable write protection.
                # It remains readable if interruption precedes the header notice.
                atomic_json(
                    Path(str(review.source) + ".moved.json"),
                    claim
                    | {
                        "destination": str(review.destination),
                        "recovery": str(review.recovery),
                    },
                )
                source_fence.protect()
                self.checkpoint("source_protected")
                source_fence.write_notice(notice)
                self.checkpoint("notice_written")
                state["status"] = "retired"
                self.store.save_state(state)
                self._complete_locked(state)

    def _notice(self, review: MoveReview) -> bytes:
        text = {
            "message": "This Reckonsolve journal moved. Use the updated matching app or CLI. Do not delete this notice or create another journal here.",
            "identity": self.store.identity,
            "journal_id": self.store.owner()["journal_id"],
            "move_id": review.move_id,
            "bootstrap": str(self.store.root),
            "destination": str(review.destination),
            "recovery": str(review.recovery),
        }
        return (
            "RECKONSOLVE JOURNAL MOVED\n" + json.dumps(text, sort_keys=True) + "\n"
        ).encode("utf-8")

    @staticmethod
    def _sidecars(source: Path) -> dict:
        return {
            suffix: digest(Path(str(source) + suffix).read_bytes())
            for suffix in ("-wal", "-journal")
            if Path(str(source) + suffix).exists()
        }

    def _pending(self) -> dict:
        state = self.store.state()
        expected = {
            "version",
            "identity",
            "journal_id",
            "status",
            "move_id",
            "source",
            "destination",
            "recovery",
            "source_identity",
            "prior_locator",
            "image_sha256",
            "raw_sha256",
            "raw_prefix",
            "notice",
            "sidecars",
            "target_identity",
        }
        try:
            if (
                state is None
                or set(state) != expected
                or state["status"] in {"idle", "complete"}
            ):
                raise ValueError("not an actionable pending move")
            require_uuid(state["move_id"])
            for key in ("source", "destination", "recovery"):
                if (
                    not isinstance(state[key], str)
                    or not Path(state[key]).is_absolute()
                ):
                    raise ValueError("invalid move path")
            source, destination, recovery = (
                Path(state[key]) for key in ("source", "destination", "recovery")
            )
            for folder in (source.parent, destination.parent, self.store.root):
                validate_local_folder(folder)
            prior = state["prior_locator"]
            if source != (Path(prior["path"]) if prior else self.store.default):
                raise ValueError("source authority mismatch")
            if (
                recovery
                != self.store.root / f"journal-recovery-{state['move_id']}.sqlite3"
                or destination.name != DATABASE_NAME
                or destination == source
            ):
                raise ValueError("invalid managed paths")
            locator = self.store.locator(allow_missing=True)
            if locator != prior and (
                locator is None
                or locator["move_id"] != state["move_id"]
                or locator["path"] != state["destination"]
            ):
                raise ValueError("changed location authority")
            if tuple(state["source_identity"]) != file_identity(source):
                raise ValueError("source file identity mismatch")
        except (KeyError, TypeError, ValueError) as error:
            raise LocationError(
                f"The interrupted move cannot be verified. Keep all files and the recovery record: {self.store.move_file}"
            ) from error
        return state

    def recovery_action(self) -> str:
        state = self._pending()
        return (
            "finish" if Path(state["source"]).stat().st_file_attributes & 1 else "keep"
        )

    def recover(self, action: str) -> MoveResult | None:
        with RuntimeLease(self.store.root, exclusive=True):
            state = self._pending()
            if action != self.recovery_action():
                raise LocationError(
                    "The recovery state changed. Reopen the recovery review."
                )
            if action == "keep":
                self._keep_locked(state)
                return None
            with FileFence(Path(state["source"]), attributes_only=True):
                self._verify_protection(state)
                with FileFence(Path(state["destination"])) as target:
                    if list(target.identity) != state["target_identity"]:
                        raise LocationError(
                            "The destination file was replaced. Keep both copies for recovery."
                        )
                    self._complete_locked(state)
            return MoveResult(Path(state["destination"]), Path(state["recovery"]))

    def _verify_protection(self, state: dict) -> None:
        if (
            state["status"] not in {"protected", "retired"}
            or state["target_identity"] is None
        ):
            raise LocationError(
                "The source protection/copy sequence is uncertain. Keep every file for recovery."
            )
        source = Path(state["source"])
        if not source.stat().st_file_attributes & 1:
            raise LocationError(
                "The original pathname is no longer write-protected. Recovery stopped."
            )
        raw = source.read_bytes()
        try:
            original = base64.b64decode(state["raw_prefix"], validate=True)
            notice = base64.b64decode(state["notice"], validate=True)
        except (ValueError, TypeError) as error:
            raise LocationError(
                "The source protection certificate is malformed."
            ) from error
        known_retirement = len(raw) <= len(notice) and notice.startswith(raw)
        known_original = (
            len(raw) >= len(original)
            and len(notice) == len(original)
            and digest(original + raw[len(original) :]) == state["raw_sha256"]
            and not any(
                value not in (a, b)
                for value, a, b in zip(
                    raw[: len(original)], original, notice, strict=True
                )
            )
        )
        if (
            not (known_retirement or known_original)
            or self._sidecars(source) != state["sidecars"]
        ):
            raise LocationError(
                "The original location changed outside the move. Keep all files; no copy was chosen."
            )
        claim = read_json(Path(str(source) + ".moved.json"))
        if (
            claim.get("move_id") != state["move_id"]
            or claim.get("journal_id") != state["journal_id"]
        ):
            raise LocationError("The old-path protection notice could not be verified.")

    def _complete_locked(self, state: dict) -> None:
        destination, recovery = Path(state["destination"]), Path(state["recovery"])
        verify_image(recovery, state["image_sha256"])
        verify_image(destination, state["image_sha256"])
        self.store._check_target_owner(destination.parent)
        claim = read_json(destination.parent / TARGET_OWNER)
        if claim.get("move_id") != state["move_id"]:
            raise LocationError(
                "The destination reservation changed. Recovery stopped."
            )
        owner = self.store.owner()
        atomic_json(self.store.identity_file, {**owner, "relocated": True})
        atomic_json(
            self.store.locator_file,
            {
                "version": 1,
                "identity": self.store.identity,
                "journal_id": owner["journal_id"],
                "move_id": state["move_id"],
                "path": str(destination),
            },
        )
        self.checkpoint("locator_installed")
        installed = self.store.verify_installed_path(state["move_id"])
        if installed != destination:
            raise LocationError(
                "The installed location points to another file. Recovery is required."
            )
        verify_image(installed, state["image_sha256"])
        self.store.save_state(
            {**self.store.base_state("complete"), "move_id": state["move_id"]}
        )
        self.checkpoint("complete")

    def _keep_locked(self, state: dict) -> None:
        source = Path(state["source"])
        if source.stat().st_file_attributes & 1:
            raise LocationError(
                "The source is already protected. Reopen Reckonsolve to finish recovery."
            )
        with FileFence(source) as fence:
            if list(fence.identity) != state["source_identity"]:
                raise LocationError("The source was replaced. Recovery stopped.")
            snapshot(source)  # Keep fresh source facts, including later legacy writes.
            prior = state["prior_locator"]
            if self.store.locator(allow_missing=True) != prior:
                raise LocationError("The active location changed. Recovery stopped.")
            self.store.save_state(
                {**self.store.base_state("complete"), "move_id": prior["move_id"]}
                if prior
                else self.store.base_state("idle")
            )
