#!/usr/bin/env sh
set -u

CONFIG_DIR="/root/.config/google-calendar-mcp"

warn() {
  # Always to stderr
  echo "WARN: $*" >&2
}

info() {
  # Always to stderr (Railway logs)
  echo "INFO: $*" >&2
}

decode_b64_to_file() {
  var_name="$1"
  out_file="$2"

  # Indirect expansion is not POSIX; use eval carefully.
  eval "val=\${$var_name:-}"

  if [ -z "${val}" ]; then
    warn "${var_name} is not set; skipping write of ${out_file}"
    return 0
  fi

  # Strip accidental whitespace/newlines from Railway env var value
  tmp="$(mktemp 2>/dev/null || true)"
  if [ -z "${tmp}" ]; then
    warn "mktemp failed; cannot decode ${var_name} to ${out_file}; continuing"
    return 0
  fi

  cleaned="$(printf %s "${val}" | tr -d '\n\r ')"

  # base64 fallback:
  # Try: base64 -d
  # If it fails, try: base64 -D
  if printf %s "${cleaned}" | base64 -d > "${tmp}" 2>/dev/null; then
    mkdir -p "${CONFIG_DIR}" 2>/dev/null || true
    mv "${tmp}" "${out_file}" 2>/dev/null || true
    info "Wrote ${out_file} from ${var_name} (base64 -d)"
    return 0
  fi

  if printf %s "${cleaned}" | base64 -D > "${tmp}" 2>/dev/null; then
    mkdir -p "${CONFIG_DIR}" 2>/dev/null || true
    mv "${tmp}" "${out_file}" 2>/dev/null || true
    info "Wrote ${out_file} from ${var_name} (base64 -D)"
    return 0
  fi

  rm -f "${tmp}" 2>/dev/null || true
  warn "Failed to base64-decode ${var_name} into ${out_file} (base64 -d/-D both failed); continuing"
  return 0
}

decode_b64_to_file "GOOGLE_OAUTH_CLIENT_SECRET_B64" "${CONFIG_DIR}/client_secret.json"
decode_b64_to_file "GOOGLE_OAUTH_TOKENS_B64" "${CONFIG_DIR}/tokens.json"

if [ "${DEBUG_MCP:-}" = "1" ]; then
  echo "DEBUG_MCP=1" >&2
  echo "PATH=${PATH}" >&2
  command -v mcp-server >&2 || true
  mcp-server --help >&2 || true
  mcp-server google-calendar --help >&2 || true
  mcp-server --list >&2 || true
  mcp --help >&2 || true
  ls -la /root/.config/google-calendar-mcp 2>/dev/null || true
  test -s /root/.config/google-calendar-mcp/client_secret.json \
    && echo "✅ /root/.config/google-calendar-mcp/client_secret.json present" \
    || echo "⚠️  /root/.config/google-calendar-mcp/client_secret.json missing/empty"
  test -s /root/.config/google-calendar-mcp/tokens.json \
    && echo "✅ /root/.config/google-calendar-mcp/tokens.json present" \
    || echo "⚠️  /root/.config/google-calendar-mcp/tokens.json missing/empty"
  echo "DEBUG_MCP done" >&2
fi

exec "$@"