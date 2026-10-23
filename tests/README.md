# Tests

Offline pytest suite for the integration (Home Assistant 2026.10, Python 3.14). No router, no network, no Home Assistant instance:
every router is `tools/mock_router.py`, running inside the test process.

## Run

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r tests/requirements_test.txt   # pins homeassistant, pytest, pytest-asyncio ...
.venv/bin/python -m pytest tests -q                                       # ~50 s; add -n 4 for ~16 s
.venv/bin/python -m pytest tests -q --cov=custom_components.woow_glinet --cov-branch --cov-report=term-missing
.venv/bin/python -m pytest tests/test_actions.py -k reboot -q             # a subset
```

CI (`.github/workflows/validate.yml`) runs the same command and fails below 90 % coverage. Coverage writes `.coverage` into the
current directory: set `COVERAGE_FILE` if you do not want that in the repository.

## Layout

| File | Covers |
|---|---|
| `conftest.py`, `testkit.py` | fixtures; the in-process transport (`RouterWorld`) and small helpers |
| `test_api.py`, `test_api_wire.py` | login handshake, session expiry, error mapping; the same over real aiohttp on loopback (TLS included) |
| `test_actions.py` | every write: Wi-Fi, blocking, static IP, forget, reboot; validation, activity log, timeouts |
| `test_activity.py`, `test_history.py`, `test_feed.py` | activity log + store, traffic history, panel snapshot and live feed |
| `test_coordinator.py` | polling, firmware differences, Lua `[]` quirks, mode changes, auth, devices |
| `test_config_flow.py` | user / reauth / reconfigure / options flows |
| `test_websocket_api.py`, `test_panel.py` | the panel's commands (admin only) and its registration |
| `test_services.py` | `add_static_ip`, `remove_static_ip`, who may call them |
| `test_platforms.py`, `test_tracker_migration.py` | entities, unique ids, names, the tracker unique-id migration |
| `test_diagnostics.py`, `test_static.py` | the diagnostics file (allow-list); translations, services.yaml, manifest, CI file |

## Conventions

- **Never touch a network.** The `world` fixture replaces the integration's aiohttp session; pytest-socket and a loopback-only guard
  in `conftest.py` refuse anything else. Hosts are RFC 5737 addresses (`192.0.2.x`). Only `test_api_wire.py` opens sockets, to 127.0.0.1.
- **Use the mock, steer it.** `world.add(host, **kw)` makes a deterministic router (6 clients: 0, 1, 3, 4 online; 2, 5 offline; no random
  flips, no sleeping); `router.configure(...)` for its own switches; `override(router, "object.method", fn)` / `remove_method(...)` to
  make a firmware say something else; `world.inject("object.method", exc=... | raw=...)` to break the wire; `world.count/calls` to see what was asked.
- **Assert on what the router ends up with**, the RPC calls made, and the activity log, not on mocks of mocks.
- **Look entities up by unique id** (`entity_id(hass, domain, unique_id)`), never by guessing entity ids; unique ids are pinned on purpose.
- **Time:** use the `freezer` fixture (declare it first, so timers are created on the frozen clock); the 5 s live poll and the coordinator
  run as *background* tasks: `await hass.async_block_till_done(wait_background_tasks=True)`. Store writes need `freezer.tick(...)` too.
- **A test that proves a lock or a check matters** has a companion that removes it and expects the failure (login lock, unblock lock,
  panel registration lock, diagnostics allow-list).
- **Known bugs are strict xfails** with a `BUG:` reason (file and line). When one is fixed the test turns red (`XPASS(strict)`):
  delete the marker. See them all with `pytest tests -q -rx`; see why one fails with `--runxfail -k <name>`.
- Disabled-by-default entities (the Wi-Fi password): request the `entity_registry_enabled_by_default` fixture.

## The mock router

`tools/mock_router.py` implements the firmware's `/rpc` (challenge, login, sessions, the object/method names and response shapes of a
GL-SFT1200 on 4.8.3, including what is broken there). The suite calls `MockRouter.handle(payload)` through `testkit.RouterWorld`; the same
file runs as a server for system tests against a real Home Assistant (`python tools/mock_router.py --port 8780 --clients 60`).
