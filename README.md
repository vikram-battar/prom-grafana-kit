# prom-grafana-kit

I built this because every new microservice I shipped needed the same thing: four or five Prometheus alerts and a Grafana dashboard, and I was tired of copy-pasting YAML between services and finding the drift six months later. One service had a p99 alert at 2 seconds, another at 500ms, a third had no runbook link at all. Nobody meant for that to happen. It just happens when every service's monitoring is hand-written.

So this is the boring version: you describe the service once in a small YAML file, and it spits out a `PrometheusRule` manifest and a Grafana dashboard JSON with the same alert shapes, the same label conventions, and a runbook link on every alert. It also lints what it generates (or what you already have) and fails your CI pipeline on the mistakes I kept making: duplicate alerts, missing severity labels, unbalanced parens in an expr, a dashboard with no uid.

This is a portfolio reference implementation, not employer internals. Thresholds and queries are starting points — tune them against your own traffic before you page anyone.

## What it does

- `monitorkit generate --spec service.yaml --out ./out` — builds `<service>-alerts.yaml` (PrometheusRule) and `<service>-dashboard.json` (Grafana) from one spec.
- `monitorkit lint --alerts out/x-alerts.yaml --dashboard out/x-dashboard.json` — checks both files and exits non-zero on errors. Built for CI.

The generated alerts:

| Alert | What it watches |
|---|---|
| `ServiceDown` | `up{job}` is 0 — nothing being scraped |
| `HighErrorRate` | 5xx ratio over 5m, warning + critical thresholds |
| `HighLatencyP99` | p99 request latency, warning + critical thresholds |
| `CpuSaturation` | CPU usage vs requests for the service's pods |
| `MemorySaturation` | memory working set vs requests |

The dashboard has six panels: request rate, 5xx percentage, p50/p95/p99 latency, CPU vs requests, memory vs requests, pod restarts. It assumes the standard Prometheus + kube-state-metrics metric names (`http_requests_total`, `http_request_duration_seconds_bucket`, `container_cpu_usage_seconds_total`). If your app exposes different metric names, adjust `alerts.py` and `dashboards.py` — the query-building code is deliberately plain so it's easy to change.

## Install

```bash
git clone https://github.com/vikram-battar/prom-grafana-kit.git
cd prom-grafana-kit
pip install -r requirements.txt
export PYTHONPATH=src   # or: pip install -e .
```

## Usage

Copy the example spec and edit it:

```bash
cp examples/service.yaml myservice.yaml
# edit myservice.yaml: service name, namespace, thresholds, runbook URL
```

Generate:

```bash
monitorkit generate --spec myservice.yaml --out ./out
# wrote ./out/myservice-alerts.yaml (7 alert rules)
# wrote ./out/myservice-dashboard.json (6 panels)
```

Lint (this is the part that belongs in CI):

```bash
monitorkit lint --alerts ./out/myservice-alerts.yaml --dashboard ./out/myservice-dashboard.json
# 0 error(s), 0 warning(s)
```

Apply:

```bash
kubectl apply -f ./out/myservice-alerts.yaml
# import ./out/myservice-dashboard.json in Grafana: Dashboards > New > Import
```

Example CI step (GitHub Actions):

```yaml
- name: Lint monitoring configs
  run: |
    export PYTHONPATH=src
    monitorkit generate --spec services/api.yaml --out /tmp/monitoring
    monitorkit lint --alerts /tmp/monitoring/api-alerts.yaml \
                    --dashboard /tmp/monitoring/api-dashboard.json
```

## The spec file

Everything lives in one YAML. The example at `examples/service.yaml` shows every field; only `service`, `namespace`, and `job` are required. Sensible defaults fill in the rest (warn thresholds, `for` durations, team label). Set any key under `alerts:` to `false` to skip that family.

## The linter's rules

Alerts: no duplicate (name, severity) pairs, expr must parse as balanced, every alert needs a `for` clause (warning if missing), a severity label, and `summary` / `description` / `runbook_url` annotations. Dashboards: valid JSON, has a uid and title, unique panel ids, every panel has at least one target with a non-empty expr, and a `datasource` template variable (warning if missing).

## Project layout

```
src/monitorkit/
  cli.py         # generate / lint subcommands
  spec.py        # spec loading, defaults, validation
  alerts.py      # PrometheusRule construction
  dashboards.py  # Grafana dashboard construction
  lint.py        # lint rules for alerts and dashboards
examples/service.yaml
tests/           # pytest suite
```

## License

MIT. See LICENSE.
