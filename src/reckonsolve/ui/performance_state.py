"""Session-only report scope; independent of Journal and source Prediction."""

from dataclasses import dataclass

from reckonsolve.application.performance import PerformanceRequest


@dataclass(slots=True)
class PerformanceState:
    tag_id: int | None = None
    adaptive_unit: str | None = None
    one_shot_unit: str | None = None
    position: int = 0

    @property
    def request(self) -> PerformanceRequest:
        return PerformanceRequest(self.tag_id, self.adaptive_unit, self.one_shot_unit)

    def reset(self) -> None:
        self.tag_id = None
        self.adaptive_unit = None
        self.one_shot_unit = None
        self.position = 0
