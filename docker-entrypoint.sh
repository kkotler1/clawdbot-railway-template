#!/usr/bin/env sh
set -u

# Google Calendar MCP credentials are decoded by /usr/local/bin/decode-gcal-creds.sh
# into /data/google-calendar-mcp (Railway volume). We no longer decode into /root/.config.

if [ "${DEBUG_MCP:-}" = "1" ]; then
  echo "DEBUG_MCP=1" >&2
  echo "PATH=${PATH}" >&2
  which npx >&2 || true
  npx @cocal/google-calendar-mcp --help >&2 || true
  ls -la /data/google-calendar-mcp 2>/dev/null || true
  test -s /data/google-calendar-mcp/client_secret.json \
    && echo "✅ /data/google-calendar-mcp/client_secret.json present" \
    || echo "⚠️  /data/google-calendar-mcp/client_secret.json missing/empty"
  test -s /data/google-calendar-mcp/tokens.json \
    && echo "✅ /data/google-calendar-mcp/tokens.json present" \
    || echo "⚠️  /data/google-calendar-mcp/tokens.json missing/empty"
  echo "DEBUG_MCP done" >&2
fi

/usr/local/bin/decode-gcal-creds.sh || true
exec "$@"
