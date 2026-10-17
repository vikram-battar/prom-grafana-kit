import os

import pytest

from monitorkit.spec import load_spec

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "service.yaml")


def test_example_spec_loads_with_defaults():
    spec = load_spec(EXAMPLE)
    assert spec["service"] == "checkout-api"
    assert spec["team"] == "platform"
    assert spec["alerts"]["latency"] is True
    assert spec["dashboard"]["datasource"] == "Prometheus"
    assert spec["evaluation"]["for_warn"] == "10m"


def test_missing_required_field_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("service: x\n")  # namespace and job missing
    with pytest.raises(ValueError, match="namespace"):
        load_spec(str(p))


def test_warn_must_be_below_critical(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(
        "service: x\nnamespace: y\njob: z\n"
        "error_budget:\n  error_rate_warn: 0.10\n  error_rate_critical: 0.05\n"
    )
    with pytest.raises(ValueError, match="error_rate_warn"):
        load_spec(str(p))


def test_runbook_base_url_must_be_http(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("service: x\nnamespace: y\njob: z\nrunbook_base_url: ftp://example.com\n")
    with pytest.raises(ValueError, match="runbook_base_url"):
        load_spec(str(p))


def test_runbook_base_url_http_ok(tmp_path):
    p = tmp_path / "ok.yaml"
    p.write_text("service: x\nnamespace: y\njob: z\nrunbook_base_url: http://internal/runbooks\n")
    spec = load_spec(str(p))
    assert spec["runbook_base_url"] == "http://internal/runbooks"
