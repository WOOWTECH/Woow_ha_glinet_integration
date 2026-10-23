# Panel browser tests

`harness/index.html` loads the built panel with a fake Home Assistant (`hass.callWS` / `subscribeMessage`) and the
scenarios in `harness/fixtures.js`, so the panel can be driven in a real browser without a router or Home Assistant:
situations a single router cannot produce (AP mode, several routers, an unreachable one, allow-list mode, hundreds of
devices, hostile or very long names, missing firmware features, a rejected login).

    npm run build          # the harness loads custom_components/woow_glinet/frontend/woow-glinet-panel.js
    npm run e2e            # CHROME_PATH=... to use an installed Chrome; E2E_BROWSERS=all adds Firefox and WebKit

Not included here (they need a real Home Assistant and router, and credentials): the live checks run before the 0.4.0
release (reboot, outage, restart with the panel open, 200-device performance, XSS through a mock router).
