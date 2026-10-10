"""Generate a Grafana dashboard JSON from a service spec."""

import hashlib


def _uid(service):
    return "svc-" + hashlib.sha1(service.encode()).hexdigest()[:12]


def _panel(panel_id, title, exprs, y_unit="short", ptype="timeseries", grid_y=8, grid_x=12, x=0, y=0):
    targets = [{"expr": e, "refId": chr(65 + i), "datasource": {"type": "prometheus"}} for i, e in enumerate(exprs)]
    return {
        "id": panel_id,
        "type": ptype,
        "title": title,
        "datasource": {"type": "prometheus"},
        "gridPos": {"h": grid_y, "w": grid_x, "x": x, "y": y},
        "fieldConfig": {
            "defaults": {"unit": y_unit, "custom": {}},
            "overrides": [],
        },
        "options": {},
        "targets": targets,
    }


def build_dashboard(spec):
    """Return a Grafana dashboard dict for the given spec."""
    svc = spec["service"]
    ns = spec["namespace"]
    job = spec["job"]
    ds = spec["dashboard"]["datasource"]
    pod_sel = 'namespace="%s",pod=~"%s-.*"' % (ns, svc)

    panels = [
        _panel(
            1,
            "Request rate",
            ['sum(rate(http_requests_total{job="%s"}[5m]))' % job],
            y_unit="reqps",
            x=0,
            y=0,
        ),
        _panel(
            2,
            "Error rate (5xx %)",
            [
                '100 * sum(rate(http_requests_total{job="%s",code=~"5.."}[5m]))'
                ' / sum(rate(http_requests_total{job="%s"}[5m]))' % (job, job)
            ],
            y_unit="percent",
            x=12,
            y=0,
        ),
        _panel(
            3,
            "Latency p50 / p95 / p99",
            [
                'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{job="%s"}[5m])) by (le))' % job,
                'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="%s"}[5m])) by (le))' % job,
                'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{job="%s"}[5m])) by (le))' % job,
            ],
            y_unit="s",
            x=0,
            y=8,
        ),
        _panel(
            4,
            "CPU usage vs requests",
            [
                'sum(rate(container_cpu_usage_seconds_total{%s}[5m]))' % pod_sel,
                'sum(kube_pod_container_resource_requests{%s,resource="cpu"})' % pod_sel,
            ],
            x=12,
            y=8,
        ),
        _panel(
            5,
            "Memory working set vs requests",
            [
                'sum(container_memory_working_set_bytes{%s})' % pod_sel,
                'sum(kube_pod_container_resource_requests{%s,resource="memory"})' % pod_sel,
            ],
            y_unit="bytes",
            x=0,
            y=16,
        ),
        _panel(
            6,
            "Pod restarts (1h)",
            ['sum(increase(kube_pod_container_status_restarts_total{%s}[1h]))' % pod_sel],
            ptype="stat",
            grid_x=12,
            x=12,
            y=16,
        ),
    ]

    return {
        "title": "%s - service overview" % svc,
        "uid": _uid(svc),
        "schemaVersion": 39,
        "version": 1,
        "tags": ["generated", "prom-grafana-kit", spec["team"]],
        "timezone": "browser",
        "templating": {
            "list": [
                {
                    "name": "datasource",
                    "type": "datasource",
                    "query": "prometheus",
                    "current": {"text": ds, "value": ds},
                },
                {
                    "name": "namespace",
                    "type": "query",
                    "datasource": {"type": "prometheus"},
                    "query": "label_values(kube_pod_info, namespace)",
                    "current": {"text": ns, "value": ns},
                },
            ]
        },
        "panels": panels,
    }
