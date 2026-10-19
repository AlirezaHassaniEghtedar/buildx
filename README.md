# BotForge

بات تلگرام/بله کسب‌وکارت را با یک گفت‌وگو بساز: ایجنت مشخصات را می‌پرسد، BotSpec می‌سازد،
در سن‌باکس تست می‌کند، خرابی‌ها را خودش رفع می‌کند و بات واقعی را منتشر می‌کند — با نسخه‌بندی و Rollback.

> مستندات اصلی پروژه: [docs/](docs/) — وضعیت: [docs/PROGRESS.md](docs/PROGRESS.md)

## پیش‌نیازها

- **Python 3.12 یا 3.13** (هر دو در CI تست می‌شوند؛ ویندوز/لینوکس/مک)
- **Node.js 22+** (فقط برای وب)
- اختیاری: **Postgres 16** (برای تست‌های concurrency و مهاجرت؛ بدون آن روی SQLite کار می‌کند)

## شروع سریع — روش پیشنهادی (همهٔ سیستم‌عامل‌ها)

ران‌کنندهٔ `scripts/dev.py` فقط با stdlib کار می‌کند و از **هر پوشه‌ای** قابل اجراست:

```bash
python scripts/dev.py setup      # venv + نصب وابستگی‌ها + ساخت .env با کلید تصادفی
python scripts/dev.py migrate    # alembic upgrade head (روی SQLite هم کار می‌کند)
python scripts/dev.py api        # uvicorn روی http://localhost:8000
python scripts/dev.py web        # ترمینال دوم — Next.js روی http://localhost:3000
python scripts/dev.py check      # ruff + mypy + pytest
```

روی ویندوز در PowerShell هم همین دستورات کار می‌کنند؛ یا از رابط نازک:

```powershell
.\scripts\dev.ps1 setup
.\scripts\dev.ps1 api
```

> اگر `.env` موجود کلید ضعیف/placeholder داشته باشد، `setup` خودش آن را با کلید قوی جایگزین می‌کند.

## شروع سریع — نصب دستی

### لینوکس / macOS

```bash
cd apps/api
cp .env.example .env
python3 -m venv ../../.venv
../../.venv/bin/pip install -e ".[dev]"
# در .env مقدار SECRET_KEY را پر کن (حداقل ۳۲ بایت):
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
../../.venv/bin/alembic upgrade head
../../.venv/bin/uvicorn app.main:app --reload --reload-dir app --port 8000
```

### ویندوز / PowerShell

```powershell
cd apps\api
python -m venv ..\..\.venv
..\..\.venv\Scripts\Activate.ps1      # اگر مسدود بود: Set-ExecutionPolicy -Scope Process Bypass
pip install -e ".[dev]"
Copy-Item .env.example .env           # بعد SECRET_KEY قوی را در .env بگذارید
alembic upgrade head
uvicorn app.main:app --reload --reload-dir app --port 8000
```

نکته‌های مهم:

- **`pip install -e "..\..[dev]"` غلط است.** `pyproject.toml` در `apps/api` است؛ همیشه از داخل همین پوشه و با `".[dev]"` نصب کنید.
- فایل `.env` را با **ویرایشگر** یا `Set-Content -Encoding utf8` بسازید، نه اپراتور `>` (PowerShell 5 فایل UTF-16/BOM می‌سازد). اگر BOM هم داشته باشد، کد آن را می‌خواند (`utf-8-sig`) — ولی ساخت درست ترجیح دارد.
- **از هر پوشه‌ای می‌توانید اجرا کنید:** مسیر `.env` و `dev.db` نسبت به `apps/api` حل می‌شود، نه پوشهٔ جاری؛ `dev.db` همیشه زیر `apps/api` ساخته می‌شود. اجرای uvicorn/alembic از ریشهٔ ریپو هم کار می‌کند.

### وب (هر دو سیستم‌عامل)

```bash
cd apps/web
npm install
npm run dev        # http://localhost:3000
```

## عیب‌یابی ویندوز

| علامت | علت و راه‌حل |
| --- | --- |
| `راه‌اندازی ناموفق: تنظیمات ناقص است` یا `Field required` برای SECRET_KEY | `.env` پیدا نشد یا کلید خالی/ضعیف است. `python scripts/dev.py setup` را اجرا کنید یا دستی `apps/api\.env` بسازید و کلید ≥۳۲ بایتی بگذارید. |
| `Activate.ps1` خطای «running scripts is disabled» | `Set-ExecutionPolicy -Scope Process Bypass` را در همان پنجره اجرا کنید. |
| `error while attempting to bind on address ... only one usage of each socket address` | پورت ۸۰۰۰ اشغال است: `PORT=8001 python scripts/dev.py api` |
| `npm` خطای `EPERM ... symlink` موقع build | حالت Developer ویندوز را فعال کنید یا Node را با manage symlink نصب‌شده بگیرید؛ `npm install` به‌جای `npm ci` هم کمک می‌کند. |
| متن فارسی در کنسول به‌هم‌ریخته است | `chcp 65001` و فونت ترمینال Unicode بگذارید. |
| `alembic` از ریشهٔ ریپو پیدا نمی‌شود | از `python scripts/dev.py migrate` استفاده کنید؛ alembic.ini با `%(here)s` از هر cwd کار می‌کند. |

## متغیرهای محیطی (`.env` در `apps/api`)

| متغیر | پیش‌فرض | توضیح |
| --- | --- | --- |
| `SECRET_KEY` | — (الزامی) | امضای JWT؛ حداقل ۳۲ بایت |
| `FERNET_KEY` | خالی | رمز توکن بات‌ها؛ در `ENV=prod` الزامی می‌شود |
| `ENV` | `dev` | `dev` یا `prod` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./dev.db` | مسیر نسبی SQLite همیشه زیر `apps/api` حل می‌شود |
| `LLM_BASE_URL` / `LLM_API_KEY` | OpenAI / خالی | Provider سازگار OpenAI؛ بدون کلید → MockLLM (فقط dev) |
| `LLM_MODEL_SMART` / `LLM_MODEL_FAST` | `gpt-4o-mini` | مدل‌های ایجنت |
| `MAX_COST_PER_SESSION_USD` | `2.0` | سقف هزینه هر سشن |

برای تست‌های PG-only هم `DATABASE_URL_TEST_PG` (در CI توسط ورک‌فلو ست می‌شود).

## اجرا با Docker Compose (روی VPS)

```bash
cp deploy/.env.example deploy/.env
# مقدارهای SECRET_KEY و FERNET_KEY و پسورد DB را پر کن
make up            # = docker compose -f deploy/docker-compose.yml up -d --build
```

سرویس‌ها: `db` (Postgres 16)، `api` (FastAPI + Alembic در استارت)، `worker`، `web` (Next.js)، `caddy` (HTTPS خودکار).

## بررسی‌ها

```bash
python scripts/dev.py lint       # ruff check + format --check
python scripts/dev.py typecheck  # mypy strict
python scripts/dev.py test       # pytest (تست‌های PG-only بدون PG skip می‌شوند)
python scripts/dev.py check      # هر سه
python scripts/dev.py eval       # eval ایجنت با MockLLM
make check                       # معادل روی لینوکس/مک
```

## ساختار

```
apps/api      # FastAPI + SQLAlchemy + Alembic + LangGraph
apps/web      # Next.js 15 + Tailwind v4 + RTL فارسی
deploy        # docker-compose.yml، Caddyfile، .env.example
scripts       # dev.py (cross-platform) و dev.ps1
docs          # PROGRESS، BACKLOG، tech، business-plan، pitch، demo-script
```

## قواعد محصول (خلاصهٔ سند اصلی)

- ایجنت فقط BotSpec (JSON معتبر Pydantic) تولید می‌کند؛ Runtime عمومی آن را اجرا می‌کند — بدون تولید کد.
- ماژول‌ها: Booking، Ordering، FAQ، Notify (فقط همین چهار تا؛ ایده‌ها → docs/BACKLOG.md).
- LLM فقط از طریق Provider سازگار OpenAI با کلید/آدرس از env؛ بدون کلید → MockLLM برای dev.
- هیچ ماک یا فیک در مسیر اصلی محصول؛ تست‌ها واقعی اجرا می‌شوند.
- همهٔ پیام‌های خطا فارسی و قابل‌فهم، UI کامل RTL با دکمهٔ dark/light.
