"""A small URL shortener: enough real behaviour to practise the whole delivery path."""
import os
import secrets
import time
from urllib.parse import urlsplit

import psycopg
from flask import Flask, Response, g, jsonify, redirect, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

MAX_URL_LENGTH = 2048
CODE_LENGTH_BYTES = 5

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["route"])
LINKS_CREATED = Counter("links_created_total", "Short links created")


def database_url() -> str:
    return os.environ["DATABASE_URL"]


def connect() -> psycopg.Connection:
    return psycopg.connect(database_url(), connect_timeout=3, autocommit=True)


def valid_url(value: object) -> bool:
    if not isinstance(value, str) or not 0 < len(value) <= MAX_URL_LENGTH:
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.before_request
    def start_timer() -> None:
        g.started = time.perf_counter()

    @app.after_request
    def record_metrics(response: Response) -> Response:
        route = request.url_rule.rule if request.url_rule else "unmatched"
        REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        LATENCY.labels(route).observe(time.perf_counter() - g.started)
        return response

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    @app.get("/readyz")
    def readyz():
        try:
            with connect() as connection:
                connection.execute("SELECT 1")
        except psycopg.Error:
            return jsonify(status="database unavailable"), 503
        return jsonify(status="ready")

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    @app.post("/api/links")
    def create_link():
        payload = request.get_json(silent=True) or {}
        url = payload.get("url")
        if not valid_url(url):
            return jsonify(error="url must be an http or https address"), 400
        code = secrets.token_urlsafe(CODE_LENGTH_BYTES)
        with connect() as connection:
            connection.execute("INSERT INTO links (code, url) VALUES (%s, %s)", (code, url))
        LINKS_CREATED.inc()
        return jsonify(code=code, short_url=f"{request.host_url}{code}"), 201

    @app.get("/<code>")
    def follow_link(code: str):
        with connect() as connection:
            row = connection.execute(
                "UPDATE links SET visits = visits + 1 WHERE code = %s RETURNING url", (code,)
            ).fetchone()
        if row is None:
            return jsonify(error="not found"), 404
        return redirect(row[0], code=302)

    return app


app = create_app()
