"""Async client for the GL.iNet /rpc JSON-RPC API (firmware 4.x).

Protocol notes (reverse-engineered 2026-10-22 from the device's own
/usr/lib/oui-httpd on a GL-SFT1200, cross-checked against
github.com/vithurshanselvarajah/ha-glinet-router):

    1. POST {"method":"challenge","params":{"username":...}}
       -> {"result": {"alg": 1|5|6, "salt", "nonce", "hash-method"}}
    2. cipher = crypt(password, alg, salt)   (1=md5, 5=sha256, 6=sha512)
    3. login_hash = hash_method(f"{username}:{cipher}:{nonce}")
    4. POST {"method":"login","params":{"username":..., "hash": login_hash}}
       -> {"result": {"sid": ...}}
    5. POST {"method":"call","params":[sid, object, method, args]}

`object` is not a ubus object name - it maps to a GL.iNet RPC module
file under /usr/lib/oui-httpd/rpc/<object> (clients, lan, wifi,
firewall, black_white_list, system, ...).

Error code -1 means the session/nonce expired (re-login and retry);
-32000 means the username/password was rejected.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

from aiohttp import ClientError, ClientSession
from passlib.hash import md5_crypt, sha256_crypt, sha512_crypt

_LOGGER = logging.getLogger(__name__)

_TOKEN_ERROR_CODE = -1
_AUTH_ERROR_CODE = -32000
_TIMEOUT = 10


class GlinetApiError(Exception):
    """Could not complete a request to the router."""


class GlinetAuthError(GlinetApiError):
    """The router rejected the username/password, or the session expired."""


def _compute_login_hash(
    alg: int, salt: str, nonce: str, hash_method: str, username: str, password: str
) -> str:
    """Blocking crypt(3)-style hash. Call via the executor, not on the event loop."""
    if alg == 1:
        cipher = md5_crypt.using(salt=salt).hash(password)
    elif alg == 5:
        cipher = sha256_crypt.using(salt=salt, rounds=5000).hash(password)
    elif alg == 6:
        cipher = sha512_crypt.using(salt=salt, rounds=5000).hash(password)
    else:
        raise GlinetApiError(f"路由器要求不支援的雜湊演算法 alg={alg}")

    data = f"{username}:{cipher}:{nonce}".encode()
    if hash_method == "sha512":
        return hashlib.sha512(data).hexdigest()
    if hash_method == "md5":
        return hashlib.md5(data, usedforsecurity=False).hexdigest()
    return hashlib.sha256(data).hexdigest()


class GlinetClient:
    """Minimal async client for one GL.iNet router's /rpc endpoint."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        username: str,
        password: str,
        scheme: str = "https",
        verify_ssl: bool = False,
    ) -> None:
        self._session = session
        self._base_url = f"{scheme}://{host}/rpc"
        self._username = username
        self._password = password
        self._ssl: bool | None = None if verify_ssl else False
        self._sid: str | None = None
        # The coordinator, the panel's live poll and the entities share one client: only one of
        # them may log in at a time, the others then reuse the session it got.
        self._login_lock = asyncio.Lock()

    async def _post(self, payload: dict[str, Any]) -> Any:
        try:
            async with self._session.post(
                self._base_url, json=payload, timeout=_TIMEOUT, ssl=self._ssl
            ) as resp:
                data = await resp.json(content_type=None)
        except (ClientError, asyncio.TimeoutError) as err:
            raise GlinetApiError(f"無法連線到 {self._base_url}：{err}") from err

        if "result" in data:
            return data["result"]

        error = data.get("error", {})
        code = error.get("code", 0)
        message = error.get("message", "unknown error")
        if code in (_TOKEN_ERROR_CODE, _AUTH_ERROR_CODE):
            raise GlinetAuthError(f"{message} (code {code})")
        raise GlinetApiError(f"{message} (code {code})")

    async def login(self) -> None:
        """Run challenge -> login and cache the session id."""
        challenge = await self._post(
            {"id": 0, "method": "challenge", "params": {"username": self._username}}
        )
        login_hash = await asyncio.get_running_loop().run_in_executor(
            None,
            _compute_login_hash,
            challenge["alg"],
            challenge["salt"],
            challenge["nonce"],
            challenge.get("hash-method", "sha256"),
            self._username,
            self._password,
        )
        result = await self._post(
            {
                "id": 0,
                "method": "login",
                "params": {"username": self._username, "hash": login_hash},
            }
        )
        self._sid = result["sid"]

    async def _ensure_login(self, stale: str | None = None) -> str:
        """A valid session id: log in unless one exists that is not the `stale` one just refused."""
        async with self._login_lock:
            if self._sid is None or self._sid == stale:
                await self.login()
            return self._sid  # type: ignore[return-value]

    async def call(self, obj: str, method: str, params: dict[str, Any] | None = None) -> Any:
        """Call <object>.<method>, logging in first / again as needed."""
        sid = self._sid or await self._ensure_login()

        payload = {"id": 0, "method": "call", "params": [sid, obj, method, params or {}]}
        try:
            return await self._post(payload)
        except GlinetAuthError:
            _LOGGER.debug("session 過期，重新登入後重試 %s.%s", obj, method)
            payload["params"][0] = await self._ensure_login(stale=sid)
            return await self._post(payload)
