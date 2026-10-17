"""Load and validate the service spec YAML."""

import yaml


REQUIRED_FIELDS = ["service", "namespace", "job"]


def load_spec(path):
    """Read a spec file, apply defaults, validate, return dict."""
    with open(path) as f:
        data = yaml.safe_load(f) or {}

    for field in REQUIRED_FIELDS:
        if not data.get(field):
            raise ValueError("spec is missing required field: %s" % field)

    data.setdefault("team", "platform")
    data.setdefault("metrics_path", "/metrics")
    data.setdefault("runbook_base_url", "https://runbooks.example.com")

    eb = data.setdefault("error_budget", {})
    eb.setdefault("error_rate_warn", 0.01)
    eb.setdefault("error_rate_critical", 0.05)

    lat = data.setdefault("latency", {})
    lat.setdefault("p99_warn_ms", 500)
    lat.setdefault("p99_critical_ms", 1000)

    res = data.setdefault("resources", {})
    res.setdefault("cpu_warn", 0.85)
    res.setdefault("memory_warn", 0.90)

    rst = data.setdefault("restarts", {})
    rst.setdefault("warn", 5)

    ev = data.setdefault("evaluation", {})
    ev.setdefault("for_warn", "10m")
    ev.setdefault("for_critical", "5m")

    alerts = data.setdefault("alerts", {})
    for key in ("target_down", "error_budget", "latency", "resources", "restarts"):
        alerts.setdefault(key, True)

    dash = data.setdefault("dashboard", {})
    dash.setdefault("datasource", "Prometheus")

    if data["error_budget"]["error_rate_warn"] >= data["error_budget"]["error_rate_critical"]:
        raise ValueError("error_rate_warn must be lower than error_rate_critical")
    if data["latency"]["p99_warn_ms"] >= data["latency"]["p99_critical_ms"]:
        raise ValueError("p99_warn_ms must be lower than p99_critical_ms")

    url = data["runbook_base_url"]
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("runbook_base_url must start with http:// or https://, got %r" % url)

    return data
