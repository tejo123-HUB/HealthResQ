from datetime import datetime, timedelta, timezone

LIVE = "LIVE"
RECENT = "RECENT"
STALE = "STALE"
UNRELIABLE = "UNRELIABLE"


def classify_freshness(observed_at: datetime, *, now: datetime | None = None) -> str:
    """OPS-08: classify a record's freshness from its `observed_at` age. Computed at read time —
    never stored — so the label always reflects the age as of the request, not as of ingestion."""
    reference = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    age = reference - observed_at

    if age < timedelta(hours=1):
        return LIVE
    if age < timedelta(hours=6):
        return RECENT
    if age < timedelta(hours=24):
        return STALE
    return UNRELIABLE
