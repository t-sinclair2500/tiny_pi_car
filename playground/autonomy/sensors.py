"""Sonar freshness gate (I2C ownership stays with RobotIO when live)."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass
class SonarSample:
    t_mono: float
    distance_mm: float

    @property
    def age_s(self) -> float:
        return monotonic() - self.t_mono


class SonarGate:
    """Forward ultrasonic as a hard near-field veto, not a mapper."""

    def __init__(
        self,
        hard_stop_mm: float = 250.0,
        warn_mm: float = 450.0,
        max_age_s: float = 0.35,
        invalid_above_mm: float = 4999.0,
    ) -> None:
        self.hard_stop_mm = hard_stop_mm
        self.warn_mm = warn_mm
        self.max_age_s = max_age_s
        self.invalid_above_mm = invalid_above_mm
        self._last: SonarSample | None = None

    def update(self, distance_mm: float, t_mono: float | None = None) -> SonarSample:
        sample = SonarSample(t_mono=t_mono if t_mono is not None else monotonic(), distance_mm=float(distance_mm))
        self._last = sample
        return sample

    def reset(self) -> None:
        self._last = None

    @property
    def last(self) -> SonarSample | None:
        return self._last

    def fresh(self) -> bool:
        if self._last is None:
            return False
        if self._last.age_s > self.max_age_s:
            return False
        if self._last.distance_mm >= self.invalid_above_mm:
            return False
        return True

    def clear_to_move(self) -> bool:
        return self.fresh() and self._last is not None and self._last.distance_mm > self.hard_stop_mm

    def in_warn_zone(self) -> bool:
        return (
            self.fresh()
            and self._last is not None
            and self.hard_stop_mm < self._last.distance_mm <= self.warn_mm
        )
