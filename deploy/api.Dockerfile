# context: ریشهٔ ریپو (deploy/docker-compose.yml → context: ../)
FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

# اول فقط pyproject تا لایهٔ نصب وابستگی‌ها کش بماند
COPY apps/api/pyproject.toml ./
COPY apps/api/alembic.ini ./
COPY apps/api/alembic ./alembic
COPY apps/api/app ./app
RUN pip install --no-cache-dir .

# ایمیج نهایی: فقط runtime (بدون کش pip)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

RUN useradd --create-home --shell /usr/sbin/nologin botforge
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY apps/api/alembic.ini ./
COPY apps/api/alembic ./alembic

USER botforge
EXPOSE 8000

# healthcheck واقعی روی /healthz (بدون curl — با urllib پایتون)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/healthz')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
