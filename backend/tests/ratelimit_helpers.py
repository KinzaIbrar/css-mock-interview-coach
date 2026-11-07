"""Helpers that reproduce Google's real 429 payloads (shape captured from a live response; no secrets)."""

from tests.fakes import FakeApiError

DAILY = "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
PER_MINUTE = "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"


def quota_details(*, quota_id: str, retry_delay: str | None = "17244s", model: str = "gemini-3.8-flash") -> dict:
    """The body Google returns for a 429: QuotaFailure (which quota) + RetryInfo (how long to wait)."""
    details: list[dict] = [
        {"@type": "type.googleapis.com/google.rpc.Help", "links": [{"description": "Learn more", "url": "https://ai.google.dev/gemini-api/docs/rate-limits"}]},
        {
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [
                {
                    "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                    "quotaId": quota_id,
                    "quotaDimensions": {"location": "global", "model": model},
                    "quotaValue": "20",
                }
            ],
        },
    ]
    if retry_delay is not None:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay})
    return {"error": {"code": 429, "message": "You exceeded your current quota", "status": "RESOURCE_EXHAUSTED", "details": details}}


class RateLimitError(FakeApiError):
    """A 429 carrying Google's structured details (like google.genai.errors.ClientError.details)."""

    def __init__(self, details: dict | None, message: str = "You exceeded your current quota"):
        super().__init__(429, message)
        self.details = details
