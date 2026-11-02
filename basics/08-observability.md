# 8. Observability

Monitoring tells you something is wrong. Observability helps you work out why, using metrics, logs and traces.

## Do it

Start the stack:

```bash
cd projects/01-url-shortener
cp .env.example .env
docker compose up --build -d
```

Create traffic in a second terminal:

```bash
for i in $(seq 1 200); do
  curl -s -o /dev/null -X POST -H 'Content-Type: application/json' \
    -d '{"url":"https://example.com"}' localhost:8000/api/links
  curl -s -o /dev/null localhost:8000/nope
done
```

Open Prometheus at `http://localhost:9090` and run these queries. Say what each one means before you press Execute.

```promql
up
rate(http_requests_total[1m])
sum by (status) (rate(http_requests_total[1m]))
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

Then read [`monitoring/alerts.yml`](../projects/01-url-shortener/monitoring/alerts.yml) and open the Alerts page.

## Break it

```bash
docker compose stop app      # Watch ShortenerDown go pending, then firing.
docker compose start app     # Watch it resolve.
```

Stop `db` while traffic runs. Requests that need the database will fail. Compare what `/metrics`, `/readyz` and the app logs each tell you, and work out which one you would look at first during an incident.

**Cardinality.** The app labels metrics with the route template `/<code>`, not the real path. Change it to use `request.path`, rebuild, generate traffic and look at `/metrics`. Each random code creates a new time series. That is how one label can take down Prometheus. Revert the change afterwards.

## Build on it

Add Grafana to `compose.yaml` with a provisioned Prometheus data source, and build a dashboard with request rate, error rate and p95 latency.

## Explain it

- What is the difference between a counter, a gauge and a histogram?
- Why do you `rate()` a counter rather than graph it directly?
- What are the RED and USE methods?
- Why alert on symptoms that users feel rather than on CPU?
- What does the `for:` field in an alert rule prevent?
- Why does this app run one Gunicorn worker? What breaks in Prometheus with several?
- What is an SLO, and what does a 99.9% target allow per month?

## Done when

From the Prometheus UI alone, you can say how much traffic the service gets, how much of it fails, and how slow it is.
