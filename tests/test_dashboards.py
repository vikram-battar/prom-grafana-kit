import json
import os

from monitorkit.dashboards import build_dashboard
from monitorkit.spec import load_spec

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "service.yaml")
SPEC = load_spec(EXAMPLE)


def test_dashboard_structure():
    dash = build_dashboard(SPEC)
    assert dash["title"] == "checkout-api - service overview"
    assert dash["uid"].startswith("svc-")
    assert len(dash["panels"]) == 6
    assert json.dumps(dash)  # must be JSON-serializable


def test_panel_ids_unique_and_queries_present():
    dash = build_dashboard(SPEC)
    ids = [p["id"] for p in dash["panels"]]
    assert len(ids) == len(set(ids))
    for panel in dash["panels"]:
        assert panel["title"]
        for target in panel["targets"]:
            assert "checkout-api" in target["expr"] or "payments" in target["expr"]


def test_datasource_template_variable():
    dash = build_dashboard(SPEC)
    names = [v["name"] for v in dash["templating"]["list"]]
    assert "datasource" in names
    assert "namespace" in names
