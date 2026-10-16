#!/usr/bin/env bash
# Post-deploy check: the backend must refuse /api and /_allauth requests that skip the web proxy.
# Usage: scripts/check_backend_gate.sh https://<backend-host>
set -euo pipefail

base_url="${1:?usage: $0 <backend base url>}"
base_url="${base_url%/}"
failures=0

expect_status() {
  local expected="$1" method="$2" path="$3"
  local actual
  actual="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X "$method" \
    -H 'Content-Type: application/json' ${4:+-d "$4"} "$base_url$path")"
  if [[ "$actual" == "$expected" ]]; then
    echo "ok    $method $path -> $actual"
  else
    echo "FAIL  $method $path -> $actual (expected $expected)"
    failures=$((failures + 1))
  fi
}

expect_status 403 POST /api/v1/predict/stream '{"query":"Bayern v Dortmund"}'
expect_status 403 GET /api/v1/fixtures
expect_status 403 GET /_allauth/browser/v1/config
expect_status 200 GET /api/v1/health

exit $((failures > 0 ? 1 : 0))
