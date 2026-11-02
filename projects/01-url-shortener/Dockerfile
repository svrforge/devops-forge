# Stage 1: install dependencies. Build tools stay here and never reach the final image.
FROM python:3.13-slim AS build
WORKDIR /build
COPY requirements.txt .
RUN python -m venv --without-pip /opt/venv \
    && pip --python /opt/venv/bin/python install --no-cache-dir -r requirements.txt

# Stage 2: test image. Build it with --target test. The final image never contains it.
FROM python:3.13-slim AS test
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY requirements-dev.txt .
RUN pip --python /opt/venv/bin/python install --no-cache-dir -r requirements-dev.txt
COPY shortener ./shortener
COPY tests ./tests
CMD ["python", "-m", "pytest", "-q"]

# Stage 3: the image that ships. It is the default target because it comes last.
FROM python:3.13-slim AS runtime
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# The app never installs packages, so remove pip and the libraries bundled inside it.
RUN /usr/local/bin/python -m pip uninstall --yes pip \
    && useradd --system --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY shortener ./shortener
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s \
  CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
# One worker because Prometheus counters live per process. Scale with replicas instead.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "shortener.app:app"]
