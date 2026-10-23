"""api.py over a real HTTP connection: the real aiohttp client against MockRouter served on loopback.

Everything in test_api.py uses an in-process stand-in for the session. These few tests keep us honest about the
parts that stand-in cannot prove: aiohttp really accepts the arguments GlinetClient passes (int timeout, ssl=None /
False), keep-alive connections survive the handshake, a dropped connection / a hang / a TLS failure surface as the
exceptions GlinetClient maps. Only 127.0.0.1 is ever touched.
"""

from __future__ import annotations

import asyncio
import datetime
import ipaddress
import json
import ssl
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from mock_router import DropConnection, HttpFailure, MockRouter

from custom_components.woow_glinet.api import (
    METHOD_NOT_FOUND,
    GlinetApiError,
    GlinetClient,
    GlinetDisconnected,
    GlinetInvalidAuth,
)
from testkit import PASSWORD, ROUTER_MAC, quiet

pytestmark = pytest.mark.usefixtures("socket_enabled")  # loopback only; the plugin still refuses other hosts


def self_signed_context(directory: Path) -> ssl.SSLContext:
    """A throw-away server certificate for 127.0.0.1 (what a GL.iNet router presents: self-signed)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=2))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
        .sign(key, hashes.SHA256())
    )
    cert_file, key_file = directory / "cert.pem", directory / "key.pem"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)
    return context


@dataclass
class Wire:
    router: MockRouter
    server: TestServer
    session: aiohttp.ClientSession
    release: asyncio.Event
    delay: float = 0.0  # seconds the router takes to answer a call (not the login)
    reset: bool = False  # answer a call by resetting the TCP connection (RST) instead of closing it politely

    @property
    def host(self) -> str:
        return f"127.0.0.1:{self.server.port}"

    def client(self, password: str = PASSWORD, **kwargs: object) -> GlinetClient:
        scheme = "https" if self.server.scheme == "https" else "http"
        return GlinetClient(self.session, self.host, "root", password, scheme=scheme, **kwargs)  # type: ignore[arg-type]


async def start_wire(router: MockRouter, ssl_context: ssl.SSLContext | None = None) -> Wire:
    release = asyncio.Event()
    wire: Wire

    async def rpc(request: web.Request) -> web.StreamResponse:
        payload = await request.json()
        if payload.get("method") == "call":
            if wire.reset:
                request.transport.abort()  # RST
                return web.Response()
            if wire.delay:
                await asyncio.sleep(wire.delay)
        try:
            out = router.handle(payload)
        except DropConnection as drop:
            if str(drop) == "hang":
                await release.wait()
            request.transport.close()  # the router cuts the connection without answering
            return web.Response()
        except HttpFailure as fail:
            return web.json_response({"error": "mock failure"}, status=fail.status)
        body = out if isinstance(out, bytes) else json.dumps(out).encode()
        return web.Response(body=body, content_type="application/json")

    app = web.Application()
    app.router.add_post("/rpc", rpc)
    server = TestServer(app)
    if ssl_context is not None:
        await server.start_server(ssl=ssl_context)
    else:
        await server.start_server()
    wire = Wire(router, server, aiohttp.ClientSession(), release)
    return wire


@pytest.fixture
async def wire() -> AsyncGenerator[Wire]:
    wire = await start_wire(quiet(MockRouter()))
    yield wire
    wire.release.set()
    await wire.session.close()
    await wire.server.close()


@pytest.fixture
async def tls_wire(tmp_path: Path) -> AsyncGenerator[Wire]:
    wire = await start_wire(quiet(MockRouter()), self_signed_context(tmp_path))
    yield wire
    wire.release.set()
    await wire.session.close()
    await wire.server.close()


# ------------------------------------------------------------------------------------------------ the happy paths
@pytest.mark.parametrize("alg", [1, 5, 6])
async def test_handshake_over_http(wire: Wire, alg: int) -> None:
    wire.router.alg = alg
    info = await wire.client().call("system", "get_info")
    assert info["mac"] == ROUTER_MAC
    assert wire.router.calls["login"] == 1


async def test_session_is_reused_and_renewed_over_keep_alive(wire: Wire) -> None:
    client = wire.client()
    await client.call("system", "get_info")
    await client.call("system", "get_info")
    assert wire.router.calls["login"] == 1
    wire.router.configure(expire_sessions=True)
    assert (await client.call("system", "get_info"))["mac"] == ROUTER_MAC
    assert wire.router.calls["login"] == 2


async def test_eight_concurrent_calls_after_expiry_log_in_once(wire: Wire) -> None:
    client = wire.client()
    await client.call("system", "get_info")
    wire.router.configure(expire_sessions=True)
    results = await asyncio.gather(*(client.call("clients", "get_list") for _ in range(8)))
    assert all("clients" in r for r in results)
    assert wire.router.calls["login"] == 2


async def test_wrong_password_and_unknown_method(wire: Wire) -> None:
    with pytest.raises(GlinetInvalidAuth):
        await wire.client("wrong").call("system", "get_info")
    with pytest.raises(GlinetApiError) as err:
        await wire.client().call("no", "such")
    assert err.value.code == METHOD_NOT_FOUND


# ------------------------------------------------------------------------------------------------ not a router / broken router
@pytest.mark.parametrize("mode", [True, "list", "html", "empty", "truncated"])
async def test_garbage_answers(wire: Wire, mode: object) -> None:
    wire.router.configure(malformed=mode)
    with pytest.raises(GlinetApiError) as err:
        await wire.client().login()
    assert type(err.value) is GlinetApiError


async def test_http_500(wire: Wire) -> None:
    wire.router.configure(fail_rate=1.0)
    with pytest.raises(GlinetApiError) as err:
        await wire.client().login()
    assert type(err.value) is GlinetApiError


async def test_a_web_server_without_rpc_is_not_a_router() -> None:
    """Pointing the integration at some other web server: 404 with an HTML body."""
    app = web.Application()
    server = TestServer(app)
    await server.start_server()
    session = aiohttp.ClientSession()
    try:
        client = GlinetClient(session, f"127.0.0.1:{server.port}", "root", PASSWORD, scheme="http")
        with pytest.raises(GlinetApiError, match="404"):
            await client.login()
    finally:
        await session.close()
        await server.close()


# ------------------------------------------------------------------------------------------------ the connection
async def test_connection_cut_by_the_router(wire: Wire) -> None:
    client = wire.client()
    await client.call("system", "get_info")
    wire.router.configure(dark_for=60)
    with pytest.raises(GlinetDisconnected):
        await client.call("system", "get_info")


async def test_router_that_never_answers_times_out(wire: Wire) -> None:
    client = wire.client()
    await client.call("system", "get_info")
    wire.router.configure(dark_for=60, dark_style="hang")
    started = time.monotonic()
    with pytest.raises(GlinetApiError) as err:
        await client.call("system", "get_info", timeout=0.3)
    assert type(err.value) is GlinetApiError  # a timeout is not "the router cut the connection"
    assert time.monotonic() - started < 5, "the per-call timeout reached aiohttp: it did not wait for the default 10 s"


async def test_a_slow_router_is_waited_for_exactly_as_long_as_the_call_allows(wire: Wire) -> None:
    """The reason for the per-call timeout: a Wi-Fi change takes the router ~9 s, far longer than a normal answer."""
    client = wire.client()
    await client.call("system", "get_info")
    wire.delay = 0.6

    with pytest.raises(GlinetApiError):
        await client.call("system", "get_info", timeout=0.2)  # not long enough
    assert (await client.call("system", "get_info", timeout=5))["mac"] == ROUTER_MAC  # long enough
    assert (await client.call("system", "get_info", timeout=5))["mac"] == ROUTER_MAC


async def test_reboot_that_cuts_the_connection(wire: Wire) -> None:
    wire.router.reboot_style = "drop"
    with pytest.raises(GlinetDisconnected):
        await wire.client().call("system", "reboot")


async def test_connection_reset_by_the_router_is_a_hang_up(wire: Wire) -> None:
    """A TCP reset (what a router that is going down may send) reaches the client as a disconnect, like a polite close."""
    client = wire.client()
    await client.call("system", "get_info")
    wire.reset = True
    with pytest.raises(GlinetDisconnected):
        await client.call("system", "reboot")


async def test_connection_refused_is_an_api_error_not_a_hang_up() -> None:
    """Nothing listens on port 1: the request never reached a router, so this must not look like 'it is rebooting'
    (see test_actions.py: reboot against a dead router is a failure)."""
    async with aiohttp.ClientSession() as session:
        client = GlinetClient(session, "127.0.0.1:1", "root", PASSWORD, scheme="http")
        with pytest.raises(GlinetApiError) as err:
            await client.login()
        assert type(err.value) is GlinetApiError and not isinstance(err.value, GlinetDisconnected)
        assert isinstance(err.value.__cause__, aiohttp.ClientConnectorError)


# ------------------------------------------------------------------------------------------------ TLS
async def test_self_signed_certificate_without_verification(tls_wire: Wire) -> None:
    """The normal GL.iNet setup: https with the router's own certificate and 'verify SSL' off."""
    info = await tls_wire.client(verify_ssl=False).call("system", "get_info")
    assert info["mac"] == ROUTER_MAC


async def test_self_signed_certificate_with_verification_is_refused(tls_wire: Wire) -> None:
    with pytest.raises(GlinetApiError) as err:
        await tls_wire.client(verify_ssl=True).login()
    assert isinstance(err.value.__cause__, aiohttp.ClientConnectorCertificateError)
    assert not isinstance(err.value, GlinetDisconnected), "a certificate problem is not a router hanging up"


async def test_https_to_a_plain_http_port_is_an_api_error(wire: Wire) -> None:
    """Choosing 'https' for a router that only speaks http (a common mistake in the config form)."""
    client = GlinetClient(wire.session, wire.host, "root", PASSWORD, scheme="https", verify_ssl=False)
    with pytest.raises(GlinetApiError) as err:
        await client.login()
    assert not isinstance(err.value, GlinetDisconnected)


async def test_http_to_a_tls_port_is_an_api_error(tls_wire: Wire) -> None:
    client = GlinetClient(tls_wire.session, tls_wire.host, "root", PASSWORD, scheme="http")
    with pytest.raises(GlinetApiError):  # (the TLS server drops a plain-text request: either flavour is fine)
        await client.login()

