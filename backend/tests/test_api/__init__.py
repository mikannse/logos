import pytest


@pytest.mark.asyncio
async def test_search_nouns(client):
    response = await client.get("/api/nouns", params={"q": "爱因斯坦"})
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert data["query"] == "爱因斯坦"


@pytest.mark.asyncio
async def test_search_nouns_short_query(client):
    response = await client.get("/api/nouns", params={"q": "爱"})
    assert response.status_code == 422
