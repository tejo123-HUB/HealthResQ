from datetime import datetime, timedelta, timezone

from backend.ops.freshness import LIVE, RECENT, STALE, UNRELIABLE, classify_freshness


def test_freshness_boundaries():
    """OPS-08 acceptance criterion: a record >= 24 hours old is labeled UNRELIABLE, and the
    other bands (LIVE < 1h, RECENT < 6h, STALE < 24h) are mutually exclusive."""
    now = datetime.now(timezone.utc)

    assert classify_freshness(now, now=now) == LIVE
    assert classify_freshness(now - timedelta(minutes=59), now=now) == LIVE
    assert classify_freshness(now - timedelta(hours=1, minutes=1), now=now) == RECENT
    assert classify_freshness(now - timedelta(hours=5, minutes=59), now=now) == RECENT
    assert classify_freshness(now - timedelta(hours=6, minutes=1), now=now) == STALE
    assert classify_freshness(now - timedelta(hours=23, minutes=59), now=now) == STALE
    assert classify_freshness(now - timedelta(hours=24), now=now) == UNRELIABLE
    assert classify_freshness(now - timedelta(days=10), now=now) == UNRELIABLE
