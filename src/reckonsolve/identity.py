"""Stable application identities for release-compatible and development runs."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApplicationIdentity:
    """Names that keep one application channel visibly and physically distinct."""

    application_name: str
    window_title: str


STABLE_APPLICATION = ApplicationIdentity(
    application_name="Reckonsolve",
    window_title="Reckonsolve",
)

DEVELOPMENT_APPLICATION = ApplicationIdentity(
    application_name="Reckonsolve Dev",
    window_title="Reckonsolve Dev",
)
