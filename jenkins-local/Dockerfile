# A Jenkins agent with everything the project pipeline needs.
FROM jenkins/inbound-agent:3391.va_37fa_a_305d6d-5-jdk21

USER 0

# hadolint ignore=DL3008,SC1091
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl python3 \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && codename="$(. /etc/os-release && echo "$VERSION_CODENAME")" \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${codename} stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-buildx-plugin docker-compose-plugin \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Trivy is checked against its published checksum before it is installed.
ARG TRIVY_VERSION=0.76.1
RUN set -e; \
    case "$(dpkg --print-architecture)" in \
      amd64) asset=Linux-64bit; sum=c7cbe3137fb8a48a17574bede3dd6beb16742d1e9772929940fc90082c39d9c0 ;; \
      arm64) asset=Linux-ARM64; sum=e174dff2a6dba5e3ae41f8d0537a6324405bd08132497340304c6b20e0f16a1f ;; \
      *) echo "unsupported architecture" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/trivy.tgz "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_${asset}.tar.gz"; \
    echo "${sum}  /tmp/trivy.tgz" > /tmp/trivy.sha256; \
    sha256sum --check /tmp/trivy.sha256; \
    tar -xzf /tmp/trivy.tgz -C /usr/local/bin trivy; \
    rm /tmp/trivy.tgz /tmp/trivy.sha256

# The jenkins user in the base image.
USER 1000
