"""Non-verbal observations. PRIVACY: only small AGGREGATE numbers produced in the browser are accepted.

Raw video, frames, images, landmarks and per-frame series are never sent or stored. Every model forbids unknown
fields and bounds every value, so the endpoint cannot be used to smuggle frame data."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Level3 = Literal["stable", "moderate", "variable"]
Movement = Literal["low", "moderate", "high"]

# Documented, transparent rules (also shown in the report and docs/multi-agent-interview.md)
MIN_ANALYSED_SECONDS = 20.0
MIN_COVERAGE_PCT = 60.0
MIN_TRACKING_QUALITY_PCT = 50.0
MIN_SAMPLES = 30
MIN_DICTATED_WORDS = 30
MIN_DICTATED_SECONDS = 20.0


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CameraAggregates(_Strict):
    enabled: bool
    total_seconds: float = Field(ge=0, le=14_400)  # time the camera was on
    analysed_seconds: float = Field(ge=0, le=14_400)  # time with a usable pose estimate
    samples: int = Field(ge=0, le=200_000)
    face_visible_pct: float | None = Field(default=None, ge=0, le=100)
    facing_camera_pct: float | None = Field(default=None, ge=0, le=100)
    posture_stability: Level3 | None = None
    movement_level: Movement | None = None
    tracking_quality_pct: float | None = Field(default=None, ge=0, le=100)


class VoiceAggregates(_Strict):
    dictated_words: int = Field(ge=0, le=200_000)
    dictated_seconds: float = Field(ge=0, le=14_400)


class ObservationsIn(_Strict):
    interview_id: int
    camera: CameraAggregates | None = None
    voice: VoiceAggregates | None = None


class ObservationsSaved(BaseModel):
    interview_id: int
    saved: bool = True
    stored: str = "aggregate numbers only (no video, frames or landmarks)"


class Metric(BaseModel):
    key: str
    label: str
    available: bool
    value: str | None = None  # human readable, e.g. "82%" or "Stable"
    note: str | None = None  # why it is unavailable / how to read it


class NonVerbalReport(BaseModel):
    """Observable behaviours only. Deliberately NOT combined into one score and NOT about emotions."""

    camera_used: bool
    voice_used: bool
    observation_coverage_pct: float | None
    tracking_quality_pct: float | None
    metrics: list[Metric]
    unavailable: list[str]
    limitations: list[str]
    rules: list[str]
