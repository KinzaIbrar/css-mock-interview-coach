"""Non-verbal observations: store browser-computed AGGREGATES and turn them into a transparent, rule-based report.

No video, frames or landmarks are ever received (see schemas/observations.py). There is deliberately no combined
"confidence"/"personality"/emotion score: only observable behaviours, each shown only when the tracking was good
enough, otherwise as "Not enough data".
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.user import User
from app.schemas.observations import (
    MIN_ANALYSED_SECONDS,
    MIN_COVERAGE_PCT,
    MIN_DICTATED_SECONDS,
    MIN_DICTATED_WORDS,
    MIN_SAMPLES,
    MIN_TRACKING_QUALITY_PCT,
    Metric,
    NonVerbalReport,
    ObservationsIn,
    ObservationsSaved,
)
from app.services.common import get_owned_interview

RULES = [
    f"Camera metrics are shown only if at least {MIN_ANALYSED_SECONDS:.0f}s and {MIN_SAMPLES} samples were analysed, "
    f"the pose was usable for at least {MIN_COVERAGE_PCT:.0f}% of the time the camera was on, and tracking quality "
    f"was at least {MIN_TRACKING_QUALITY_PCT:.0f}%.",
    "Face visible / facing camera are percentages of analysed samples; head direction is estimated from face landmarks.",
    "Posture stability and movement come from how much the shoulder/head position varied; they describe motion, not skill.",
    f"Speaking pace is shown only after at least {MIN_DICTATED_WORDS} dictated words over {MIN_DICTATED_SECONDS:.0f}s; "
    "it counts dictated (spoken) answers only, not typed ones.",
    "No emotion, confidence, honesty or personality is inferred, and no single combined score is produced.",
]
LIMITATIONS = [
    "These are rough, observable indicators from a webcam in your browser; lighting, camera angle and distance affect them.",
    "They are not an assessment of your answers or of your character and do not affect the verbal score.",
    "Only summary numbers are stored. Video and images never leave your device.",
]


def save(db: Session, user: User, req: ObservationsIn) -> ObservationsSaved:
    interview = get_owned_interview(db, user, req.interview_id)
    if interview.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "Interview is already completed")
    data = req.model_dump(exclude={"interview_id"}, exclude_none=True)
    interview.observations = data or None
    db.commit()
    return ObservationsSaved(interview_id=interview.id)


def build_report(observations: dict | None) -> NonVerbalReport | None:
    if not observations:
        return None
    cam = observations.get("camera") or {}
    voice = observations.get("voice") or {}
    camera_used = bool(cam.get("enabled")) and cam.get("total_seconds", 0) > 0
    voice_used = bool(voice) and voice.get("dictated_words", 0) > 0
    if not camera_used and not voice_used:
        return None

    metrics: list[Metric] = []
    unavailable: list[str] = []
    coverage = tracking = None
    if camera_used:
        total = cam.get("total_seconds", 0.0)
        analysed = cam.get("analysed_seconds", 0.0)
        coverage = round(100 * analysed / total, 1) if total > 0 else 0.0
        tracking = cam.get("tracking_quality_pct")
        reliable = (
            analysed >= MIN_ANALYSED_SECONDS
            and cam.get("samples", 0) >= MIN_SAMPLES
            and coverage >= MIN_COVERAGE_PCT
            and tracking is not None
            and tracking >= MIN_TRACKING_QUALITY_PCT
        )
        specs = [
            ("face_visible", "Face visible", cam.get("face_visible_pct"), lambda v: f"{v:.0f}% of the time"),
            ("facing_camera", "Facing the camera", cam.get("facing_camera_pct"), lambda v: f"{v:.0f}% of the time"),
            ("posture_stability", "Posture stability", cam.get("posture_stability"), lambda v: str(v).capitalize()),
            ("movement", "Movement level", cam.get("movement_level"), lambda v: str(v).capitalize()),
        ]
        for key, label, value, fmt in specs:
            if reliable and value is not None:
                metrics.append(Metric(key=key, label=label, available=True, value=fmt(value)))
            else:
                metrics.append(Metric(key=key, label=label, available=False, note="Not enough data"))
                unavailable.append(label)
    else:
        unavailable.append("Camera metrics (camera was not used)")

    if voice_used:
        words, secs = voice.get("dictated_words", 0), voice.get("dictated_seconds", 0.0)
        if words >= MIN_DICTATED_WORDS and secs >= MIN_DICTATED_SECONDS:
            metrics.append(Metric(key="speaking_pace", label="Speaking pace (dictated answers)", available=True,
                                  value=f"{words / secs * 60:.0f} words/min", note="Roughly 110-160 words/min is typical for clear speech."))
        else:
            metrics.append(Metric(key="speaking_pace", label="Speaking pace (dictated answers)", available=False, note="Not enough data"))
            unavailable.append("Speaking pace")
    return NonVerbalReport(
        camera_used=camera_used,
        voice_used=voice_used,
        observation_coverage_pct=coverage,
        tracking_quality_pct=tracking,
        metrics=metrics,
        unavailable=unavailable,
        limitations=LIMITATIONS,
        rules=RULES,
    )
