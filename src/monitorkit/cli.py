"""monitorkit CLI: generate PrometheusRule + Grafana dashboard from a spec, lint them."""

import argparse
import json
import os
import sys

import yaml

from .alerts import build_prometheus_rule, build_rules
from .dashboards import build_dashboard
from .lint import lint_alerts, lint_dashboard, report
from .spec import load_spec


def cmd_generate(args):
    spec = load_spec(args.spec)
    rules = build_rules(spec)
    manifest = build_prometheus_rule(spec, rules)
    dashboard = build_dashboard(spec)

    os.makedirs(args.out, exist_ok=True)
    alerts_path = os.path.join(args.out, "%s-alerts.yaml" % spec["service"])
    dash_path = os.path.join(args.out, "%s-dashboard.json" % spec["service"])

    with open(alerts_path, "w") as f:
        yaml.safe_dump(manifest, f, sort_keys=False, default_flow_style=False)
    with open(dash_path, "w") as f:
        json.dump(dashboard, f, indent=2)
        f.write("\n")

    print("wrote %s (%d alert rules)" % (alerts_path, len(rules)))
    print("wrote %s (%d panels)" % (dash_path, len(dashboard["panels"])))
    return 0


def cmd_lint(args):
    findings = []
    if args.alerts:
        findings += lint_alerts(args.alerts)
    if args.dashboard:
        findings += lint_dashboard(args.dashboard)
    report(findings)
    errors = sum(1 for f in findings if f["level"] == "error")
    warnings = sum(1 for f in findings if f["level"] == "warning")
    print("%d error(s), %d warning(s)" % (errors, warnings))
    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="monitorkit", description="Generate and lint Prometheus alerts + Grafana dashboards from one service spec.")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="generate PrometheusRule YAML and Grafana dashboard JSON")
    gen.add_argument("--spec", required=True, help="path to service spec YAML")
    gen.add_argument("--out", required=True, help="output directory")
    gen.set_defaults(func=cmd_generate)

    ln = sub.add_parser("lint", help="lint alert rules and/or dashboard files")
    ln.add_argument("--alerts", help="path to PrometheusRule YAML")
    ln.add_argument("--dashboard", help="path to Grafana dashboard JSON")
    ln.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero on warnings as well as errors",
    )
    ln.set_defaults(func=cmd_lint)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
