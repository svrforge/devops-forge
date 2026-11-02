"""These tests need a real PostgreSQL server. Set DATABASE_URL before running them."""
import pytest

from shortener.app import create_app, valid_url
from shortener.migrate import migrate


@pytest.fixture(scope="session", autouse=True)
def schema():
    migrate()


@pytest.fixture
def client():
    return create_app().test_client()


def test_liveness_needs_no_database(client):
    assert client.get("/healthz").status_code == 200


def test_readiness_checks_the_database(client):
    assert client.get("/readyz").json == {"status": "ready"}


def test_readiness_fails_when_the_database_is_down(client, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody@127.0.0.1:1/none")
    response = client.get("/readyz")
    assert response.status_code == 503


def test_create_and_follow_a_link(client):
    created = client.post("/api/links", json={"url": "https://example.com/page"})
    assert created.status_code == 201
    followed = client.get(f"/{created.json['code']}")
    assert followed.status_code == 302
    assert followed.headers["Location"] == "https://example.com/page"


def test_unknown_code_is_a_404(client):
    assert client.get("/does-not-exist").status_code == 404


@pytest.mark.parametrize(
    "bad",
    ["javascript:alert(1)", "ftp://example.com", "not a url", "", None, 123, "https://", "http://" + "a" * 2050],
)
def test_bad_urls_are_rejected(client, bad):
    assert client.post("/api/links", json={"url": bad}).status_code == 400


def test_missing_body_is_rejected(client):
    assert client.post("/api/links", data="nope").status_code == 400


def test_metrics_use_route_templates_not_raw_paths(client):
    client.get("/some-random-code")
    body = client.get("/metrics").get_data(as_text=True)
    assert 'route="/<code>"' in body
    assert "some-random-code" not in body


def test_valid_url_accepts_http_and_https():
    assert valid_url("http://example.com")
    assert valid_url("https://example.com/a?b=c")
