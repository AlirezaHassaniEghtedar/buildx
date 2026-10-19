.DEFAULT_GOAL := help
SHELL := /bin/bash

# همهٔ ابزارها از طریق scripts/dev.py (cross-platform؛ روی ویندوز: python scripts/dev.py ...)
PY := python3

# ── اجرا و ابزارها ────────────────────────────────────────
setup install api web lint typecheck test check eval migrate:
	$(PY) scripts/dev.py $@

smoke: ## دود-تست پس از دیپلوی: make smoke URL=https://...
	$(PY) scripts/dev.py smoke $(URL)

# ── Docker ────────────────────────────────────────────────
up: ## اجرای کل پلتفرم با Docker Compose
	docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build

down: ## توقف پلتفرم
	docker compose -f deploy/docker-compose.yml down

logs: ## لاگ سرویس‌ها
	docker compose -f deploy/docker-compose.yml logs -f --tail=100 api worker web

help: ## راهنما
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
