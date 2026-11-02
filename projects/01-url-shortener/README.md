# Project 1: URL shortener, from laptop to Kubernetes

A small app with a real database, used to practise the full delivery path. The app is deliberately simple, so the attention stays on how it is built, shipped and run.

```text
Developer -> Git -> CI -> Image -> Kubernetes -> Service -> Users
                    |                  |
                 tests, lint,       probes, limits,
                 image scan         network policies
                                       |
                                  Prometheus -> Alerts
```

| Path | What it shows |
| --- | --- |
| [`shortener/`](shortener) | Flask API, health checks, Prometheus metrics, safe migration |
| [`tests/`](tests) | Tests against a real PostgreSQL server |
| [`Dockerfile`](Dockerfile) | Multi-stage, non-root image with a separate test stage |
| [`compose.yaml`](compose.yaml) | The whole stack on one machine |
| [`k8s/`](k8s) | Hardened Deployment, StatefulSet, autoscaling, disruption budget and network policies |
| [`monitoring/`](monitoring) | Prometheus configuration and alert rules |
| [`Jenkinsfile`](Jenkinsfile) | Jenkins pipeline that passes its own audit. Run it with [`jenkins-local/`](../../jenkins-local) |
| [`../../.github/workflows/ci.yml`](../../.github/workflows/ci.yml) | The same checks in GitHub Actions |

## Run it with Docker Compose

```bash
cp .env.example .env     # Then choose a local password in .env.
docker compose up --build -d

curl -X POST -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}' http://localhost:8000/api/links
curl -i http://localhost:8000/<code-from-the-response>
```

| URL | Purpose |
| --- | --- |
| `http://localhost:8000/healthz` | Is the process alive? |
| `http://localhost:8000/readyz` | Can it reach the database? |
| `http://localhost:8000/metrics` | Prometheus metrics |
| `http://localhost:9090` | Prometheus |

Run the tests in containers:

```bash
docker compose --profile test run --rm --build test
docker compose --profile test down --volumes
```

## Run it on Kubernetes

Follow [`basics/05-kubernetes.md`](../../basics/05-kubernetes.md). It uses a local [kind](https://kind.sigs.k8s.io/) cluster.

## Design decisions

These are good interview answers. Be ready to defend each one.

- **`/healthz` does not touch the database, and `/readyz` does.** If the database fails, restarting the app does not help. Pods should stop receiving traffic, not restart.
- **Migrations run in an init container with an advisory lock.** Two replicas starting together cannot migrate at the same time.
- **One Gunicorn worker per container.** Prometheus counters live per process, so scaling happens through replicas.
- **Metrics use the route template, not the path.** Random short codes in a label would create unlimited time series.
- **The Kubernetes memory limit is set, the CPU limit is not.** Memory cannot be reclaimed. Going over a CPU limit only causes throttling, which often hurts more than it helps.
- **Secrets are never in Git.** The Kubernetes secret is created by a command, and `.env` is ignored.

## Extend it

Do these yourself. They are what make the project yours.

1. Add Grafana with a provisioned dashboard.
2. Add an Ingress with TLS through cert-manager.
3. Publish images to GHCR on a Git tag, signed with cosign.
4. Deploy with Argo CD so Git becomes the source of truth.
5. Add a rollback runbook, then practise it.
6. Replace the StatefulSet with a managed database through Terraform.
