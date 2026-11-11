"""Explicit workspace origins, without a general navigation history stack."""

from dataclasses import dataclass, field
from enum import StrEnum


class Route(StrEnum):
    JOURNAL = "Journal"
    NEW = "New Prediction"
    DETAIL = "Prediction Detail"
    PERFORMANCE = "Performance"
    SETTINGS = "Settings"


@dataclass(frozen=True, slots=True)
class Destination:
    route: Route = Route.JOURNAL
    prediction_id: int | None = None


@dataclass(slots=True)
class WorkspaceState:
    current: Destination = field(default_factory=Destination)
    new_origin: Destination = field(default_factory=Destination)
    performance_origin: Destination = field(default_factory=Destination)
    settings_origin: Destination = field(default_factory=Destination)

    def enter(self, destination: Destination, *, remember_source: bool = True) -> None:
        if remember_source and destination.route is not self.current.route:
            if destination.route is Route.NEW:
                self.new_origin = self.current
            elif destination.route is Route.PERFORMANCE:
                self.performance_origin = self.current
            elif destination.route is Route.SETTINGS:
                self.settings_origin = self.current
        self.current = destination

    def back_destination(self) -> Destination:
        match self.current.route:
            case Route.NEW:
                return self.new_origin
            case Route.PERFORMANCE:
                return self.performance_origin
            case Route.SETTINGS:
                return self.settings_origin
            case _:
                return Destination()
