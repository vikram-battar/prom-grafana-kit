"""Lint generated (or hand-written) alert rules and dashboards.

Exit code semantics: lint() returns a list of findings; each finding is a
dict with level ('error'|'warning'), check name, and message. The CLI exits
non-zero when any finding has level 'error'.
"""

import json

import yaml


def _balanced(expr):
    depth = 0
    for ch in expr:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def lint_alerts(path):
    """Lint a PrometheusRule YAML file. Returns list of findings."""
    findings = []
    try:
        with open(path) as f:
            doc = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [{"level": "error", "check": "yaml-parse", "message": str(e)}]

    groups = (doc or {}).get("spec", {}).get("groups", [])
    seen = {}
    for group in groups:
        for rule in group.get("rules", []):
            name = rule.get("alert", "<unnamed>")
            if "alert" not in rule:
                continue  # recording rules are out of scope for this linter
            key = (name, rule.get("labels", {}).get("severity", ""))
            if key in seen:
                findings.append(
                    {
                        "level": "error",
                        "check": "duplicate-alert",
                        "message": "alert %r with severity %r defined twice" % (name, key[1] or "(none)"),
                    }
                )
            seen[key] = True

            expr = rule.get("expr", "")
            if not expr:
                findings.append({"level": "error", "check": "empty-expr", "message": "%s has an empty expr" % name})
            elif not _balanced(str(expr)):
                findings.append(
                    {"level": "error", "check": "unbalanced-parens", "message": "%s expr has unbalanced parentheses" % name}
                )

            if not rule.get("for"):
                findings.append({"level": "warning", "check": "missing-for", "message": "%s has no 'for' clause; it will fire instantly" % name})

            labels = rule.get("labels", {})
            if "severity" not in labels:
                findings.append({"level": "error", "check": "missing-severity", "message": "%s has no severity label" % name})
            elif labels["severity"] not in ("warning", "critical", "info", "page"):
                findings.append(
                    {"level": "warning", "check": "unknown-severity", "message": "%s severity %r is non-standard" % (name, labels["severity"])}
                )

            ann = rule.get("annotations", {})
            for field in ("summary", "description", "runbook_url"):
                if not ann.get(field):
                    findings.append(
                        {"level": "error", "check": "missing-annotation", "message": "%s is missing annotation %r" % (name, field)}
                    )
            if "rate(" in str(expr) and "[5m]" not in str(expr) and "[1m]" not in str(expr):
                findings.append(
                    {"level": "warning", "check": "suspicious-range", "message": "%s uses rate() without an explicit range vector like [5m]" % name}
                )
    if not seen:
        findings.append({"level": "warning", "check": "no-alerts", "message": "no alert rules found in %s" % path})
    return findings


def lint_dashboard(path):
    """Lint a Grafana dashboard JSON file. Returns list of findings."""
    findings = []
    try:
        with open(path) as f:
            dash = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return [{"level": "error", "check": "json-parse", "message": str(e)}]

    if not dash.get("uid"):
        findings.append({"level": "error", "check": "missing-uid", "message": "dashboard has no uid; Grafana provisioning needs one"})
    if not dash.get("title"):
        findings.append({"level": "error", "check": "missing-title", "message": "dashboard has no title"})

    panels = dash.get("panels", [])
    if not panels:
        findings.append({"level": "error", "check": "no-panels", "message": "dashboard has no panels"})

    ids = set()
    for panel in panels:
        pid = panel.get("id")
        if pid in ids:
            findings.append({"level": "error", "check": "duplicate-panel-id", "message": "panel id %r used twice" % pid})
        ids.add(pid)
        if not panel.get("title"):
            findings.append({"level": "warning", "check": "untitled-panel", "message": "panel id %r has no title" % pid})
        targets = panel.get("targets", [])
        if not targets:
            findings.append({"level": "error", "check": "panel-no-targets", "message": "panel %r has no query targets" % panel.get("title", pid)})
        for t in targets:
            expr = t.get("expr", "")
            if not expr:
                findings.append(
                    {"level": "error", "check": "empty-panel-expr", "message": "panel %r has a target with empty expr" % panel.get("title", pid)}
                )
            elif not _balanced(str(expr)):
                findings.append(
                    {
                        "level": "error",
                        "check": "unbalanced-parens",
                        "message": "panel %r expr has unbalanced parentheses" % panel.get("title", pid),
                    }
                )

    templating = dash.get("templating", {}).get("list", [])
    names = [v.get("name") for v in templating]
    if "datasource" not in names:
        findings.append({"level": "warning", "check": "no-datasource-var", "message": "no 'datasource' template variable; dashboard is tied to one Prometheus"})

    return findings


def report(findings):
    for f in findings:
        print("[%s] %s: %s" % (f["level"].upper(), f["check"], f["message"]))
