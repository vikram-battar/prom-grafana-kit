.PHONY: test lint-demo generate clean

test:
	PYTHONPATH=src python3 -m pytest tests/ -q

generate:
	PYTHONPATH=src python3 -m monitorkit.cli generate --spec examples/service.yaml --out out

lint-demo: generate
	PYTHONPATH=src python3 -m monitorkit.cli lint --alerts out/checkout-api-alerts.yaml --dashboard out/checkout-api-dashboard.json

clean:
	rm -rf out .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; true
