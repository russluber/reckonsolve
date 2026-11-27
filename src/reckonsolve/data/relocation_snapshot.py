"""Checked complete relocation images; no migrations, repairs or score writes."""

import hashlib
import os
from pathlib import Path

from .database import Database
from .location_native import LocationError


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot(path: Path) -> bytes:
    database = Database.open_readonly(path)
    try:
        with database.read_snapshot() as connection:
            checks = connection.execute("PRAGMA integrity_check").fetchall()
            if [row[0] for row in checks] != ["ok"]:
                raise LocationError("The journal failed its integrity check.")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise LocationError("The journal failed its foreign-key check.")
            return connection.serialize()
    finally:
        database.close()


def write_image(path: Path, image: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(image)
        stream.flush()
        os.fsync(stream.fileno())
    verify_image(path, digest(image))


def verify_image(path: Path, expected: str) -> None:
    if digest(path.read_bytes()) != expected or digest(snapshot(path)) != expected:
        raise LocationError(f"The complete journal copy could not be verified: {path}")
