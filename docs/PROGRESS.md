# PROGRESS

> هر فاز: وضعیت، برنامه کوتاه، پذیرش، و مشکلات روزبه‌روز. آخرین به‌روزرسانی: ۱۴۰۵/۰۷/۱۵ (۲۰۲۶-۱۰-۰۷)

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
- concurrency (۵۰↔۱۰): `test_concurrency.py` — ۲ تست با Postgres شرطی؛ روی این ماشین اجرا نشده
  (DATABASE_URL_TEST_PG لازم است) — به‌عنوان limitation گزارش می‌شود، نه pass.
- webhook واقعی وصل شد: `POST /webhook/{deployment_id}/{secret}` → ۲۰۰ سریع + پردازش پس‌زمینه؛
  تست‌های `test_webhook.py` (۴ تست): ردِ secret غلط، deployment ناشناس، ترنسکریپت Sandbox،
  چرخهٔ کامل /start تا پیام خوش‌آمد + EndUser/Conversation/MessagesLog.
- SandboxChannel در `get_channel` ثبت شد؛ ترنسکریپت درون‌حافظه برای PhoneMock.
- `make eval` → `app/agent/eval.py`: ۶/۶ مورد موفق (MockLLM قطعی، هزینهٔ $0.0000).
- `make smoke` → `app/testing/smoke.py`: روی uvicorn واقعی سبز (healthz، register+کوکی HttpOnly،
  /api/bots، ردِ webhook غلط).
- کیفیت: `ruff` ✅ | `mypy --strict` ✅ (۴۲ فایل) | `pytest` **۳۱ passed / 2 skipped** ✅

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
- کیفیت: `ruff` ✅ | `mypy --strict` ✅ (۴۶ فایل) | `pytest` **۳۶ passed / 2 skipped** ✅
  (۵ تست جدید فاز ۲: شبیه‌ساز ۲، گراف ۲، SSE ۱)

**مشکلات و درس‌های فاز ۲:**
- ASGITransport درخواست SSE را تا کامل‌شدن پاسخ باز نگه می‌دارد؛ تست SSE ترتیب «اول POST
  پیام، بعد خواندن استریم» را می‌گیرد (صف، رویدادهای قبلی را replay می‌کند).
- chunkهای `astream` دلتای هر node هستند (کلیید = نام node) نه state انباشته.
- `state.update(seed)` روی TypedDict در mypy strict ممنوع؛ با حلقهٔ `state[k] = v` حل شد.

## فاز ۳ — انتشار و Modify (بعدها)

**برنامه:** confirm→انتشار: ساخت BotVersion، Deployment با توکن Fernet و secret ۳۲ بایتی،
setWebhook روی کانال واقعی، Rollback بین نسخه‌ها؛ حالت modify با diff_specs/humanize_diff
(آماده در spec/diff.py) و publish_card در SSE.
