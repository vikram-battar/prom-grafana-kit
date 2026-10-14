import os

from monitorkit.alerts import build_prometheus_rule, build_rules
from monitorkit.spec import load_spec

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "service.yaml")
SPEC = load_spec(EXAMPLE)


def test_all_six_alert_families_generated():
    names = sorted(r["alert"] for r in build_rules(SPEC))
    assert names == sorted(
        ["ServiceDown", "HighErrorRate", "HighErrorRate", "HighLatencyP99",
         "HighLatencyP99", "CpuSaturation", "MemorySaturation", "PodRestarting"]
    )


def test_pod_restarting_rule_shape():
    rules = [r for r in build_rules(SPEC) if r["alert"] == "PodRestarting"]
    assert len(rules) == 1
    r = rules[0]
    assert "kube_pod_container_status_restarts_total" in r["expr"]
    assert "> 5" in r["expr"]
    assert r["labels"]["severity"] == "warning"
    assert r["annotations"]["runbook_url"].endswith("/pod-restarts")


def test_rules_reference_spec_job_and_service():
    for rule in build_rules(SPEC):
        assert "checkout-api" in rule["expr"]
        assert rule["labels"]["team"] == "platform"
        assert rule["annotations"]["runbook_url"].startswith("https://runbooks.example.com/")


def test_alert_toggles_skip_families():
    spec = dict(SPEC)
    spec["alerts"] = dict(SPEC["alerts"], latency=False, resources=False, restarts=False)
    names = [r["alert"] for r in build_rules(spec)]
    assert "HighLatencyP99" not in names
    assert "CpuSaturation" not in names
    assert "PodRestarting" not in names
    assert "ServiceDown" in names


def test_manifest_shape():
    manifest = build_prometheus_rule(SPEC, build_rules(SPEC))
    assert manifest["kind"] == "PrometheusRule"
    assert manifest["metadata"]["name"] == "checkout-api-alerts"
    assert manifest["metadata"]["namespace"] == "payments"
    assert len(manifest["spec"]["groups"][0]["rules"]) == 8
