import json
import os

import yaml

from monitorkit.alerts import build_prometheus_rule, build_rules
from monitorkit.dashboards import build_dashboard
from monitorkit.lint import lint_alerts, lint_dashboard
from monitorkit.spec import load_spec

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "service.yaml")
SPEC = load_spec(EXAMPLE)


def _write_alerts(tmp_path, manifest):
    p = tmp_path / "alerts.yaml"
    p.write_text(yaml.safe_dump(manifest))
    return str(p)


def _write_dashboard(tmp_path, dash):
    p = tmp_path / "dash.json"
    p.write_text(json.dumps(dash))
    return str(p)


def test_generated_alerts_are_clean(tmp_path):
    findings = lint_alerts(_write_alerts(tmp_path, build_prometheus_rule(SPEC, build_rules(SPEC))))
    errors = [f for f in findings if f["level"] == "error"]
    assert errors == [], errors


def test_generated_dashboard_is_clean(tmp_path):
    findings = lint_dashboard(_write_dashboard(tmp_path, build_dashboard(SPEC)))
    errors = [f for f in findings if f["level"] == "error"]
    assert errors == [], errors


def test_duplicate_alert_same_severity_is_error(tmp_path):
    rules = build_rules(SPEC)
    dupe = dict(rules[0])
    rules.append(dupe)  # same name + same severity twice
    findings = lint_alerts(_write_alerts(tmp_path, build_prometheus_rule(SPEC, rules)))
    assert any(f["check"] == "duplicate-alert" and f["level"] == "error" for f in findings)


def test_same_name_different_severity_is_fine(tmp_path):
    # HighErrorRate exists as warning + critical by design; that must not flag
    findings = lint_alerts(_write_alerts(tmp_path, build_prometheus_rule(SPEC, build_rules(SPEC))))
    assert not any(f["check"] == "duplicate-alert" for f in findings)


def test_missing_runbook_is_error(tmp_path):
    rules = build_rules(SPEC)
    del rules[0]["annotations"]["runbook_url"]
    findings = lint_alerts(_write_alerts(tmp_path, build_prometheus_rule(SPEC, rules)))
    assert any(f["check"] == "missing-annotation" for f in findings if f["level"] == "error")


def test_unbalanced_parens_is_error(tmp_path):
    rules = build_rules(SPEC)
    rules[0]["expr"] = 'sum(rate(http_requests_total{job="x"}[5m]) > 0.01'
    findings = lint_alerts(_write_alerts(tmp_path, build_prometheus_rule(SPEC, rules)))
    assert any(f["check"] == "unbalanced-parens" for f in findings if f["level"] == "error")


def test_dashboard_without_uid_is_error(tmp_path):
    dash = build_dashboard(SPEC)
    del dash["uid"]
    findings = lint_dashboard(_write_dashboard(tmp_path, dash))
    assert any(f["check"] == "missing-uid" for f in findings if f["level"] == "error")


def test_broken_yaml_is_error(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("spec:\n  groups: [unclosed")
    findings = lint_alerts(str(p))
    assert any(f["check"] == "yaml-parse" for f in findings if f["level"] == "error")
