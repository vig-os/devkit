# Use Python 3.14 as base image (pinned to digest for supply chain integrity)
# Renovate (dockerfile manager) will propose digest updates automatically
# Updated to bookworm (stable) for better security patch cadence
#
# IMPORTANT: this MUST be the multi-arch *index* digest (the top-level
# `Digest:` from `docker buildx imagetools inspect python:3.14-slim-bookworm`),
# never a per-platform child manifest. Pinning a single-arch (amd64) child
# manifest breaks the arm64 release build with "exec format error" (see #578).
FROM python:3.14-slim-bookworm@sha256:a9bee15510a364124aa24692899d269835683b883de42f7ebec8c293cf679ccb

# Add metadata
# By default, we build the dev version unless specified as an argument
ARG IMAGE_TAG="dev"
LABEL maintainer="Carlos Vigo <carlos.vigo@exoma.ch>"
LABEL description="vigOS development environment"
LABEL version="${IMAGE_TAG}"

# OCI standard labels
LABEL org.opencontainers.image.title="vigOS development environment"
LABEL org.opencontainers.image.description="Development environment with common tools and utilities"
LABEL org.opencontainers.image.version="${IMAGE_TAG}"
LABEL org.opencontainers.image.authors="Carlos Vigo <carlos.vigo@exoma.ch>, Lars Gerchow <lars.gerchow@exoma.ch>"
LABEL org.opencontainers.image.vendor="vigOS"
LABEL org.opencontainers.image.source="https://github.com/vig-os/devcontainer"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.documentation="https://github.com/vig-os/devcontainer/blob/main/README.md"
LABEL org.opencontainers.image.url="https://github.com/vig-os/devcontainer"

# Build and runtime information (injected at build time)
ARG BUILD_DATE=""
ARG VCS_REF=""
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${VCS_REF}"
LABEL org.opencontainers.image.ref.name="${IMAGE_TAG}"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Security patching strategy: we do NOT run blanket apt-get upgrade/dist-upgrade.
# The base image digest pin (line 4) guarantees reproducible builds. A blanket
# upgrade silently changes packages between builds, defeating that guarantee.
#
# Instead we rely on:
#   1. Renovate proposing base-image digest updates (covers most CVEs).
#   2. Nightly Trivy scans (.github/workflows/security-scan.yml) for visibility.
#   3. Targeted --only-upgrade for HIGH/CRITICAL CVEs that cannot wait for a
#      new base image rebuild. Each entry must reference a CVE.
#
# See docs/CONTAINER_SECURITY.md for the full policy.
#
# Uncomment and add packages below when a critical CVE needs an immediate fix.
# Remove entries once the base image digest is updated to include the patch.
# RUN apt-get update && apt-get install -y --only-upgrade \
#     <package>=<version> \  # CVE-XXXX-XXXXX
#     && apt-get clean && rm -rf /var/lib/apt/lists/*

# CVE-2026-33845, CVE-2026-33846, CVE-2026-3833, CVE-2026-42009, CVE-2026-42010 (GnuTLS; bookworm-security)
RUN apt-get update && apt-get install -y --no-install-recommends --only-upgrade \
    libgnutls30=3.7.9-2+deb12u7 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# CVE-2026-45447 (OpenSSL PKCS#7/S-MIME; bookworm-security)
RUN apt-get update && apt-get install -y --no-install-recommends --only-upgrade \
    libssl3=3.0.20-1~deb12u2 \
    openssl=3.0.20-1~deb12u2 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    jq \
    openssh-client \
    locales \
    ca-certificates \
    nano \
    minisign \
    podman \
    rsync \
    tmux \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Generate en_US.UTF-8 locale
RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && locale-gen

# Set locale environment variables
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Install latest GitHub CLI manually from releases
# TARGETARCH is automatically provided by Docker BuildKit for multi-platform builds
ARG TARGETARCH
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) ARCH=linux_amd64 ;; \
        arm64) ARCH=linux_arm64 ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}"; exit 1 ;; \
    esac; \
    GH_VERSION="$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest | sed -n 's/.*"tag_name": *"v\?\([^"]*\)".*/\1/p')"; \
    URL=https://github.com/cli/cli/releases/download; \
    BINARY="${URL}/v${GH_VERSION}/gh_${GH_VERSION}_${ARCH}.tar.gz"; \
    CHECKSUM=$(curl -fsSL "${URL}/v${GH_VERSION}/gh_${GH_VERSION}_checksums.txt" | grep "gh_${GH_VERSION}_${ARCH}.tar.gz" | awk '{print $1}'); \
    FILE=gh.tar.gz; \
    curl -fsSL "$BINARY" -o "$FILE"; \
    echo "${CHECKSUM}  ${FILE}" | sha256sum -c -; \
    tar -xzf "$FILE"; \
    mv "gh_${GH_VERSION}_${ARCH}/bin/gh" /usr/local/bin/gh; \
    chmod +x /usr/local/bin/gh; \
    rm -rf "gh_${GH_VERSION}_${ARCH}" "$FILE"; \
    gh --version;

# Install latest just with checksum verification
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) ARCH=x86_64-unknown-linux-musl ;; \
        arm64) ARCH=aarch64-unknown-linux-musl ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}"; exit 1 ;; \
    esac; \
    JUST_VERSION="$(curl -fsSL https://api.github.com/repos/casey/just/releases/latest | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p')"; \
    URL="https://github.com/casey/just/releases/download/${JUST_VERSION}"; \
    FILE="just-${JUST_VERSION}-${ARCH}.tar.gz"; \
    curl -fsSL "${URL}/${FILE}" -o "$FILE"; \
    CHECKSUM=$(curl -fsSL "${URL}/SHA256SUMS" | grep "${FILE}" | awk '{print $1}'); \
    echo "${CHECKSUM}  ${FILE}" | sha256sum -c -; \
    tar -xzf "$FILE" -C /usr/local/bin just; \
    chmod +x /usr/local/bin/just; \
    rm "$FILE"; \
    just --version;

# Install hadolint binary with checksum verification
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) ARCH=linux-x86_64 ;; \
        arm64) ARCH=linux-arm64 ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}"; exit 1 ;; \
    esac; \
    HADOLINT_VERSION="v2.14.0"; \
    URL="https://github.com/hadolint/hadolint/releases/download/${HADOLINT_VERSION}"; \
    FILE="hadolint-${ARCH}"; \
    SHA_FILE="${FILE}.sha256"; \
    curl -fsSL "${URL}/${FILE}" -o "$FILE"; \
    curl -fsSL "${URL}/${SHA_FILE}" -o "$SHA_FILE"; \
    EXPECTED_SHA="$(awk '{print $1}' "$SHA_FILE")"; \
    echo "${EXPECTED_SHA}  ${FILE}" | sha256sum -c -; \
    install -m 0755 "$FILE" /usr/local/bin/hadolint; \
    rm "$FILE" "$SHA_FILE"; \
    hadolint --version;

# Install taplo binary (TOML formatter/linter)
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) ARCH=x86_64 ;; \
        arm64) ARCH=aarch64 ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}"; exit 1 ;; \
    esac; \
    TAPLO_VERSION="$(curl -fsSL https://api.github.com/repos/tamasfe/taplo/releases/latest | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p')"; \
    URL="https://github.com/tamasfe/taplo/releases/download/${TAPLO_VERSION}"; \
    FILE="taplo-linux-${ARCH}.gz"; \
    curl -fsSL "${URL}/${FILE}" -o "$FILE"; \
    gunzip "$FILE"; \
    install -m 0755 "taplo-linux-${ARCH}" /usr/local/bin/taplo; \
    rm -f "taplo-linux-${ARCH}"; \
    taplo --version;

# Install cursor-agent CLI (installs to ~/.local/bin)
ENV PATH="/root/.local/bin:${PATH}"
RUN set -eux; \
    INSTALLER="/tmp/cursor-install.sh"; \
    for attempt in 1 2 3; do \
        if curl -fsSL https://cursor.com/install -o "${INSTALLER}" \
            && bash "${INSTALLER}" \
            && agent --version; then \
            rm -f "${INSTALLER}"; \
            exit 0; \
        fi; \
        rm -f "${INSTALLER}"; \
        echo "cursor-agent install attempt ${attempt} failed, retrying in 10s..."; \
        sleep 10; \
    done; \
    echo "WARNING: cursor-agent install failed after 3 attempts (external CDN issue); skipping"; \
    echo "Install manually: curl -fsSL https://cursor.com/install | bash";

# Install latest cargo-binstall from release archive with minisign signature verification
# cargo-binstall uses minisign for signing releases. Each release has an ephemeral key.
ENV PATH="/root/.cargo/bin:${PATH}"
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) ARCH=x86_64-unknown-linux-musl ;; \
        arm64) ARCH=aarch64-unknown-linux-musl ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}"; exit 1 ;; \
    esac; \
    BINSTALL_VERSION="$( \
        curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/cargo-bins/cargo-binstall/releases/latest \
        | sed -n 's#.*/tag/v\([^/?]*\).*#\1#p' \
    )"; \
    if [ -z "$BINSTALL_VERSION" ]; then \
        echo "Failed to resolve cargo-binstall latest version"; \
        exit 1; \
    fi; \
    URL="https://github.com/cargo-bins/cargo-binstall/releases/download/v${BINSTALL_VERSION}"; \
    FILE="cargo-binstall-${ARCH}.tgz"; \
    SIG_FILE="${FILE}.sig"; \
    PUBKEY_FILE="minisign.pub"; \
    curl -fsSL "${URL}/${FILE}" -o "$FILE"; \
    curl -fsSL "${URL}/${SIG_FILE}" -o "$SIG_FILE"; \
    curl -fsSL "${URL}/${PUBKEY_FILE}" -o "$PUBKEY_FILE"; \
    PUBKEY="$(grep -v '^untrusted comment:' "$PUBKEY_FILE")"; \
    minisign -V -m "$FILE" -x "$SIG_FILE" -P "$PUBKEY"; \
    mkdir -p /root/.cargo/bin; \
    tar -xzf "$FILE" -C /root/.cargo/bin; \
    chmod +x /root/.cargo/bin/cargo-binstall; \
    rm "$FILE" "$SIG_FILE" "$PUBKEY_FILE"; \
    INSTALLED_VERSION="$(cargo-binstall -V | cut -d ' ' -f2)"; \
    if [ "$INSTALLED_VERSION" != "$BINSTALL_VERSION" ]; then \
        echo "Version mismatch: expected ${BINSTALL_VERSION}, got ${INSTALLED_VERSION}"; \
        exit 1; \
    fi; \
    echo "cargo-binstall ${INSTALLED_VERSION} verified with minisign";

# Install just LSP
RUN cargo-binstall just-lsp; \
    just-lsp --version;

# Install typstyle
RUN cargo-binstall typstyle; \
    typstyle --version;

# Install latest uv verifying checksum
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) ARCH=x86_64-unknown-linux-gnu ;; \
        arm64) ARCH=aarch64-unknown-linux-gnu ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}"; exit 1 ;; \
    esac; \
    UV_VERSION="$(curl -fsSL https://api.github.com/repos/astral-sh/uv/releases/latest | sed -n 's/.*"tag_name": *"v\?\([^"]*\)".*/\1/p')"; \
    URL=https://github.com/astral-sh/uv/releases/download; \
    BINARY="${URL}/${UV_VERSION}/uv-${ARCH}.tar.gz"; \
    CHECKSUM=$(curl -fsSL "${BINARY}.sha256" | awk '{print $1}'); \
    FILE=uv.tar.gz; \
    curl -fsSL "$BINARY" -o "$FILE"; \
    echo "${CHECKSUM}  ${FILE}" | sha256sum -c -; \
    tar -xzf "$FILE" -C /usr/local/bin --strip-components=1; \
    rm "$FILE";

# Install Python development tools from root pyproject.toml (SSoT)
# and upgrade pip to fix CVE-2025-8869 (symbolic link extraction vulnerability)
# vig-utils must be present before uv export because uv.lock references it as a workspace member
WORKDIR /build
COPY packages/vig-utils packages/vig-utils
COPY pyproject.toml uv.lock ./
RUN uv export --only-group devcontainer --no-emit-project -o /tmp/devcontainer-reqs.txt && \
    uv pip install --system -r /tmp/devcontainer-reqs.txt && \
    uv pip install --system --upgrade pip && \
    rm /tmp/devcontainer-reqs.txt

# Install vig-utils system-wide
RUN uv pip install --system packages/vig-utils

# Copy assets into container image
COPY assets /root/assets

# Set execute permissions on all shell scripts in the assets
RUN find /root/assets -type f -name "*.sh" -exec chmod +x {} \;

# Note: Container socket configuration is now handled at runtime
# The initialize.sh script detects the host OS and writes CONTAINER_SOCKET_PATH to .env
# docker-compose.yml uses this environment variable for the socket mount

# Generate build-time manifest of files containing placeholders
# This avoids expensive runtime searching in init-workspace.sh
RUN grep -rl '{{SHORT_NAME}}\|{{ORG_NAME}}\|{{IMAGE_TAG}}\|{{GITHUB_REPOSITORY}}' /root/assets/workspace/ \
    --exclude-dir=.git \
    --exclude-dir=.venv \
    --exclude-dir=.pre-commit-cache \
    2>/dev/null > /root/assets/.placeholder-manifest.txt || true

# Pre-initialize pre-commit hooks to system cache location
# This cache is used by the container (not copied to workspace by init-workspace.sh)
# Host users will use their own cache (~/.cache/pre-commit or project-local)
WORKDIR /root/assets/workspace
RUN git config --global init.defaultBranch main && \
    git init && \
    PRE_COMMIT_HOME=/opt/pre-commit-cache \
    pre-commit install-hooks && \
    rm -rf .git

# Pre-build Python virtual environment with template dependencies
# This venv is used directly via UV_PROJECT_ENVIRONMENT (not copied to workspace)
# Temporarily replace {{SHORT_NAME}} placeholder for uv sync, then restore for init-workspace.sh
RUN sed -i 's/{{SHORT_NAME}}/template_project/g' pyproject.toml && \
    uv sync --all-extras --no-install-project && \
    uv pip list && \
    sed -i 's/template_project/{{SHORT_NAME}}/g' pyproject.toml

# Create workspace directory
RUN mkdir -p /workspace
WORKDIR /workspace

# Set environment variables
ENV PYTHONUNBUFFERED="1"
ENV IN_CONTAINER="true"
ENV PRE_COMMIT_HOME="/opt/pre-commit-cache"
ENV UV_PROJECT_ENVIRONMENT="/root/assets/workspace/.venv"
ENV VIRTUAL_ENV="/root/assets/workspace/.venv"

# Create aliases for pre-commit
RUN echo 'alias precommit="pre-commit run"' >> /root/.bashrc

# Default command - interactive shell
CMD ["/bin/bash"]
