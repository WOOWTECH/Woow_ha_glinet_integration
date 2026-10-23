#!/usr/bin/env python3
"""A GL.iNet firmware-4.x /rpc server in memory, for tests.

Same login handshake (challenge -> crypt -> login -> sid), same object/method names and the same response shapes
as a real GL-SFT1200 on 4.8.3 (read from one), including the things that are broken there: lan.remove_static_bind
always answers "Invalid params", and black_white_list.set_single_mac with operate=remove silently does nothing.

Three ways to use it:
  * import MockRouter and call .handle(payload) in-process (the pytest suite does);
  * run it as a server for system tests against a real Home Assistant:
        uv run --python 3.13 --with passlib python tools/mock_router.py --port 8780 --clients 60
    and add the integration with host "<this machine>:8780", scheme http;
  * steer it while it runs: POST /__control {"latency": 1.5, "clients": 150, "password": "new", ...},
    read /__state for the per-method request counts.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import random
import secrets
import string
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from passlib.hash import md5_crypt, sha256_crypt, sha512_crypt

MODE_CODES = {"router": 0, "wds": 1, "relay": 2, "mesh": 3, "ap": 4, "passthrough": 6}
NAMES = ["iPhone-Ann", "MacBook Pro", "Living-room TV", "Hue Bridge", "ESP32-kitchen", "HP LaserJet", "", "Galaxy-S24",
         "Nest Thermostat", "Switch-Lite", "Echo Dot", "Roborock", "iPad", "Pixel-8", "NAS", "Camera-front", "Sonos",
         "Desktop-PC", "Laptop-Bob", "Kindle", "客廳電視", "小米掃地機", "Printer-2F", "Meeting-room-panel"]


class RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


class DropConnection(Exception):
    """The server should cut the connection without answering (a router going down)."""


class HttpFailure(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


def _crypt(alg: int, password: str, salt: str) -> str:
    if alg == 1:
        return md5_crypt.using(salt=salt).hash(password)
    if alg == 5:
        return sha256_crypt.using(salt=salt, rounds=5000).hash(password)
    return sha512_crypt.using(salt=salt, rounds=5000).hash(password)


def _digest(method: str, data: bytes) -> str:
    return getattr(hashlib, method)(data).hexdigest()


class MockRouter:
    """The router's state and its JSON-RPC dispatcher (thread-safe)."""

    def __init__(self, *, username: str = "root", password: str = "mockpass", mac: str = "94:83:C4:00:00:01",
                 clients: int = 6, mode: str = "router", alg: int = 1, hash_method: str = "sha256", wifi: str = "dual",
                 seed: int = 1, session_ttl: float = 1800.0, nonce_ttl: float = 10.0) -> None:
        self.lock = threading.RLock()
        self.rng = random.Random(seed)
        self.username, self.password, self.mac = username, password, mac.upper()
        self.mode, self.alg, self.hash_method, self.wifi_layout = mode, alg, hash_method, wifi
        self.session_ttl, self.nonce_ttl = session_ttl, nonce_ttl
        self.sessions: dict[str, float] = {}  # sid -> last use
        self.nonces: dict[str, tuple[float, str]] = {}  # nonce -> (issued, salt)
        self.calls: Counter[str] = Counter()
        self.boot = time.time() - 86400
        self.dark_until = 0.0
        # behaviour switches (see configure)
        self.latency = 0.0
        self.fail_rate = 0.0  # share of requests answered with HTTP 500
        self.dark_style = "reset"  # what a down router does: "reset" the connection, or "hang" until the caller gives up
        self.malformed: Any = False  # True/"dict": no result/error; "list"; "html"; "empty"; "truncated"
        self.error_methods: dict[str, tuple[int, str]] = {}  # "object.method" -> (code, message)
        self.reboot_seconds = 20.0
        self.reboot_style = "respond"  # "respond": answer, then go dark; "drop": cut the connection, then go dark
        self.wifi_apply_seconds = 0.2
        self.firmware = "4.8.3"
        self.black_mac: list[str] = []
        self.white_mac: list[str] = []
        self.blacklist_mode = "black"
        self.static_binds: list[dict[str, str]] = []
        self.clients: list[dict[str, Any]] = []
        self.set_clients(clients)
        self._build_wifi()
        self._last_tick = time.time()
        self.methods = {
            "system.get_info": self.system_get_info, "system.get_status": self.system_get_status,
            "system.reboot": self.system_reboot, "netmode.get_mode": lambda p: {"mode": self.mode},
            "clients.get_wan_speed": self.clients_get_wan_speed, "clients.get_list": self.clients_get_list,
            "clients.remove_offline": self.clients_remove_offline, "wifi.get_config": self.wifi_get_config,
            "wifi.set_config": self.wifi_set_config, "lan.get_static_bind_list": self.lan_get_static_bind_list,
            "lan.add_static_bind": self.lan_add_static_bind, "lan.remove_static_bind": self.lan_remove_static_bind,
            "black_white_list.get_config": self.bwl_get_config, "black_white_list.set_config": self.bwl_set_config,
            "black_white_list.set_single_mac": self.bwl_set_single_mac,
            "firewall.get_wan_access": lambda p: {"enable_https": True, "enable_ping": False, "enable_ssh": False,
                                                 "whitelist": [], "enable_whitelist": False},
        }

    # ---------------------------------------------------------------- steering
    def configure(self, **kw: Any) -> None:
        with self.lock:
            for key, value in kw.items():
                if key == "clients":
                    self.set_clients(int(value))
                elif key == "password":
                    self.password = str(value)
                    self.sessions.clear()
                elif key == "mode":
                    self.mode = str(value)
                elif key == "wifi":
                    self.wifi_layout = str(value)
                    self._build_wifi()
                elif key == "error_methods":
                    self.error_methods = {k: (int(v[0]), str(v[1])) for k, v in dict(value).items()}
                elif key == "expire_sessions":
                    self.sessions.clear()
                elif key == "dark_for":
                    self.dark_until = time.time() + float(value)
                elif key == "client_names":
                    for c, name in zip(self.clients, value, strict=False):
                        c["name"] = c["alias"] = name
                elif key == "ssids":
                    for b in self.bands:
                        for i in b["ifaces"]:
                            if i["name"] in value:
                                i["ssid"] = value[i["name"]]
                elif key == "black_mac":
                    self.black_mac = list(value)
                elif key == "static_binds":
                    self.static_binds = [dict(b) for b in value]
                elif key in {"latency", "fail_rate", "dark_style", "malformed", "reboot_seconds", "reboot_style",
                             "wifi_apply_seconds", "firmware", "session_ttl", "nonce_ttl", "blacklist_mode"}:
                    setattr(self, key, value)
                else:
                    raise ValueError(f"unknown setting {key}")

    def state(self) -> dict[str, Any]:
        with self.lock:
            return {"calls": dict(self.calls), "sessions": len(self.sessions), "clients": len(self.clients),
                    "mode": self.mode, "black_mac": self.black_mac, "static_binds": self.static_binds,
                    "dark": max(0.0, self.dark_until - time.time()), "wifi": self.wifi_get_config({})["res"]}

    def set_clients(self, count: int) -> None:
        old = {c["mac"]: c for c in self.clients}
        out = []
        for i in range(count):
            mac = f"AA:BB:CC:{i // 65536:02X}:{(i // 256) % 256:02X}:{i % 256:02X}"
            c = old.get(mac) or {
                "mac": mac, "ip": f"192.168.{8 + i // 250}.{10 + i % 240}", "name": NAMES[i % len(NAMES)] or "",
                "alias": NAMES[i % len(NAMES)] or "", "online": self.rng.random() < 0.85, "blocked": mac in self.black_mac,
                "iface": ("cable", "2.4G", "5G")[i % 3], "type": 2, "remote": True, "rx": 0, "tx": 0,
                "total_rx": str(self.rng.randint(10**6, 10**10)), "total_tx": str(self.rng.randint(10**5, 10**9)),
                "limit_rx": 0, "limit_tx": 0, "ipv6": [], "online_time": int(time.time()) - self.rng.randint(60, 10**5),
                "last_update_rate": int(time.time()),
            }
            out.append(c)
        self.clients = out

    def _build_wifi(self) -> None:
        def iface(name: str, ssid: str, guest: bool, on: bool, enc: str = "psk2") -> dict[str, Any]:
            return {"name": name, "ssid": ssid, "enabled": on, "encryption": enc, "guest": guest, "hidden": False,
                    "key": "mock-wifi-key", "bssid": "D2:00:00:" + ":".join(secrets.token_hex(1).upper() for _ in range(3))}
        bands = [{"band": "2G", "device": "radio0", "channel": 0, "hwmode": "11g/n", "htmode": "auto",
                  "ifaces": [iface("default_radio0", "MOCK-8f2", False, True), iface("guest2g", "MOCK-8f2-Guest", True, False)]},
                 {"band": "5G", "device": "radio1", "channel": 0, "hwmode": "11a/n/ac", "htmode": "80",
                  "ifaces": [iface("default_radio1", "MOCK-8f2-5G", False, True), iface("guest5g", "MOCK-8f2-5G-Guest", True, False)]}]
        if self.wifi_layout == "tri":
            bands.append({"band": "6G", "device": "radio2", "channel": 0, "hwmode": "11ax", "htmode": "160",
                          "ifaces": [iface("default_radio2", "MOCK-8f2-6G", False, True, "sae")]})
        elif self.wifi_layout == "single":
            bands = bands[:1]
        if self.wifi_layout in ("no_guest", "single"):
            for b in bands:
                b["ifaces"] = [i for i in b["ifaces"] if not i["guest"]]
        self.bands = bands

    # ---------------------------------------------------------------- dispatcher
    def handle(self, payload: dict[str, Any]) -> Any:
        """One JSON-RPC request -> response object (or raw bytes when misbehaving). Raises DropConnection / HttpFailure."""
        with self.lock:
            latency, fail, dark = self.latency, self.fail_rate, self.dark_until > time.time()
            if dark:
                self.calls["(while down)"] += 1
        if dark:
            raise DropConnection(self.dark_style)
        if latency:
            time.sleep(latency)
        if fail and self.rng.random() < fail:
            self.calls["(http 500)"] += 1
            raise HttpFailure(500)
        with self.lock:
            if self.malformed:
                return {"list": [], "html": b"<html><body>Not a router</body></html>", "empty": b"",
                        "truncated": b'{"id": 0, "jsonrpc": "2.0", "result": {"clie'}.get(self.malformed, {"unexpected": True})
            rid = payload.get("id", 0)
            try:
                result = self._dispatch(payload)
            except RpcError as err:
                return {"id": rid, "jsonrpc": "2.0", "error": {"code": err.code, "message": err.message}}
            return {"id": rid, "jsonrpc": "2.0", "result": result}

    def _dispatch(self, payload: dict[str, Any]) -> Any:
        method, params = payload.get("method"), payload.get("params")
        now = time.time()
        if method == "challenge":
            self.calls["challenge"] += 1
            if not isinstance(params, dict) or params.get("username") != self.username:
                raise RpcError(-32000, "Access denied")
            nonce, salt = secrets.token_hex(8), "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
            self.nonces = {n: v for n, v in self.nonces.items() if now - v[0] < self.nonce_ttl}
            self.nonces[nonce] = (now, salt)
            return {"alg": self.alg, "salt": salt, "nonce": nonce, "hash-method": self.hash_method}
        if method == "login":
            self.calls["login"] += 1
            if not isinstance(params, dict):
                raise RpcError(-32602, "Invalid params")
            for nonce, (issued, salt) in list(self.nonces.items()):
                if now - issued >= self.nonce_ttl:
                    continue
                expected = _digest(self.hash_method, f"{self.username}:{_crypt(self.alg, self.password, salt)}:{nonce}".encode())
                if params.get("username") == self.username and params.get("hash") == expected:
                    del self.nonces[nonce]
                    sid = secrets.token_hex(16)
                    self.sessions[sid] = now
                    return {"sid": sid, "username": self.username}
            raise RpcError(-32000, "Access denied")
        if method == "call":
            if not isinstance(params, list) or len(params) != 4:
                raise RpcError(-32602, "Invalid params")
            sid, obj, name, args = params
            if sid not in self.sessions or now - self.sessions[sid] > self.session_ttl:
                self.sessions.pop(sid, None)
                self.calls["(bad session)"] += 1
                raise RpcError(-1, "Access denied")
            self.sessions[sid] = now
            key = f"{obj}.{name}"
            self.calls[key] += 1
            if key in self.error_methods:
                raise RpcError(*self.error_methods[key])
            if key not in self.methods:
                raise RpcError(-32601, "Method not found")
            return self.methods[key](args or {})
        raise RpcError(-32601, "Method not found")

    # ---------------------------------------------------------------- traffic
    def _tick(self) -> None:
        now = time.time()
        for c in self.clients:
            if self.rng.random() < 0.01:  # a device comes or goes now and then
                c["online"] = not c["online"]
            if c["online"]:
                busy = self.rng.random() < 0.3
                c["rx"] = int(self.rng.lognormvariate(10, 2)) if busy else self.rng.randint(0, 800)
                c["tx"] = int(c["rx"] * self.rng.uniform(0.02, 0.4))
                c["total_rx"] = str(int(c["total_rx"]) + c["rx"] * int(now - self._last_tick or 1))
                c["total_tx"] = str(int(c["total_tx"]) + c["tx"] * int(now - self._last_tick or 1))
            else:
                c["rx"] = c["tx"] = 0
            c["blocked"] = c["mac"] in self.black_mac
        self._last_tick = now

    # ---------------------------------------------------------------- methods
    def system_get_info(self, p: dict) -> dict:
        return {"vendor": "GL.iNet", "model": "sft1200", "mac": self.mac, "firmware_version": self.firmware,
                "board_info": {"model": "GL-MOCK1200", "hostname": "GL-MOCK1200", "kernel_version": "5.4.238",
                               "openwrt_version": "OpenWrt 21.02-SNAPSHOT"}}

    def system_get_status(self, p: dict) -> dict:
        self._tick()
        now = time.time()
        wifi = [{"band": b["band"], "mld": False, "ssid": i["ssid"], "encryption": i["encryption"], "hidden": False,
                 "passwd": i["key"], "guest": i["guest"], "name": i["name"], "channel": 0, "up": i["enabled"]}
                for b in self.bands for i in b["ifaces"]]
        online = [c for c in self.clients if c["online"]]
        return {
            "network": [{"online": False, "up": False, "interface": n} for n in ("modem_1_1_2", "tethering", "wan6", "wwan")]
                       + [{"online": True, "up": True, "interface": "wan" if self.mode == "router" else "wwan"}],
            "wifi": wifi, "service": [{"name": "wgserver", "status": 0}, {"name": "ovpnserver", "status": 0}],
            "client": [{"wireless_total": sum(1 for c in online if c["iface"] != "cable"),
                        "cable_total": sum(1 for c in online if c["iface"] == "cable")}],
            "system": {"uptime": now - self.boot, "load_average": [0.5, 0.6, 0.55], "lan_ip": "192.168.8.1",
                       "lan_netmask": "255.255.255.0", "mode": MODE_CODES.get(self.mode, 0), "timestamp": int(now),
                       "memory_total": 121548800, "memory_free": 21835776, "memory_buff_cache": 6815744,
                       "flash_total": 134217728, "flash_free": 85434368, "qos_enabled": False},
        }

    def system_reboot(self, p: dict) -> Any:
        self.dark_until = time.time() + self.reboot_seconds
        self.sessions.clear()
        self.boot = self.dark_until
        if self.reboot_style == "drop":
            raise DropConnection("reset")
        return []

    def clients_get_wan_speed(self, p: dict) -> dict:
        self._tick()
        online = [c for c in self.clients if c["online"]]
        return {"speed_rx": sum(c["rx"] for c in online), "speed_tx": sum(c["tx"] for c in online)}

    def clients_get_list(self, p: dict) -> dict:
        self._tick()
        return {"clients": [dict(c) for c in self.clients]}

    def clients_remove_offline(self, p: dict) -> list:
        mac = str(p.get("mac", "")).upper()
        self.clients = [c for c in self.clients if not (c["mac"].upper() == mac and not c["online"])]
        return []

    def wifi_get_config(self, p: dict) -> dict:
        return {"dfs_support": False, "res": json.loads(json.dumps(self.bands))}

    def wifi_set_config(self, p: dict) -> list:
        for b in self.bands:
            for i in b["ifaces"]:
                if i["name"] == p.get("iface_name"):
                    if "ssid" in p and not (1 <= len(str(p["ssid"]).encode()) <= 32):
                        raise RpcError(-32602, "Invalid params")
                    if "key" in p and not (8 <= len(str(p["key"]).encode()) <= 63):
                        raise RpcError(-32602, "Invalid params")
                    time.sleep(self.wifi_apply_seconds)
                    i.update({k: p[k] for k in ("enabled", "ssid", "key") if k in p})
                    return []
        raise RpcError(-32602, "Invalid params")

    def lan_get_static_bind_list(self, p: dict) -> dict:
        return {"static_bind_list": [dict(b) for b in self.static_binds]}

    def lan_add_static_bind(self, p: dict) -> list:
        if not all(isinstance(p.get(k), str) and p[k] for k in ("mac", "ip", "name")):
            raise RpcError(-32602, "Invalid params")
        self.static_binds.append({"mac": p["mac"], "ip": p["ip"], "name": p["name"]})
        return []

    def lan_remove_static_bind(self, p: dict) -> list:
        raise RpcError(-32602, "Invalid params")  # as on the real firmware

    def bwl_get_config(self, p: dict) -> dict:
        out: dict[str, Any] = {"mode": self.blacklist_mode}
        if self.black_mac:
            out["black_mac"] = list(self.black_mac)
        if self.white_mac:
            out["white_mac"] = list(self.white_mac)
        return out

    def bwl_set_config(self, p: dict) -> list:
        macs = [str(m).upper() for m in p.get("mac", [])]
        if p.get("mode") == "black":
            self.black_mac = macs
        else:
            self.white_mac = macs
        return []

    def bwl_set_single_mac(self, p: dict) -> list:
        mac = str(p.get("mac", "")).upper()
        if p.get("operate") == "add" and mac and mac not in self.black_mac:
            self.black_mac.append(mac)
        return []  # operate=remove / delete: a silent no-op, as on the real firmware


# ------------------------------------------------------------------ HTTP wrapper
def make_handler(router: MockRouter) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: Any) -> None:
            pass

        def _send(self, status: int, body: Any) -> None:
            raw = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _cut(self, style: str) -> None:
            if style == "hang":
                time.sleep(60)
            self.close_connection = True
            self.connection.close()

        def do_GET(self) -> None:
            self._send(200, router.state()) if self.path == "/__state" else self._send(404, {})

        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0)
            try:
                payload = json.loads(body or b"{}")
            except ValueError:
                return self._send(400, {"error": "bad json"})
            if self.path == "/__control":
                try:
                    router.configure(**payload)
                except (ValueError, TypeError) as err:
                    return self._send(400, {"error": str(err)})
                return self._send(200, {"ok": True})
            if self.path != "/rpc":
                return self._send(404, {})
            try:
                self._send(200, router.handle(payload))
            except DropConnection as drop:
                self._cut(str(drop))
            except HttpFailure as fail:
                self._send(fail.status, {"error": "mock failure"})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--password", default="mockpass")
    parser.add_argument("--mac", default="94:83:C4:00:00:01")
    parser.add_argument("--clients", type=int, default=6)
    parser.add_argument("--mode", default="router")
    parser.add_argument("--alg", type=int, default=1, choices=(1, 5, 6))
    parser.add_argument("--hash-method", default="sha256", choices=("md5", "sha256", "sha512"))
    parser.add_argument("--wifi", default="dual", choices=("dual", "tri", "single", "no_guest"))
    args = parser.parse_args()
    router = MockRouter(password=args.password, mac=args.mac, clients=args.clients, mode=args.mode, alg=args.alg,
                        hash_method=args.hash_method, wifi=args.wifi)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(router))
    server.daemon_threads = True
    print(f"mock GL.iNet router on http://{args.host}:{args.port}/rpc  (root / {args.password})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
