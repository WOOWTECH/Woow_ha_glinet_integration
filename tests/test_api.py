"""api.py: the challenge/login handshake, session handling and error mapping, against the in-memory router.

The real `GlinetClient._post` runs here (JSON parsing, exception mapping); only the aiohttp session under it is
replaced (see testkit.py). The same behaviours over a real loopback HTTP server are in test_api_wire.py.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import ssl
from types import SimpleNamespace

import aiohttp
import pytest
from mock_router import MockRouter

from custom_components.woow_glinet import api
from custom_components.woow_glinet.api import (
    METHOD_NOT_FOUND,
    GlinetApiError,
    GlinetAuthError,
    GlinetClient,
    GlinetDisconnected,
    GlinetInvalidAuth,
)
from testkit import HOST, PASSWORD, ROUTER_MAC, RouterWorld, connection_key


def rpc_error(code: int, message: str = "nope") -> bytes:
    return json.dumps({"id": 0, "jsonrpc": "2.0", "error": {"code": code, "message": message}}).encode()


# ---------------------------------------------------------------------------------- handshake
@pytest.mark.parametrize("hash_method", ["md5", "sha256", "sha512"])
@pytest.mark.parametrize("alg", [1, 5, 6])
async def test_handshake_for_every_alg_and_hash_method(world: RouterWorld, alg: int, hash_method: str) -> None:
    """crypt alg 1/5/6 (md5/sha256/sha512-crypt) x login digest md5/sha256/sha512: the router accepts the hash."""
    router = world.add(HOST, alg=alg, hash_method=hash_method)
    client = GlinetClient(world.session, HOST, "root", PASSWORD)

    info = await client.call("system", "get_info")

    assert info["mac"] == ROUTER_MAC
    assert (router.calls["challenge"], router.calls["login"]) == (1, 1)
    await client.call("system", "get_info")
    assert router.calls["login"] == 1, "the session id must be reused"


async def test_handshake_with_another_username(world: RouterWorld) -> None:
    router = world.add(HOST, username="admin", password="s3cret")
    await GlinetClient(world.session, HOST, "admin", "s3cret").call("system", "get_info")
    assert router.calls["login"] == 1


async def test_password_with_non_ascii_characters(world: RouterWorld) -> None:
    router = world.add(HOST, password="密碼 pässwörd ✓")
    info = await GlinetClient(world.session, HOST, "root", "密碼 pässwörd ✓").call("system", "get_info")
    assert info["mac"] == router.mac


# Independent known answers (Drepper's SHA-crypt spec; `openssl passwd -1 -salt saltsalt password` for md5): they do
# not go through MockRouter, so a mistake shared by the client and the mock cannot hide here.
CRYPT_VECTORS = [
    (1, "saltsalt", "password", "$1$saltsalt$qjXMvbEw8oaL.CzflDtaK/"),
    (5, "saltstring", "Hello world!", "$5$saltstring$5B8vYYiY.CVt1RlTTf8KbXBH3hsxY/GNooZaBBGWEc5"),
    (
        6,
        "saltstring",
        "Hello world!",
        "$6$saltstring$svn8UoSVapNtMuq1ukKS4tPQd8iKwSMHWjl/O817G3uBnIFNjnQJuesI68u4OTLiBFdcbYEdFCoEOfaS35inz1",
    ),
]


@pytest.mark.parametrize("hash_method", ["md5", "sha256", "sha512"])
@pytest.mark.parametrize(("alg", "salt", "password", "cipher"), CRYPT_VECTORS)
def test_login_hash_known_answers(alg: int, salt: str, password: str, cipher: str, hash_method: str) -> None:
    nonce = "0123456789abcdef"
    expected = getattr(hashlib, hash_method)(f"root:{cipher}:{nonce}".encode()).hexdigest()
    assert api._compute_login_hash(alg, salt, nonce, hash_method, "root", password) == expected


def test_login_hash_defaults_to_sha256_for_an_unknown_method() -> None:
    cipher = CRYPT_VECTORS[0][3]
    expected = hashlib.sha256(f"root:{cipher}:n".encode()).hexdigest()
    assert api._compute_login_hash(1, "saltsalt", "n", "whatever", "root", "password") == expected


def test_unsupported_crypt_algorithm_is_an_api_error() -> None:
    with pytest.raises(GlinetApiError, match="alg=7"):
        api._compute_login_hash(7, "salt", "n", "sha256", "root", "pw")


# ---------------------------------------------------------------------------------- wrong credentials
async def test_wrong_password_is_invalid_auth(world: RouterWorld, router: MockRouter) -> None:
    client = GlinetClient(world.session, HOST, "root", "wrong")
    with pytest.raises(GlinetInvalidAuth) as err:
        await client.login()
    assert err.value.code == -32000
    assert isinstance(err.value, GlinetAuthError)
    assert isinstance(err.value, GlinetApiError)
    assert not isinstance(err.value, GlinetDisconnected)


async def test_unknown_username_is_invalid_auth(world: RouterWorld, router: MockRouter) -> None:
    with pytest.raises(GlinetInvalidAuth) as err:
        await GlinetClient(world.session, HOST, "nobody", PASSWORD).call("system", "get_info")
    assert err.value.code == -32000


async def test_failed_login_does_not_poison_the_client(world: RouterWorld, router: MockRouter) -> None:
    """After a rejected login the next call logs in again from scratch (and succeeds once the router agrees)."""
    client = GlinetClient(world.session, HOST, "root", "changed-later")
    with pytest.raises(GlinetInvalidAuth):
        await client.call("system", "get_info")
    router.configure(password="changed-later")
    assert (await client.call("system", "get_info"))["mac"] == ROUTER_MAC


# ---------------------------------------------------------------------------------- session expiry
async def test_expired_session_is_renewed_transparently(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    first = await client.call("system", "get_info")
    router.configure(expire_sessions=True)  # every sid is now refused with -1

    assert await client.call("system", "get_info") == first
    assert router.calls["login"] == 2
    assert router.calls["(bad session)"] == 1


async def test_password_changed_behind_a_live_session_is_invalid_auth(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    await client.call("system", "get_info")
    router.configure(password="brand-new")  # drops the sessions as well
    with pytest.raises(GlinetInvalidAuth):
        await client.call("system", "get_info")
    assert router.calls["login"] == 2, "exactly one more attempt, no retry loop"


async def test_router_that_keeps_refusing_the_session_does_not_loop(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    """-1 on the call, a good re-login, and -1 again: give up with the auth error instead of trying forever."""
    await client.call("system", "get_info")
    world.inject("system.get_info", raw=rpc_error(-1, "Access denied"), times=None)
    with pytest.raises(GlinetAuthError) as err:
        await client.call("system", "get_info")
    assert not isinstance(err.value, GlinetInvalidAuth)  # the credentials are fine; the call is what is refused
    assert err.value.code == -1
    assert world.count("system.get_info") == 3  # the first good one + the refused attempt + its single retry
    assert router.calls["login"] == 2


async def test_eight_concurrent_calls_after_expiry_log_in_exactly_once(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    await client.call("system", "get_info")
    assert router.calls["login"] == 1
    router.configure(expire_sessions=True)

    results = await asyncio.gather(*(client.call("system", "get_info") for _ in range(8)))

    assert all(r["mac"] == ROUTER_MAC for r in results)
    assert router.calls["login"] == 2, "8 callers noticed the expiry, only one may log in"
    assert router.calls["challenge"] == 2
    assert router.calls["(bad session)"] == 8


async def test_eight_concurrent_first_calls_log_in_exactly_once(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    results = await asyncio.gather(*(client.call("system", "get_info") for _ in range(8)))
    assert len(results) == 8
    assert (router.calls["challenge"], router.calls["login"]) == (1, 1)


async def test_concurrent_calls_all_see_a_rejected_password(world: RouterWorld, router: MockRouter) -> None:
    client = GlinetClient(world.session, HOST, "root", "wrong")
    results = await asyncio.gather(*(client.call("system", "get_info") for _ in range(4)), return_exceptions=True)
    assert all(isinstance(r, GlinetInvalidAuth) for r in results)


# ---------------------------------------------------------------------------------- RPC errors
async def test_method_not_found_carries_its_code(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    with pytest.raises(GlinetApiError) as err:
        await client.call("nosuch", "method")
    assert err.value.code == METHOD_NOT_FOUND == -32601
    assert type(err.value) is GlinetApiError  # an unknown method is not an auth problem
    assert router.calls["login"] == 1  # ... so it must not trigger a re-login either
    assert "Method not found" in str(err.value)


async def test_other_rpc_errors_keep_code_and_message(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    router.configure(error_methods={"system.get_info": (-5, "Boom")})
    with pytest.raises(GlinetApiError) as err:
        await client.call("system", "get_info")
    assert err.value.code == -5
    assert "Boom" in str(err.value)
    assert type(err.value) is GlinetApiError


async def test_invalid_params_error(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    with pytest.raises(GlinetApiError) as err:
        await client.call("lan", "remove_static_bind", {"mac": "AA:BB:CC:DD:EE:01"})
    assert err.value.code == -32602


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b'{"error": {"message": "m"}}', 0),  # no code: 0
        (b'{"error": {"code": "x", "message": "m"}}', None),  # a code that is not a number: unknown
    ],
)
async def test_rpc_error_without_a_usable_code(world: RouterWorld, router: MockRouter, client: GlinetClient, raw: bytes, code: int | None) -> None:
    await client.call("system", "get_info")
    world.inject("system.get_info", raw=raw)
    with pytest.raises(GlinetApiError) as err:
        await client.call("system", "get_info")
    assert err.value.code == code
    assert type(err.value) is GlinetApiError


# ---------------------------------------------------------------------------------- malformed answers
MALFORMED_MODES = [True, "list", "html", "empty", "truncated"]  # MockRouter.malformed values


@pytest.mark.parametrize("mode", MALFORMED_MODES)
async def test_malformed_answer_to_login_is_an_api_error(world: RouterWorld, router: MockRouter, client: GlinetClient, mode: object) -> None:
    """HTML page, JSON list, truncated JSON, empty body, an object without result/error: always GlinetApiError."""
    router.configure(malformed=mode)
    with pytest.raises(GlinetApiError) as err:
        await client.login()
    assert type(err.value) is GlinetApiError


@pytest.mark.parametrize("mode", MALFORMED_MODES)
async def test_malformed_answer_to_a_call_is_an_api_error(world: RouterWorld, router: MockRouter, client: GlinetClient, mode: object) -> None:
    await client.call("system", "get_info")
    router.configure(malformed=mode)
    with pytest.raises(GlinetApiError) as err:
        await client.call("system", "get_info")
    assert type(err.value) is GlinetApiError
    assert router.calls["login"] == 1  # garbage is not a reason to log in again


@pytest.mark.parametrize(
    "raw",
    [
        b"null",
        b"123",
        b'"just a string"',
        b"true",
        b"[1, 2, 3]",
        b"",
        b"   ",
        b"\xff\xfe\x00not text",  # not even valid UTF-8
        b'{"error": "boom"}',
        b'{"error": null}',
        b'{"error": []}',
        b'{"id": 0}',
        b'{"result',
        b"<html><body>502 Bad Gateway</body></html>",
    ],
)
async def test_odd_response_bodies_never_leak_another_exception(world: RouterWorld, router: MockRouter, client: GlinetClient, raw: bytes) -> None:
    await client.call("system", "get_info")
    world.inject("system.get_info", raw=raw)
    with pytest.raises(GlinetApiError) as err:
        await client.call("system", "get_info")
    assert type(err.value) is GlinetApiError


async def test_http_error_status_with_a_json_error_body(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    """A reverse proxy answering 502/500 with its own JSON is still an API error, not a crash."""
    await client.call("system", "get_info")
    world.inject("system.get_info", raw=b'{"error": "mock failure"}', status=500)
    with pytest.raises(GlinetApiError):
        await client.call("system", "get_info")


async def test_http_500_from_the_router(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    router.configure(fail_rate=1.0)
    with pytest.raises(GlinetApiError) as err:
        await client.login()
    assert type(err.value) is GlinetApiError
    assert router.calls["(http 500)"] == 1


async def test_a_result_of_null_is_a_valid_answer(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    await client.call("system", "get_info")
    world.inject("system.get_info", raw=b'{"result": null}')
    assert await client.call("system", "get_info") is None


@pytest.mark.parametrize(
    "challenge",
    [
        [],  # Lua: an empty table is a list
        "text",
        None,
        {"alg": 1},  # fields missing
        {"alg": 1, "salt": "abcdefgh"},  # nonce missing
        {"alg": 7, "salt": "abcdefgh", "nonce": "n"},  # an algorithm nobody implements
        {"alg": "1", "salt": "abcdefgh", "nonce": "n"},  # wrong type
        {"alg": 1, "salt": 12345, "nonce": "n"},
    ],
)
async def test_malformed_challenge_is_an_api_error(world: RouterWorld, router: MockRouter, client: GlinetClient, challenge: object) -> None:
    world.inject("challenge", raw=json.dumps({"id": 0, "result": challenge}).encode())
    with pytest.raises(GlinetApiError) as err:
        await client.login()
    assert not isinstance(err.value, GlinetInvalidAuth)


@pytest.mark.parametrize("result", [[], "text", None, {"username": "root"}])
async def test_login_answer_without_a_session_id(world: RouterWorld, router: MockRouter, client: GlinetClient, result: object) -> None:
    world.inject("login", raw=json.dumps({"id": 0, "result": result}).encode())
    with pytest.raises(GlinetApiError) as err:
        await client.login()
    assert not isinstance(err.value, GlinetInvalidAuth)


async def test_login_error_on_challenge_step_is_invalid_auth(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    world.inject("challenge", raw=rpc_error(-32000, "Access denied"))
    with pytest.raises(GlinetInvalidAuth) as err:
        await client.login()
    assert err.value.code == -32000


# ---------------------------------------------------------------------------------- the connection itself
async def test_router_closing_the_connection_is_disconnected(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    """What a router that is rebooting does: it cuts the connection without answering."""
    await client.call("system", "get_info")
    router.configure(dark_for=60)  # dark_style 'reset'
    with pytest.raises(GlinetDisconnected) as err:
        await client.call("system", "get_info")
    assert isinstance(err.value, GlinetApiError)
    assert not isinstance(err.value, GlinetAuthError)


async def test_disconnect_while_logging_in(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    router.configure(dark_for=60)
    with pytest.raises(GlinetDisconnected):
        await client.login()


async def test_reboot_that_cuts_the_connection(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    router.reboot_style = "drop"
    with pytest.raises(GlinetDisconnected):
        await client.call("system", "reboot")
    assert router.calls["system.reboot"] == 1


@pytest.mark.parametrize(
    "exc",
    [
        aiohttp.ServerDisconnectedError("gone"),  # the router closed the connection without answering
        aiohttp.ClientOSError(104, "Connection reset by peer"),  # ... or reset it after we connected
        aiohttp.ClientOSError(32, "Broken pipe"),
    ],
    ids=["server-disconnected", "connection-reset", "broken-pipe"],
)
async def test_a_connection_cut_after_connecting_is_a_hang_up(world: RouterWorld, router: MockRouter, client: GlinetClient, exc: BaseException) -> None:
    """What a router that is rebooting does."""
    world.inject("challenge", exc=exc)
    with pytest.raises(GlinetDisconnected) as err:
        await client.login()
    assert err.value.__cause__ is exc


NEVER_CONNECTED = [
    aiohttp.ClientConnectorError(connection_key(), OSError(111, "Connection refused")),
    aiohttp.ClientConnectorError(connection_key(), OSError(65, "No route to host")),
    aiohttp.ClientConnectorError(connection_key(), OSError(101, "Network is unreachable")),
    aiohttp.ClientConnectorDNSError(connection_key(), OSError("Name or service not known")),
    aiohttp.ClientConnectorSSLError(connection_key(), OSError("TLS handshake failed")),
    aiohttp.ClientConnectorCertificateError(connection_key(), ssl.SSLCertVerificationError("certificate verify failed")),
    aiohttp.ClientProxyConnectionError(connection_key(), OSError(111, "proxy refused")),
]


@pytest.mark.parametrize("exc", NEVER_CONNECTED, ids=lambda e: f"{type(e).__name__}-{e.os_error if hasattr(e, 'os_error') else 'cert'}"[:48])
async def test_never_getting_connected_is_not_a_hang_up(world: RouterWorld, router: MockRouter, client: GlinetClient, exc: BaseException) -> None:
    """Connection refused, no route, DNS, TLS and certificate failures: the request never reached the router, so this
    must not look like 'the router went down' (a reboot that never happened was reported as done)."""
    world.inject("challenge", exc=exc)
    with pytest.raises(GlinetApiError) as err:
        await client.login()
    assert type(err.value) is GlinetApiError
    assert not isinstance(err.value, GlinetDisconnected)
    assert err.value.__cause__ is exc


async def test_never_getting_connected_during_a_call(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    await client.call("system", "get_info")
    world.inject("system.reboot", exc=NEVER_CONNECTED[0])
    with pytest.raises(GlinetApiError) as err:
        await client.call("system", "reboot")
    assert not isinstance(err.value, GlinetDisconnected)
    assert router.calls["system.reboot"] == 0


@pytest.mark.parametrize(
    "exc",
    [
        TimeoutError(),
        asyncio.TimeoutError(),
        aiohttp.ServerTimeoutError("timed out"),
        aiohttp.ConnectionTimeoutError("connect timed out"),
        aiohttp.ClientConnectionError("lost"),
        aiohttp.ClientPayloadError("body cut short"),
    ],
    ids=lambda e: type(e).__name__,
)
async def test_timeouts_and_other_client_errors_are_api_errors(world: RouterWorld, router: MockRouter, client: GlinetClient, exc: BaseException) -> None:
    world.inject("challenge", exc=exc)
    with pytest.raises(GlinetApiError) as err:
        await client.login()
    assert type(err.value) is GlinetApiError  # neither "disconnected" (a reboot) nor an auth failure


async def test_timeout_during_a_call(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    await client.call("system", "get_info")
    world.inject("system.get_info", exc=TimeoutError())
    with pytest.raises(GlinetApiError) as err:
        await client.call("system", "get_info")
    assert type(err.value) is GlinetApiError
    assert router.calls["login"] == 1


async def test_router_that_hangs_until_the_caller_gives_up(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    router.configure(dark_for=60, dark_style="hang")
    with pytest.raises(GlinetApiError) as err:
        await client.login()
    assert type(err.value) is GlinetApiError


async def test_unreachable_host(world: RouterWorld) -> None:
    """Nothing there: a plain GlinetApiError, not a hang-up."""
    client = GlinetClient(world.session, "192.0.2.99", "root", PASSWORD)
    with pytest.raises(GlinetApiError) as err:
        await client.login()
    assert not isinstance(err.value, GlinetDisconnected)


# ---------------------------------------------------------------------------------- request shape
async def test_request_payloads(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    await client.call("wifi", "set_config", {"iface_name": "guest2g", "enabled": True})
    challenge, login, call = world.requests
    assert challenge.payload == {"id": 0, "method": "challenge", "params": {"username": "root"}}
    assert login.payload["method"] == "login"
    assert set(login.payload["params"]) == {"username", "hash"}
    sid = router.sessions and next(iter(router.sessions))
    assert call.payload == {
        "id": 0,
        "method": "call",
        "params": [sid, "wifi", "set_config", {"iface_name": "guest2g", "enabled": True}],
    }


async def test_call_without_params_sends_an_empty_object(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    await client.call("system", "get_info")
    assert world.calls("system.get_info")[0].args == {}


@pytest.mark.parametrize(
    ("scheme", "verify_ssl", "ssl"),
    [("https", False, False), ("https", True, None), ("http", False, False)],
)
async def test_url_timeout_and_ssl_arguments(world: RouterWorld, router: MockRouter, scheme: str, verify_ssl: bool, ssl: object) -> None:
    world.add("192.0.2.10:8080", router)
    client = GlinetClient(world.session, "192.0.2.10:8080", "root", PASSWORD, scheme=scheme, verify_ssl=verify_ssl)
    await client.call("system", "get_info")
    for request in world.requests:
        assert request.url == f"{scheme}://192.0.2.10:8080/rpc"
        assert request.timeout == 10
        assert request.ssl is ssl


async def test_two_clients_do_not_share_a_session(world: RouterWorld, router: MockRouter) -> None:
    one = GlinetClient(world.session, HOST, "root", PASSWORD)
    two = GlinetClient(world.session, HOST, "root", PASSWORD)
    await one.call("system", "get_info")
    await two.call("system", "get_info")
    assert router.calls["login"] == 2


async def test_calls_use_the_default_timeout(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    await client.call("system", "get_info")
    assert [r.timeout for r in world.requests] == [10, 10, 10], "challenge, login and the call"


async def test_a_call_can_ask_for_more_time_without_slowing_the_login_down(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    """Applying a Wi-Fi change takes the router about 9 s: that call gets a longer timeout, the login does not."""
    await client.call("wifi", "set_config", {"iface_name": "guest2g", "enabled": True}, timeout=40)
    assert [(r.method, r.timeout) for r in world.requests] == [("challenge", 10), ("login", 10), ("wifi.set_config", 40)]


async def test_the_longer_timeout_also_applies_to_the_retry_after_a_session_expiry(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    await client.call("system", "get_info")
    router.configure(expire_sessions=True)
    before = len(world.requests)

    await client.call("wifi", "set_config", {"iface_name": "guest2g", "enabled": True}, timeout=33)

    assert [(r.method, r.timeout) for r in world.requests[before:]] == [
        ("wifi.set_config", 33), ("challenge", 10), ("login", 10), ("wifi.set_config", 33),
    ]  # fmt: skip


async def test_timeout_can_be_given_positionally_and_defaults_stay_per_call(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    await client.call("system", "get_info", None, 7)
    await client.call("system", "get_info")
    assert [r.timeout for r in world.calls("system.get_info")] == [7, 10]


# ---------------------------------------------------------------------------------- robustness against odd routers
@pytest.mark.parametrize(
    "challenge",
    [
        {"alg": 1, "salt": "bad$salt!", "nonce": "n"},
        {"alg": 5, "salt": "has space", "nonce": "n"},
        {"alg": 6, "salt": "tab\tsalt", "nonce": "n"},
        {"alg": 1, "salt": "abcdefghijklmnop", "nonce": "n"},  # md5-crypt takes at most 8 characters
    ],
    ids=["bad-chars-md5", "bad-chars-sha256", "bad-chars-sha512", "too-long-md5"],
)
async def test_unusable_salt_is_an_api_error_not_a_value_error(world: RouterWorld, router: MockRouter, client: GlinetClient, challenge: dict) -> None:
    world.inject("challenge", raw=json.dumps({"id": 0, "result": challenge}).encode())
    with pytest.raises(GlinetApiError) as err:
        await client.login()
    assert not isinstance(err.value, GlinetInvalidAuth), "a broken answer is not a rejected password"


async def test_hostile_deeply_nested_json_is_an_api_error(world: RouterWorld, router: MockRouter, client: GlinetClient) -> None:
    await client.call("system", "get_info")
    world.inject("system.get_info", raw=b"[" * 200000 + b"]" * 200000)
    with pytest.raises(GlinetApiError) as err:
        await client.call("system", "get_info")
    assert type(err.value) is GlinetApiError


async def test_md5_login_digest_works_where_python_forbids_md5_for_security(world: RouterWorld, monkeypatch: pytest.MonkeyPatch) -> None:
    """FIPS-enabled Python builds refuse hashlib.md5() unless usedforsecurity=False is passed (only api.py's own use is patched)."""
    real = hashlib.md5

    def fips_md5(data: bytes = b"", *, usedforsecurity: bool = True) -> object:
        if usedforsecurity:
            raise ValueError("[digital envelope routines] unsupported")
        return real(data, usedforsecurity=False)

    monkeypatch.setattr(api, "hashlib", SimpleNamespace(md5=fips_md5, sha256=hashlib.sha256, sha512=hashlib.sha512))
    router = world.add(HOST, hash_method="md5")
    assert (await GlinetClient(world.session, HOST, "root", PASSWORD).call("system", "get_info"))["mac"] == router.mac
