# 4. Docker

A container is a normal Linux process with namespaces and cgroups around it. An image is a stack of read-only layers.

Use [`projects/01-url-shortener`](../projects/01-url-shortener) for this module.

## Do it

```bash
cd projects/01-url-shortener
docker build --target runtime -t url-shortener:0.1.0 .
docker history url-shortener:0.1.0
docker image inspect url-shortener:0.1.0 --format '{{json .Config.User}} {{json .Config.Cmd}}'

cp .env.example .env
docker compose up --build -d
docker compose ps
docker compose logs -f app
```

Read the [`Dockerfile`](../projects/01-url-shortener/Dockerfile) and explain every line. Why three stages? Why does the runtime stage use a numeric user? Why is the `requirements.txt` copy before the source copy?

Rebuild after changing only `shortener/app.py`, then after changing `requirements.txt`. Watch which layers come from the cache.

## Break it

**Exit code 137.**

```bash
docker run --name oom --memory 32m python:3.13-slim python -c "x = bytearray(200 * 1024 * 1024)"
docker inspect oom --format 'exit={{.State.ExitCode}} oom={{.State.OOMKilled}}'
docker rm oom
```

**A process that ignores `docker stop`.** Shell-form `CMD python app.py` runs under `/bin/sh -c`, so the shell is PID 1 and may not pass SIGTERM on. Compare how long `docker stop` takes with shell form and exec form.

**A root filesystem you cannot write to.**

```bash
docker run --rm --read-only url-shortener:0.1.0 sh -c 'touch /app/x; touch /tmp/x; echo done'
docker run --rm --read-only --tmpfs /tmp url-shortener:0.1.0 sh -c 'touch /tmp/x; echo done'
```

**A container that cannot reach its neighbour.** Run `docker compose stop db`, then `curl -i localhost:8000/readyz` and `curl -i localhost:8000/healthz`. Explain why they differ, then start `db` again.

## Explain it

- What is the difference between an image and a container?
- What does exit code 137 mean? What about 143?
- What is the difference between `CMD` and `ENTRYPOINT`?
- Why does the order of `COPY` and `RUN` affect build speed?
- Why is running as root in a container dangerous if the container is "isolated"?
- What is the difference between a volume and a bind mount?

## Done when

You can build a small non-root image from an empty file, and diagnose a container that exits immediately using `logs`, `inspect` and `exec`.
