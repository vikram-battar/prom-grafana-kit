"""Generate a PrometheusRule manifest from a service spec."""

RUNBOOK_PATHS = {
    "ServiceDown": "/service-down",
    "HighErrorRate": "/high-error-rate",
    "HighLatencyP99": "/high-latency",
    "CpuSaturation": "/cpu-saturation",
    "MemorySaturation": "/memory-saturation",
    "PodRestarting": "/pod-restarts",
}


def _rule(name, expr, severity, for_, summary, description, spec):
    runbook = spec["runbook_base_url"].rstrip("/") + RUNBOOK_PATHS[name]
    return {
        "alert": name,
        "expr": expr,
        "for": for_,
        "labels": {"severity": severity, "team": spec["team"], "service": spec["service"]},
        "annotations": {
            "summary": summary,
            "description": description,
            "runbook_url": runbook,
        },
    }


def build_rules(spec):
    """Return a list of alert rule dicts for the given spec."""
    svc = spec["service"]
    ns = spec["namespace"]
    job = spec["job"]
    ev = spec["evaluation"]
    pod_sel = 'namespace="%s",pod=~"%s-.*"' % (ns, svc)
    rules = []

    if spec["alerts"]["target_down"]:
        rules.append(
            _rule(
                "ServiceDown",
                'up{job="%s"} == 0' % job,
                "critical",
                "5m",
                "No %s targets are up" % svc,
                "Prometheus has not scraped any %s target for 5 minutes. "
                "Service may be down or ServiceMonitor misconfigured." % svc,
                spec,
            )
        )

    if spec["alerts"]["error_budget"]:
        eb = spec["error_budget"]
        err_ratio = (
            'sum(rate(http_requests_total{job="%s",code=~"5.."}[5m]))\n'
            "  / sum(rate(http_requests_total{job=\"%s\"}[5m]))" % (job, job)
        )
        rules.append(
            _rule(
                "HighErrorRate",
                "(%s) > %s" % (err_ratio, eb["error_rate_warn"]),
                "warning",
                ev["for_warn"],
                "%s error rate above %.2f%%" % (svc, eb["error_rate_warn"] * 100),
                "5xx ratio for %s has exceeded the warning threshold "
                "for %s. Check recent deploys and error logs." % (svc, ev["for_warn"]),
                spec,
            )
        )
        rules.append(
            _rule(
                "HighErrorRate",
                "(%s) > %s" % (err_ratio, eb["error_rate_critical"]),
                "critical",
                ev["for_critical"],
                "%s error rate above %.2f%%" % (svc, eb["error_rate_critical"] * 100),
                "5xx ratio for %s has exceeded the critical threshold. "
                "Page the on-call, consider rollback." % svc,
                spec,
            )
        )

    if spec["alerts"]["latency"]:
        lat = spec["latency"]
        p99 = (
            'histogram_quantile(0.99,\n'
            '  sum(rate(http_request_duration_seconds_bucket{job="%s"}[5m])) by (le))' % job
        )
        for sev, ms, for_ in (
            ("warning", lat["p99_warn_ms"], ev["for_warn"]),
            ("critical", lat["p99_critical_ms"], ev["for_critical"]),
        ):
            rules.append(
                _rule(
                    "HighLatencyP99",
                    "%s > %s" % (p99, ms / 1000.0),
                    sev,
                    for_,
                    "%s p99 latency above %dms" % (svc, ms),
                    "p99 request latency for %s is above %dms for %s. "
                    "Check slow endpoints and downstream dependencies." % (svc, ms, for_),
                    spec,
                )
            )

    if spec["alerts"]["resources"]:
        res = spec["resources"]
        cpu_ratio = (
            'sum(rate(container_cpu_usage_seconds_total{%s}[5m]))\n'
            '  / sum(kube_pod_container_resource_requests{%s,resource="cpu"})' % (pod_sel, pod_sel)
        )
        mem_ratio = (
            'sum(container_memory_working_set_bytes{%s})\n'
            '  / sum(kube_pod_container_resource_requests{%s,resource="memory"})' % (pod_sel, pod_sel)
        )
        rules.append(
            _rule(
                "CpuSaturation",
                "(%s) > %s" % (cpu_ratio, res["cpu_warn"]),
                "warning",
                ev["for_warn"],
                "%s CPU usage above %.0f%% of requests" % (svc, res["cpu_warn"] * 100),
                "Containers are using more than %.0f%% of requested CPU for %s. "
                "Consider raising requests or scaling out." % (res["cpu_warn"] * 100, ev["for_warn"]),
                spec,
            )
        )
        rules.append(
            _rule(
                "MemorySaturation",
                "(%s) > %s" % (mem_ratio, res["memory_warn"]),
                "warning",
                ev["for_warn"],
                "%s memory usage above %.0f%% of requests" % (svc, res["memory_warn"] * 100),
                "Containers are using more than %.0f%% of requested memory for %s. "
                "Watch for OOMKills." % (res["memory_warn"] * 100, ev["for_warn"]),
                spec,
            )
        )

    if spec["alerts"]["restarts"]:
        rst = spec["restarts"]
        restarts = (
            'sum(increase(kube_pod_container_status_restarts_total{%s}[1h]))' % pod_sel
        )
        rules.append(
            _rule(
                "PodRestarting",
                "%s > %d" % (restarts, rst["warn"]),
                "warning",
                ev["for_warn"],
                "%s pods restarting more than %d times/hour" % (svc, rst["warn"]),
                "Pods for %s restarted %d+ times in the last hour. "
                "Check crashlooping containers and recent deploys." % (svc, rst["warn"]),
                spec,
            )
        )

    return rules


def build_prometheus_rule(spec, rules):
    """Wrap rules in a PrometheusRule manifest dict."""
    return {
        "apiVersion": "monitoring.coreos.com/v1",
        "kind": "PrometheusRule",
        "metadata": {
            "name": "%s-alerts" % spec["service"],
            "namespace": spec["namespace"],
            "labels": {"team": spec["team"], "app.kubernetes.io/managed-by": "prom-grafana-kit"},
        },
        "spec": {"groups": [{"name": "%s.rules" % spec["service"], "rules": rules}]},
    }
