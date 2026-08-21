import numpy as np
import pandas as pd

from backend.intelligence.anomaly.detection import detect_anomaly
from backend.intelligence.models import Severity
from backend.intelligence.risk.stockout import classify_severity, first_stockout_day, project_stock


def test_classify_severity_thresholds():
    assert classify_severity(None) == Severity.NORMAL
    assert classify_severity(1) == Severity.CRITICAL
    assert classify_severity(2) == Severity.CRITICAL
    assert classify_severity(3) == Severity.HIGH
    assert classify_severity(7) == Severity.WATCH
    assert classify_severity(8) == Severity.NORMAL


def test_classify_severity_deterministic_same_input():
    """INT-04's acceptance criterion: the same input never yields two different severities."""
    for days in (None, 1, 2, 3, 7, 8, 30):
        assert classify_severity(days) == classify_severity(days)


def test_project_stock_and_first_stockout_day():
    projected = project_stock(current_stock=100, expected_incoming=np.zeros(10), forecast_consumption=np.full(10, 20))
    assert first_stockout_day(projected) == 5  # 100 - 20*5 = 0


def test_first_stockout_day_none_when_never_reached():
    projected = project_stock(current_stock=1000, expected_incoming=np.zeros(10), forecast_consumption=np.full(10, 1))
    assert first_stockout_day(projected) is None


def test_detect_anomaly_flags_surge():
    series = pd.Series([100.0] * 14 + [400.0] * 3)
    anomaly = detect_anomaly(series)
    assert anomaly is not None
    assert set(anomaly.keys()) == {"baseline", "recent", "percentChange"}
    assert anomaly["percentChange"] > 0


def test_detect_anomaly_none_when_stable():
    series = pd.Series([100.0] * 20)
    assert detect_anomaly(series) is None
