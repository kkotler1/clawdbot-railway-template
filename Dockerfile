# Build openclaw from source to avoid npm packaging gaps (some dist files are not shipped).
FROM node:22-bookworm AS openclaw-build

# Dependencies needed for openclaw build
RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    curl \
    python3 \
    make \
    g++ \
  && rm -rf /var/lib/apt/lists/*

# Install Bun (openclaw build uses it)
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:${PATH}"

RUN corepack enable

WORKDIR /openclaw

# Pin to a known ref (tag/branch). If it doesn't exist, fall back to main.
ARG OPENCLAW_GIT_REF=main
RUN git clone --depth 1 --branch "${OPENCLAW_GIT_REF}" https://github.com/openclaw/openclaw.git .

# Patch: relax version requirements for packages that may reference unpublished versions.
# Apply to all extension package.json files to handle workspace protocol (workspace:*).
RUN set -eux; \
  find ./extensions -name 'package.json' -type f | while read -r f; do \
    sed -i -E 's/"openclaw"[[:space:]]*:[[:space:]]*">=[^"]+"/"openclaw": "*"/g' "$f"; \
    sed -i -E 's/"openclaw"[[:space:]]*:[[:space:]]*"workspace:[^"]+"/"openclaw": "*"/g' "$f"; \
  done

RUN pnpm install --no-frozen-lockfile
RUN pnpm build
ENV OPENCLAW_PREFER_PNPM=1
RUN pnpm ui:install && pnpm ui:build


# Runtime image
FROM node:22-bookworm
ENV NODE_ENV=production

RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    python3 \
    python3-pip \
  && rm -rf /var/lib/apt/lists/*

# Install gog (gogcli) binary deterministically (for OpenClaw gog skill).
# Do not rely on pip.
ARG GOGCLI_VERSION=0.9.0
ARG GOGCLI_SHA256_LINUX_AMD64=28219f4a57478b3c38d5b33cfcb00f53a5943784b96c3b47e6dd877b384c5a13
ARG GOGCLI_SHA256_LINUX_ARM64=67a4fb974c34165c60fb7edb613f78a25aa6f0a94a904b6bdc4641a409743f75
RUN set -eux; \
  arch="$(dpkg --print-architecture)"; \
  case "$arch" in \
    amd64) gog_arch="amd64"; sha="$GOGCLI_SHA256_LINUX_AMD64" ;; \
    arm64) gog_arch="arm64"; sha="$GOGCLI_SHA256_LINUX_ARM64" ;; \
    *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; \
  esac; \
  url="https://github.com/steipete/gogcli/releases/download/v${GOGCLI_VERSION}/gogcli_${GOGCLI_VERSION}_linux_${gog_arch}.tar.gz"; \
  curl -fsSL "$url" -o /tmp/gogcli.tgz; \
  echo "${sha}  /tmp/gogcli.tgz" | sha256sum -c -; \
  tar -xzf /tmp/gogcli.tgz -C /tmp gog; \
  install -m 0755 /tmp/gog /usr/local/bin/gog; \
  rm -f /tmp/gogcli.tgz /tmp/gog

WORKDIR /app

# Wrapper deps
COPY package.json ./
RUN npm install --omit=dev && npm cache clean --force

# Python deps (gogcli / `gog` CLI)
COPY requirements.txt ./
RUN python3 -m pip install --no-cache-dir --user -r requirements.txt
ENV PATH="/root/.local/bin:${PATH}"

# Copy built openclaw
COPY --from=openclaw-build /openclaw /openclaw

# Provide an openclaw executable
RUN printf '%s\n' '#!/usr/bin/env bash' 'exec node /openclaw/dist/entry.js "$@"' > /usr/local/bin/openclaw \
  && chmod +x /usr/local/bin/openclaw

COPY src ./src

# The wrapper listens on this port.
ENV OPENCLAW_PUBLIC_PORT=8080
ENV PORT=8080
EXPOSE 8080

# TEMP DEBUG (remove after collecting logs): gog + oauth + openclaw log tail
# ORIGINAL_STARTUP: CMD ["node", "src/server.js"]
CMD ["sh", "-lc", "set +e; (command -v bash >/dev/null 2>&1 && exec bash -lc 'set +e; echo \"===== DEBUG BEGIN =====\" >&2; whoami >&2 || true; pwd >&2 || true; echo \"PATH=$PATH\" >&2; which gog >&2 || command -v gog >&2 || true; ls -la /usr/bin /usr/local/bin /app 2>/dev/null | grep -i gog >&2 || true; gog --help >&2 || gog version >&2 || true; ls -la ~/.config >&2 || true; ls -la ~/.config/gog* >&2 || true; ls -la /tmp/openclaw >&2 || true; if ls -1 /tmp/openclaw/openclaw-*.log >/dev/null 2>&1; then echo \"--- openclaw log tail ---\" >&2; tail -n 200 /tmp/openclaw/openclaw-*.log >&2 || true; fi; echo \"===== DEBUG END =====\" >&2; exec node src/server.js' ) || ( echo \"===== DEBUG BEGIN =====\" >&2; whoami >&2 || true; pwd >&2 || true; echo \"PATH=$PATH\" >&2; which gog >&2 || command -v gog >&2 || true; ls -la /usr/bin /usr/local/bin /app 2>/dev/null | grep -i gog >&2 || true; gog --help >&2 || gog version >&2 || true; ls -la ~/.config >&2 || true; ls -la ~/.config/gog* >&2 || true; ls -la /tmp/openclaw >&2 || true; if ls -1 /tmp/openclaw/openclaw-*.log >/dev/null 2>&1; then echo \"--- openclaw log tail ---\" >&2; tail -n 200 /tmp/openclaw/openclaw-*.log >&2 || true; fi; echo \"===== DEBUG END =====\" >&2; exec node src/server.js )"]
