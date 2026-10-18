"""تست CRUD بات‌ها."""

from httpx import AsyncClient


async def test_bot_crud(authed_client: AsyncClient) -> None:
    r = await authed_client.post("/api/bots", json={"name": "بات کافه", "channel": "sandbox"})
    assert r.status_code == 201
    bot = r.json()

    r2 = await authed_client.get("/api/bots")
    assert [b["id"] for b in r2.json()] == [bot["id"]]

    r3 = await authed_client.patch(f"/api/bots/{bot['id']}", json={"name": "بات کارگاه"})
    assert r3.json()["name"] == "بات کارگاه"

    assert (await authed_client.delete(f"/api/bots/{bot['id']}")).status_code == 200
    assert (await authed_client.get(f"/api/bots/{bot['id']}")).status_code == 404


async def test_owner_isolation(client: AsyncClient) -> None:
    """دو کاربر نباید بات‌های همدیگر را ببینند."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    await client.post(
        "/api/auth/register",
        json={"email": "u1@example.com", "password": "secret1234", "name": "یکی"},
    )
    bot = (await client.post("/api/bots", json={"name": "بات من"})).json()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c2:
        r = await c2.post(
            "/api/auth/register",
            json={"email": "u2@example.com", "password": "secret1234", "name": "دومی"},
        )
        assert r.status_code == 201
        assert (await c2.get("/api/bots")).json() == []
        assert (await c2.get(f"/api/bots/{bot['id']}")).status_code == 404
