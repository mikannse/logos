import pytest


@pytest.fixture
def app():
    from app.main import app
    return app


@pytest.fixture
def client(app):
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")
