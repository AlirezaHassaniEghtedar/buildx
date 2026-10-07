async def test_healthz(client):  # noqa: ANN001
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
