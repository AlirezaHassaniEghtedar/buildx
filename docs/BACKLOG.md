# BACKLOG

ایده‌های خارج از دامنه V1 (قانون شماره ۴ سند اصلی):

- ماژول‌های اضافه: پرسش‌نامه، نظرسنجی، باشگاه مشتری، اطلاع‌رسانی زمان‌بندی‌شده (cron) برای صاحبان بات.
- flows پیشرفته: چندمرحله‌ای شرطی، A/B روی پیام خوش‌آمد.
- پرداخت درون‌بات (درگاه‌های ایرانی).
- چند ادمین/نقش برای هر بات و مجوزهای تفکیک‌شده.
- اپ موبایل و PWA.
- حالت چندزبانه (غیر از فارسی).
- LangSmith/Langfuse trace به‌صورت پیش‌فرض فعال (الان اختیاری با env).

## کارهای باقی‌ماندهٔ همین V1 (اولویت‌دار، خارج از این شاخه)

- **فاز ۳ — انتشار/نسخه/Rollback:** confirm→ساخت BotVersion + Deployment با توکن Fernet،
  setWebhook روی کانال واقعی، Rollback بین نسخه‌ها، حالت modify با diff_specs/humanize_diff و
  publish_card در SSE.
- **رویدادهای ایجنت پایدار:** جایگزینی حباب درون‌حافظهٔ SSE با جدول `builder_events` یا
  LISTEN/NOTIFY؛ پشتیبانی Last-Event-ID؛ status صحیح سشن؛ جلوگیری از اجرای همزمان دو گراف.
- **گراف:** سقف تلاش generate_spec، checkpointer واقعی LangGraph، `record_usage` در همهٔ
  فراخوانی‌های LLM، سقف هزینهٔ per-session پایدار از llm_usage.
- **LLM:** retry با backoff برای 429/5xx، timeout قابل‌تنظیم، fallback از json_schema به
  json_object، محافظت prompt injection.
- **شبیه‌ساز/eval:** جایگزینی InMemoryStore با RuntimeStore روی SQLite؛ `expect` برای هر مرحله
  در build_cases (همان چیزی که B4 را می‌گرفت)؛ eval با پاسخ ضبط‌شده + حالت --live.
- **فرانت‌اند:** صفحهٔ `bots/[id]/build` (سشن + SSE + reconnect)، فرم‌ها با react-hook-form+zod،
  ESLint flat config و تست کامپوننت/E2E.
- **پوشش تست ≥۸۰٪ برای app/runtime, app/spec, app/channels (pytest-cov).**
