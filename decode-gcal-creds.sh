#!/usr/bin/env sh
set -u

DIR="/data/google-calendar-mcp"

warn() {
  echo "WARN: $*" >&2
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

  mkdir -p "${DIR}" 2>/dev/null || true

  cleaned="$(printf %s "${val}" | tr -d '\n\r ')"
  tmp="$(mktemp 2>/dev/null || true)"
  if [ -z "${tmp}" ]; then
    warn "mktemp failed; cannot decode ${var_name} to ${out_file}; continuing"
    return 0
  fi

  # base64 fallback:
  # Try: base64 -d
  # If it fails, try: base64 -D
  if printf %s "${cleaned}" | base64 -d > "${tmp}" 2>/dev/null; then
    mv "${tmp}" "${out_file}" 2>/dev/null || true
    return 0
  fi

  if printf %s "${cleaned}" | base64 -D > "${tmp}" 2>/dev/null; then
    mv "${tmp}" "${out_file}" 2>/dev/null || true
    return 0
  fi

  rm -f "${tmp}" 2>/dev/null || true
  warn "Failed to base64-decode ${var_name} into ${out_file} (base64 -d/-D both failed); continuing"
  return 0
}

decode_b64_to_file "GCAL_OAUTH_KEYS_B64" "${DIR}/client_secret.json"
decode_b64_to_file "GCAL_TOKENS_B64" "${DIR}/tokens.json"


