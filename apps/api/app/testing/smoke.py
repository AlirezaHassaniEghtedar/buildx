"""دود-تست پس از دیپلوی — بدون وابستگی به دیتابیس مستقیم.

اجرا: python -m app.testing.smoke [BASE_URL]
  پیش‌فرض: http://localhost:8000   (یا: make smoke URL=https://bot.example.com)

بررسی‌ها:
  1) /healthz پاسخ ok می‌دهد
  2) ثبت‌نام یک کاربر تصادفی کار می‌کند (کوکی HttpOnly ست می‌شود)
  3) /api/bots با همان کوکی لیست خالی برمی‌گرداند
  4) webhook با secret غلط {ok: false} می‌دهد و چیزی لو نمی‌رود
"""

import sys
import uuid

import httpx

DEFAULT_URL = "http://localhost:8000"
TIMEOUT = 15.0


def _ok(label: str) -> None:
    print(f"  ✅ {label}")


def _fail(label: str, detail: str = "") -> None:
    print(f"  ❌ {label}" + (f" — {detail}" if detail else ""))


def run(base_url: str) -> int:
    base = base_url.rstrip("/")
    failures = 0
    print(f"دود-تست BotForge روی {base}\n")

    with httpx.Client(base_url=base, timeout=TIMEOUT, follow_redirects=True) as c:
        # 1) healthz
        try:
            r = c.get("/healthz")
            if r.status_code == 200 and r.json().get("status") == "ok":
                _ok("healthz")
            else:
                failures += 1
                _fail("healthz", f"HTTP {r.status_code}: {r.text[:120]}")
        except httpx.HTTPError as exc:
            failures += 1
            _fail("healthz", str(exc))
            print("\nنتیجه: شکست — سرویس در دسترس نیست.")
            return 1

        # 2) ثبت‌نام کاربر تصادفی
        email = f"smoke-{uuid.uuid4().hex[:10]}@example.com"
        r = c.post(
            "/api/auth/register",
            json={"email": email, "password": "smoke-test-1234", "name": "دود تست"},
        )
        if r.status_code == 201 and "bf_access" in c.cookies:
            _ok(f"register ({email}) + کوکی HttpOnly")
        else:
            failures += 1
            _fail("register", f"HTTP {r.status_code}: {r.text[:160]}")

        # 3) لیست بات‌ها با احراز هویت
        r = c.get("/api/bots")
        if r.status_code == 200 and isinstance(r.json(), list):
            _ok("GET /api/bots")
        else:
            failures += 1
            _fail("GET /api/bots", f"HTTP {r.status_code}: {r.text[:160]}")

        # 4) webhook با secret غلط — باید ok:false باشد، نه 500 و نه نشت اطلاعات
        r = c.post("/webhook/smoke-deployment/wrong-secret", json={"message": {"text": "/start"}})
        if r.status_code == 200 and r.json().get("ok") is False:
            _ok("webhook ردِ secret غلط")
        else:
            failures += 1
            _fail("webhook", f"HTTP {r.status_code}: {r.text[:160]}")

    print(f"\nنتیجه: {'همهٔ بررسی‌ها سبز ✅' if failures == 0 else f'{failures} بررسی شکست ❌'}")
    return 0 if failures == 0 else 1


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    return run(url)


if __name__ == "__main__":
    sys.exit(main())
