.DEFAULT_GOAL := help
SHELL := /bin/bash

# ── API (لوکال، بدون داکر) ─────────────────────────────
PY := python3
VENV := .venv
PIP := $(VENV)/bin/pip
API_DIR := apps/api

venv: ## ساخت محیط مجازی و نصب وابستگی‌های API
	$(PY) -m venv $(VENV)
	$(PIP) install -q -e "$(API_DIR)[dev]"

install: venv ## نصب همه وابستگی‌ها

up: ## اجرای کل پلتفرم با Docker Compose
	docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build

down: ## توقف پلتفرم
	docker compose -f deploy/docker-compose.yml down

logs: ## لاگ سرویس‌ها
	docker compose -f deploy/docker-compose.yml logs -f --tail=100 api worker web

# ── کیفیت کد و تست ─────────────────────────────────────
lint: ## ruff + mypy
	cd $(API_DIR) && $(VENV)/bin/ruff check app tests && ruff format --check app tests

typecheck: ## mypy
	cd $(API_DIR) && $(VENV)/bin/mypy app

test: ## تست‌های واحد و concurrency با Postgres شرطی
	cd $(API_DIR) && $(VENV)/bin/pytest -q

check: lint typecheck test ## همه بررسی‌ها

eval: ## اجرای eval مجموعه درخواست‌های فارسی (با MockLLM)
	cd $(API_DIR) && $(VENV)/bin/python -m app.agent.eval

smoke: ## دود-تست پس از دیپلوی: make smoke URL=https://...
	cd $(API_DIR) && $(VENV)/bin/python -m app.testing.smoke $(URL)

migrate: ## اجرای مایگریشن Alembic (لوکال)
	cd $(API_DIR) && $(VENV)/bin/alembic upgrade head

help: ## راهنما
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
