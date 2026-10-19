"""تست‌های Auth — پذیرش فاز ۰."""

from httpx import AsyncClient


async def test_register_login_me(client: AsyncClient) -> None:
    r = await client.post(
        "/api/auth/register",
        json={"email": "amir@example.com", "password": "secret1234", "name": "امیر"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "amir@example.com"

    r2 = await client.post(
        "/api/auth/login", json={"email": "amir@example.com", "password": "secret1234"}
    )
    assert r2.status_code == 200

    r3 = await client.get("/api/auth/me")
    assert r3.status_code == 200
    assert r3.json()["name"] == "امیر"


async def test_register_duplicate_email(client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "secret1234", "name": "تکراری"}
    assert (await client.post("/api/auth/register", json=payload)).status_code == 201
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 409
    assert r.json()["code"] == "email_taken"


async def test_login_wrong_password(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "secret1234", "name": "ایکس"},
    )
    r = await client.post(
        "/api/auth/login", json={"email": "x@example.com", "password": "wrong-pass"}
    )
    assert r.status_code == 401
    assert r.json()["message_fa"]


async def test_me_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


async def test_logout(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/register",
        json={"email": "l@example.com", "password": "secret1234", "name": "ال"},
    )
    r = await client.post("/api/auth/logout")
    assert r.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_validation_error_is_persian(client: AsyncClient) -> None:
    """B7: خطای 422 باید پاکت فارسی {code, message_fa, details} باشد، نه detail انگلیسی."""
    r = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "secret1234", "name": "نامعتبر"},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation_error"
    assert "ایمیل" in body["message_fa"]
    assert body["details"]["fields"] == ["email"]
    assert "detail" not in body
