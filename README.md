# BotForge

بات تلگرام/بله کسب‌وکارت را با یک گفت‌وگو بساز: ایجنت مشخصات را می‌پرسد، BotSpec می‌سازد،
در سن‌باکس تست می‌کند، خرابی‌ها را خودش رفع می‌کند و بات واقعی را منتشر می‌کند — با نسخه‌بندی و Rollback.

> مستندات اصلی پروژه: [docs/](docs/) — وضعیت: [docs/PROGRESS.md](docs/PROGRESS.md)

## اجرای سریع (لوکال، بدون داکر)

```bash
# ۱) API
cd apps/api
cp .env.example .env
python3 -m venv ../../.venv
../../.venv/bin/pip install -e "../..[dev]"   # از ریشه: make install
../../.venv/bin/alembic upgrade head          # یا: make migrate (روی SQLite هم کار می‌کند)
../../.venv/bin/uvicorn app.main:app --reload --port 8000
```

```bash
# ۲) وب
cd apps/web
npm install
npm run dev        # http://localhost:3000
```

## اجرا با Docker Compose (روی VPS)

```bash
cp deploy/.env.example deploy/.env
# مقدارهای SECRET_KEY و FERNET_KEY و پسورد DB را پر کن
make up            # = docker compose -f deploy/docker-compose.yml up -d --build
```

سرویس‌ها: `db` (Postgres 16)، `api` (FastAPI + Alembic در استارت)، `worker`، `web` (Next.js)، `caddy` (HTTPS خودکار).

## بررسی‌ها

```bash
make lint     # ruff check + format --check
make typecheck  # mypy strict
make test     # pytest (SQLite in-memory)
make check    # هر سه
make eval     # eval ایجنت با MockLLM
```

## ساختار

```
apps/api      # FastAPI + SQLAlchemy + Alembic + LangGraph
apps/web      # Next.js 15 + Tailwind v4 + RTL فارسی
deploy        # docker-compose.yml، Caddyfile، .env.example
docs          # PROGRESS، BACKLOG، tech، business-plan، pitch، demo-script
```

## قواعد محصول (خلاصهٔ سند اصلی)

- ایجنت فقط BotSpec (JSON معتبر Pydantic) تولید می‌کند؛ Runtime عمومی آن را اجرا می‌کند — بدون تولید کد.
- ماژول‌ها: Booking، Ordering، FAQ، Notify (فقط همین چهار تا؛ ایده‌ها → docs/BACKLOG.md).
- LLM فقط از طریق Provider سازگار OpenAI با کلید/آدرس از env؛ بدون کلید → MockLLM برای dev.
- هیچ ماک یا فیک در مسیر اصلی محصول؛ تست‌ها واقعی اجرا می‌شوند.
- همهٔ پیام‌های خطا فارسی و قابل‌فهم، UI کامل RTL با دکمهٔ dark/light.
