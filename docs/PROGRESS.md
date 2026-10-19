# PROGRESS

> هر فاز: وضعیت، برنامه کوتاه، پذیرش، و مشکلات روزبه‌روز. آخرین به‌روزرسانی: ۱۴۰۵/۰۷/۲۸ (۲۰۲۶-۱۰-۱۹)

## فاز ۰ — اسکلت ✅ (تمام)

**برنامه:** monorepo، Docker Compose (web/api/worker/db/caddy)، `.env.example`، Alembic + همهٔ جدول‌ها،
Auth کامل (argon2 + JWT در کوکی HttpOnly + SameSite=Lax)، bots CRUD با ایزوله‌سازی owner،
توکن‌های «Forge»، صفحات Landing/Login/Signup/bots فارسی RTL با دکمهٔ dark/light، worker (jobs + SKIP LOCKED)، CI.

**پذیرش فاز ۰:** ✅
- ثبت‌نام/ورود/خروج/me — تست: `tests/test_auth.py` (۵ تست، پاس)
- bots CRUD + ایزوله‌سازی — تست: `tests/test_bots.py` (پاس)
- کل پلتفرم بدون Docker هم اجرا می‌شود: uvicorn (پورت ۸۰۰۰) + next dev (پورت ۳۰۰۰)؛
  روی VPS: `make up` (کامپوز) — در این ماشین Docker نصب نیست، کامپوز آمادهٔ اجرا روی سرور است.
- RTL و dark/light: `data-theme` روی `<html dir="rtl" lang="fa">` + toggle با localStorage.
- کیفیت: `ruff` ✅ | `mypy --strict` ✅ (۲۳ فایل) | `pytest` ۸/۸ ✅ | `next build` ✅

**مشکلات و درس‌ها:**
- ترتیب آرگومان argon2 `verify(hash, password)` است نه برعکس — تست گرفت و رفع شد.
- کوکی HttpOnly از fetch جواب می‌دهد چون `credentials: "include"` در کلاینت گذاشته شد.
- mypy 2.4 روی ternary با overload کرش می‌کرد؛ به if/else ساده تبدیل شد.

## فاز ۱ — BotSpec و Runtime ✅ (تمام)

**برنامه:** ماژول spec (BotSpec discriminated union + validatorهای منطقی + diff + completeness + پیام خطای فارسی)،
لایهٔ llm (کلاینت OpenAI-compatible + pricing.yaml + usage + MockLLM)،
Runtime عمومی (booking با قفل ردیف و لیست انتظار، ordering، faq، notify، rules، nlu، i18n_fa)؛
کانال‌ها (Telegram/Bale/Sandbox + webhook + poller)؛ testing (اسکیما، شبیه‌ساز، ارزیاب، گزارش)؛
تست concurrency ظرفیت/لیست انتظار (با Postgres شرطی).

**پذیرش فاز ۱:** ✅
- با Spec دستی (fixture سفالگری) کل چرخهٔ رزرو در Runtime پاس می‌شود: تست‌های `test_runtime.py` (۷ تست).
- concurrency (۵۰↔۱۰): `test_concurrency.py` — ۲ تست روی Postgres واقعی. از شاخهٔ
  `fix/ci-and-hardening`: در CI اجرا می‌شوند (سرویس postgres:16 + DATABASE_URL_TEST_PG)
  و بدون env تست fail می‌شوند نه skip. قفل با `pg_advisory_xact_lock` (B1 رفع شد).
- webhook واقعی وصل شد: `POST /webhook/{deployment_id}/{secret}` → ۲۰۰ سریع + پردازش پس‌زمینه؛
  تست‌های `test_webhook.py` (۴ تست): ردِ secret غلط، deployment ناشناس، ترنسکریپت Sandbox،
  چرخهٔ کامل /start تا پیام خوش‌آمد + EndUser/Conversation/MessagesLog.
- SandboxChannel در `get_channel` ثبت شد؛ ترنسکریپت درون‌حافظه برای PhoneMock.
- `make eval` → `app/agent/eval.py`: ۶/۶ مورد موفق (MockLLM قطعی، هزینهٔ $0.0000).
- `make smoke` → `app/testing/smoke.py`: روی uvicorn واقعی سبز (healthz، register+کوکی HttpOnly،
  /api/bots، ردِ webhook غلط).
- کیفیت (۱۴۰۵/۰۷/۲۸): `ruff` ✅ | `mypy --strict` ✅ (۴۶ فایل) | `pytest` **۵۴ passed / 0 skipped** ✅

**مشکلات و درس‌های فاز ۱:**
- ناسازگاری قرارداد store/engine پیدا و رفع شد: engine به store با `bot_id=`/`env=` صدا می‌زد
  ولی `RuntimeStore` این‌ها را در سازنده می‌گیرد؛ FakeStore تست با `**kw` آن را پنهان کرده بود.
- `get_channel("sandbox")` به‌جای SandboxChannel تلگرام برمی‌گرداند (رفع شد؛ import دیرهنگام برای چرخه).
- conftest حالا `get_sessionmaker` ماژول webhook را هم patch می‌کند (پردازش پس‌زمینه سشن خودش را می‌سازد).
- MockLlmClient با یک کلید purpose مشترک، آخرین set_response را برای همهٔ caseها می‌داد؛
  در eval برای هر مورد نمونهٔ تازه ساخته شد.

## فاز ۲ — ایجنت LangGraph ✅ (تمام)

**برنامه:** گراف intake→generate_spec→validate→(clarify)→design_tests→run_sandbox→(fix)→confirm؛
BuilderSession/BuilderMessage روی دیتابیس، SSE برای استودیو، MockLLM بدون کلید.
تقسیم کار با LLM (طبق سند): استخراج/تولید Spec در generate_spec با schema=BotSpec (purpose=build)،
تلاش مجدد در fix (purpose=fix + diff فارسی)، سؤال‌سازی فقط از completeness،
تست‌سازی قطعی از اسکیمای ماژول‌ها (بدون LLM). fallback قطعی synth برای dev بدون کلید.

**پذیرش فاز ۲:** ✅
- گراف `app/agent/graph.py` (LangGraph 1.2.13): reducer رویدادها با operator.add؛
  حلقهٔ fix با سقف MAX_FIX_ROUNDS=۲ و diff فارسی بین نوبت‌ها.
- شبیه‌ساز `app/testing/simulator.py`: تولید قطعی تست‌ها از اسکیما (رزرو موفق، تلفن نامعتبر،
  لغو، ظرفیت پُر→لیست انتظار، سفارش کامل/زیر حداقل) و اجرا روی RuntimeEngine با store درون‌حافظه.
- API بیلدر `app/builder/router.py`: POST sessions (۲۰۱)، POST messages (۲۰۲ + اجرای گراف در
  پس‌زمینه)، GET messages، GET events با SSE (replay بافر + keepalive)، محافظت owner.
- استودیو `apps/web`: StepTimeline (۶ مرحله با وضعیت)، SpecCard (فارسی ساده)، QuestionCard،
  PhoneMock (قاب موبایل RTL با ترنسکریپت زندهٔ تست‌ها) — `next build` ✅.
- **E2E روی سرور واقعی (uvicorn+curl):** register→create bot→session→message→
  SSE تا `done`: همهٔ مراحل step_started→spec_ready→ok→tests_ready→tests_done→
  awaiting_confirmation→done سبز.
- کیفیت (۱۴۰۵/۰۷/۲۸): `ruff` ✅ | `mypy --strict` ✅ | `pytest` **۵۴ passed / 0 skipped** ✅
  (شامل ۲ تست concurrency و ۲ تست مهاجرت روی Postgres واقعی)

**مشکلات و درس‌های فاز ۲:**
- ASGITransport درخواست SSE را تا کامل‌شدن پاسخ باز نگه می‌دارد؛ تست SSE ترتیب «اول POST
  پیام، بعد خواندن استریم» را می‌گیرد (صف، رویدادهای قبلی را replay می‌کند).
- chunkهای `astream` دلتای هر node هستند (کلیید = نام node) نه state انباشته.
- `state.update(seed)` روی TypedDict در mypy strict ممنوع؛ با حلقهٔ `state[k] = v` حل شد.

## فاز A/B — تثبیت CI و رفع باگ‌های بحرانی ✅ (شاخهٔ `fix/ci-and-hardening`)

**فاز A — CI قرمز → سبز** (run 39331431774: api ✅ web ✅ docker ✅):
- `ci.yml`: `SECRET_KEY` حداقل ۳۲ بایت + سرویس `postgres:16-alpine` + ست‌کردن `DATABASE_URL_TEST_PG`.
- `conftest.py`: قطعی‌کردن `os.environ["SECRET_KEY"]` به‌جای setdefault (کلید ضعیف CI بر تست‌ها غلبه می‌کرد).
- حذف `pytest.ini` ریشه (بی‌اثر بود؛ CI از `apps/api/pyproject.toml` می‌خواند).

**رفع باگ‌ها (تست قرمز قبل از فیکس):**

| باگ | فیکس | تست |
|-----|------|-----|
| B1 — Overbooking همزمان (skip_locked) | `pg_advisory_xact_lock` روی کلید آیتم در `RuntimeStore.create_booking` | `test_concurrency.py` (۵۰↔۱۰ → دقیقاً ۱۰ و ۲۵) روی PG واقعی، اجرا در CI |
| B2 — تست‌های concurrency skip و خراب | ساخت Bot واقعی در تست + fail (نه skip) اگر در CI env نباشد | همان ۲ تست، در CI سبز |
| B3 — direction اسکیما VARCHAR(4) ↔ enum اسمی | مهاجرت `0002`: تبدیل امن دادهٔ قدیمی + مدل enum حالا مقدار (value) را ذخیره می‌کند | `test_migrations.py` + درج واقعی MessagesLog روی PG مهاجرت‌شده |
| B4 — همهٔ سؤال‌های فیلد «متوجه نشدم» | کلید `ask_field` در `Texts.t` با متنِ نوع فیلد؛ اعتبارسنجی email/number فعال شد | `test_ask_field_uses_label_not_unknown`, `test_bad_email_rejected_then_accepted`, `test_bad_number_rejected_then_accepted` |
| B5 — NLU قاپیدن مکالمه (متن خالی/تک‌حرف = menu) | گارد متن خالی + حداقل ۲ کاراکتر برای تطبیق زیررشتهٔ دکمه | `test_nlu_empty_and_single_char_not_menu`, `test_contact_share_mid_flow_keeps_flow` |
| B6 — کلیدواژه وسط flow پاسخ را می‌دزد؛ لغو کار نمی‌کرد | «لغو» همیشه اول؛ متن تایپشدهٔ میان‌flow پاسخ همان مرحله است؛ دکمه (callback_data) مستثنی | `test_cancel_mid_flow_exits_flow`, `test_keyword_mid_flow_does_not_hijack` |
| B7 — 422 انگلیسی FastAPI | هندلر `RequestValidationError` با پاکت فارسی + نام فارسی فیلدها | `test_validation_error_is_persian` |
| B8 — Dockerfileهای خراب | `api.Dockerfile` با context ریشهٔ ریپو؛ `web.Dockerfile` standalone بدون `public` اجباری | جاب docker در CI (Build api/web image) سبز |
| B11 — ستون‌های زمان nullable در 0001 | مهاجرت `0002_not_null_timestamps` + هوک `compare_type` برای enum غیربومی در env.py | `alembic check` تمیز + رفت‌وبرگشت مهاجرت روی PG (`test_migrations.py`)

**محدودیت‌های صادقانه:**
- `docker compose up` روی این ماشین اجرا نشده (Docker نصب نیست)؛ فقط build ایمیج‌ها در CI سبز است.
- فاز ۳ (انتشار/نسخه/Rollback) هنوز پیاده نشده — در BACKLOG.

## فاز ۳ — انتشار و Modify (بعدها)

**برنامه:** confirm→انتشار: ساخت BotVersion، Deployment با توکن Fernet و secret ۳۲ بایتی،
setWebhook روی کانال واقعی، Rollback بین نسخه‌ها؛ حالت modify با diff_specs/humanize_diff
(آماده در spec/diff.py) و publish_card در SSE.
