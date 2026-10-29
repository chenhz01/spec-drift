"""Every functional requirement is anchored here on purpose."""

from src.health import health


def test_health_returns_status_json():
    # anchors FR-001
    payload = health()
    assert payload["status"] == "ok"


def test_health_reports_database_connectivity():
    # anchors FR-002
    assert health(database_up=True)["database"] is True
    assert health(database_up=False)["database"] is False
