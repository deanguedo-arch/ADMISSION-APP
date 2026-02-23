#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env" ]]; then
  # shellcheck source=/dev/null
  source ".env"
fi

URL="${NEXTSTEP_WEBAPP_URL:-}"
if [[ -z "$URL" ]]; then
  echo "ERROR: NEXTSTEP_WEBAPP_URL is not set."
  echo "Copy .env.example to .env and set your Apps Script deployment URL."
  exit 1
fi

if [[ ! "$URL" =~ ^https:// ]]; then
  echo "ERROR: NEXTSTEP_WEBAPP_URL must be https."
  exit 1
fi

if [[ ! "$URL" =~ script\.google\.com/macros/s/ ]]; then
  echo "WARNING: URL does not look like an Apps Script deployment."
fi

for cmd in node npm npx xcodebuild xcrun; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: Missing required command: $cmd"
    exit 1
  fi
done

if ! command -v pod >/dev/null 2>&1; then
  echo "WARNING: CocoaPods not found. Install with: sudo gem install cocoapods"
fi

STATUS_CODE="$(curl -I -L -s -o /dev/null -w "%{http_code}" "$URL" || true)"
if [[ "$STATUS_CODE" != "200" && "$STATUS_CODE" != "302" && "$STATUS_CODE" != "307" ]]; then
  echo "WARNING: URL probe returned HTTP $STATUS_CODE. Verify deployment URL and access."
fi

echo "Preflight complete."
echo "URL: $URL"
