#!/usr/bin/env python3
"""ران‌کنندهٔ cross-platform پروژه BotForge — فقط stdlib؛ ویندوز/لینوکس/هر cwd.

R18: جایگزین Makefile برای توسعه‌دهندهٔ ویندوز (بدون bash و بدون bin/).

مثال‌ها:
    python scripts/dev.py setup      # venv + نصب + ساخت .env با کلید تصادفی
    python scripts/dev.py api        # uvicorn با reload — از هر پوشه‌ای
    python scripts/dev.py check      # lint + typecheck + test
    python scripts/dev.py smoke URL  # دود-تست سرور مستقر
"""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
API = REPO / "apps" / "api"
WEB = REPO / "apps" / "web"
VENV = REPO / ".venv"
IS_WIN = os.name == "nt"
VENV_BIN = VENV / ("Scripts" if IS_WIN else "bin")
PY = VENV_BIN / ("python.exe" if IS_WIN else "python")

Commands = dict[str, Callable[[list[str]], int]]


def _force_utf8_console() -> None:
    """ویندوز: stdout/stderr پیش‌فرض (cp1252) متن فارسی را می‌شکند؛ UTF-8 + جایگزین به‌جای crash."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def _run(
    cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> int:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, cwd=str(cwd or REPO), env=env)


def _tool(name: str) -> str:
    """npm روی ویندوز npm.cmd است؛ مسیر کامل پیدا می‌کنیم تا subprocess نشکند."""
    found = shutil.which(name)
    if found is None:
        print(f"⚠️ '{name}' پیدا نشد؛ Node.js نصب است؟", file=sys.stderr)
    return found or name


def _api(cmd: list[str]) -> int:
    if not PY.exists():
        print(
            "⚠️ محیط مجازی ساخته نشده است؛ اول اجرا کنید: python scripts/dev.py setup",
            file=sys.stderr,
        )
        return 1
    return _run(cmd, cwd=API)


def cmd_setup(_args: list[str]) -> int:
    """ساخت venv (در صورت نیاز)، نصب وابستگی‌ها و ساخت .env با کلید تصادفی."""
    if not PY.exists():
        if _run([sys.executable, "-m", "venv", str(VENV)]) != 0:
            return 1
    if _run([str(PY), "-m", "pip", "install", "-q", "-e", f"{API}[dev]"]) != 0:
        return 1
    env_file = API / ".env"
    key = secrets.token_urlsafe(48)
    if not env_file.exists():
        example = API / ".env.example"
        lines = example.read_text(encoding="utf-8-sig").splitlines()
        lines = [
            ("SECRET_KEY=" + key) if ln.startswith("SECRET_KEY=") else ln for ln in lines
        ]
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"✅ .env ساخته شد (با SECRET_KEY تصادفی): {env_file}")
    else:
        # .env موجود ممکن است کلید placeholder ضعیف داشته باشد (مثلاً کپی‌شده از example)
        lines = env_file.read_text(encoding="utf-8-sig").splitlines()
        has_key = False
        weak = False
        fixed: list[str] = []
        for ln in lines:
            if ln.startswith("SECRET_KEY="):
                has_key = True
                if len(ln.split("=", 1)[1].strip().encode("utf-8")) < 32:
                    weak = True
                    fixed.append("SECRET_KEY=" + key)
                    continue
            fixed.append(ln)
        if not has_key:
            fixed.append("SECRET_KEY=" + key)
            weak = True
        if weak:
            env_file.write_text("\n".join(fixed) + "\n", encoding="utf-8")
            print(f"⚠️ SECRET_KEY در {env_file} خالی/ضعیف بود؛ با کلید تصادفی جایگزین شد.")
        else:
            print(f"• .env از قبل وجود دارد و معتبر است: {env_file}")
    print("مرحلهٔ بعد: python scripts/dev.py migrate && python scripts/dev.py api")
    return 0


def cmd_api(args: list[str]) -> int:
    """uvicorn با reload — عمداً از ریشهٔ ریپو تا cwd-مستقل بودن اثبات شود."""
    port = os.environ.get("PORT", "8000")
    return _run(
        [
            str(PY),
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            str(API),
            "--reload",
            "--reload-dir",
            str(API / "app"),
            "--port",
            port,
            *args,
        ],
        cwd=REPO,
    )


def cmd_web(_args: list[str]) -> int:
    return _run([_tool("npm"), "run", "dev"], cwd=WEB)


def cmd_migrate(_args: list[str]) -> int:
    return _api([str(PY), "-m", "alembic", "upgrade", "head"])


def cmd_test(_args: list[str]) -> int:
    return _api([str(PY), "-m", "pytest", "-q"])


def cmd_lint(_args: list[str]) -> int:
    rc = _api([str(PY), "-m", "ruff", "check", "app", "tests"])
    rc2 = _api([str(PY), "-m", "ruff", "format", "--check", "app", "tests"])
    return rc or rc2


def cmd_typecheck(_args: list[str]) -> int:
    return _api([str(PY), "-m", "mypy", "app"])


def cmd_eval(_args: list[str]) -> int:
    return _api([str(PY), "-m", "app.agent.eval"])


def cmd_smoke(args: list[str]) -> int:
    if not args:
        print("استفاده: python scripts/dev.py smoke https://your-domain.example", file=sys.stderr)
        return 2
    return _api([str(PY), "-m", "app.testing.smoke", args[0]])


def cmd_check(_args: list[str]) -> int:
    for f in (cmd_lint, cmd_typecheck, cmd_test):
        if f([]) != 0:
            return 1
    return 0


COMMANDS: Commands = {
    "setup": cmd_setup,
    "api": cmd_api,
    "web": cmd_web,
    "migrate": cmd_migrate,
    "test": cmd_test,
    "lint": cmd_lint,
    "typecheck": cmd_typecheck,
    "eval": cmd_eval,
    "smoke": cmd_smoke,
    "check": cmd_check,
}

HELP = """دستورات (python scripts/dev.py <دستور>):
  setup      ساخت venv + نصب وابستگی‌ها + ساخت .env با کلید تصادفی
  migrate    alembic upgrade head
  api        uvicorn با reload (پورت 8000 یا PORT)
  web        npm run dev در apps/web
  test       pytest -q
  lint       ruff check + format --check
  typecheck  mypy --strict (app)
  check      lint + typecheck + test
  eval       اجرای eval ایجنت با MockLLM
  smoke URL  دود-تست سرور مستقر
(لینوکس/مک: make هم همین اسکریپت را صدا می‌زند.)"""


def main(argv: list[str]) -> int:
    _force_utf8_console()
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(HELP)
        return 0
    name, rest = argv[0], argv[1:]
    fn = COMMANDS.get(name)
    if fn is None:
        print(f"دستور ناشناخته: {name}\n\n{HELP}", file=sys.stderr)
        return 2
    return fn(rest)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
