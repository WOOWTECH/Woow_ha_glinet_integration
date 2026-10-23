#!/usr/bin/env bash
# Browser tests of the panel against a fake Home Assistant (e2e/harness): scenarios (AP mode, several routers, allow-list
# mode, 24 devices ...), resilience (feed lost, startup retry, rejected login, missing firmware features), overflow with
# very long names, accessibility (axe). Needs the bundle built first (`npm run build`).
#   CHROME_PATH=/path/to/chrome   use an installed Chrome instead of Playwright's Chromium
#   E2E_BROWSERS=all              also run the cross-browser check in Firefox and WebKit (`npx playwright-core install firefox webkit`)
set -euo pipefail
cd "$(dirname "$0")/../.."   # the repo root, so the harness can load custom_components/.../woow-glinet-panel.js
PORT=${E2E_PORT:-8765}
python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
sleep 1
cd frontend
export E2E_BASE="http://127.0.0.1:$PORT/frontend/e2e/harness/index.html"
status=0
for t in scenarios resilience overflow axe; do echo "== $t"; node "e2e/$t.mjs" || status=1; done
if [ "${E2E_BROWSERS:-chrome}" = "all" ]; then echo "== cross-browser"; node e2e/xbrowser.mjs || status=1; fi
exit $status
