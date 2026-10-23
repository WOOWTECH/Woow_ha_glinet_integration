"""Every change to a router goes through here, whether it comes from an entity, a service or the panel.

One place for the validation, the router calls (including the bulk rewrite that unblocking needs) and the
activity log, so the three doors behave the same.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError

from .activity import ActivityLog, Origin
from .api import GlinetApiError, GlinetDisconnected, GlinetInvalidAuth
from .const import BLACKLIST_MODE, DOMAIN, MODE_ROUTER, OPERATE_ADD

if TYPE_CHECKING:
    from .coordinator import GlinetCoordinator

_MAC_SEPARATORS = re.compile(r"[:\-.\s]")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
WIFI_APPLY_TIMEOUT = 40  # s: the router takes ~9 s to apply a Wi-Fi change; a loaded one longer
_HEX12 = re.compile(r"^[0-9A-F]{12}$")


class ActionError(HomeAssistantError):
    """A refused or failed change. `code` lets the panel show it in the user's language."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _byte_length(text: str) -> int | None:
    """Length in UTF-8 bytes, or None for a string that cannot be encoded (a lone surrogate from a hostile client)."""
    try:
        return len(text.encode())
    except UnicodeEncodeError:
        return None


def normalize_mac(value: str) -> str:
    """AA:BB:CC:DD:EE:FF from AA-BB-..., aabb.ccdd.eeff or a bare 12 digits."""
    digits = _MAC_SEPARATORS.sub("", value or "").upper()
    if not _HEX12.match(digits) or int(digits[1], 16) & 1:  # the low bit of the first byte marks multicast
        raise ActionError("invalid_mac", f"MAC 位址格式不正確：{value}")
    return ":".join(digits[i : i + 2] for i in range(0, 12, 2))


class GlinetActions:
    """The writes one router supports."""

    def __init__(self, coordinator: GlinetCoordinator) -> None:
        self.coordinator = coordinator
        # Unblocking reads the whole blocklist, drops one MAC and writes it back: two of those at once
        # (an automation unblocking several devices) would overwrite each other.
        self._blocklist_lock = asyncio.Lock()

    # ---- helpers -----------------------------------------------------------------------
    @property
    def _log(self) -> ActivityLog | None:
        return self.coordinator.hass.data.get(DOMAIN, {}).get("activity")

    async def _record(self, origin: Origin, action: str, msg: str, ok: bool = True, **args: Any) -> None:
        if (log := self._log) is not None:
            entry = self.coordinator.config_entry
            await log.async_record(origin, entry.entry_id, entry.title, action, msg, args, ok)

    async def _call(
        self, obj: str, method: str, params: dict[str, Any] | None = None, timeout: float | None = None
    ) -> Any:
        try:
            if timeout is None:
                return await self.coordinator.client.call(obj, method, params)
            return await self.coordinator.client.call(obj, method, params, timeout)
        except GlinetInvalidAuth as err:
            raise ActionError("auth_failed", f"路由器拒絕了帳號或密碼，請到「設定 › 裝置與服務」重新驗證：{err}") from err
        except GlinetApiError as err:
            raise ActionError("api_error", f"路由器回報錯誤：{err}") from err

    def _iface(self, name: str) -> dict[str, Any] | None:
        for band in self.coordinator.data.wifi_bands:
            for iface in band.get("ifaces", []):
                if iface.get("name") == name:
                    return iface
        return None

    def _client(self, mac: str) -> dict[str, Any] | None:
        for client in self.coordinator.data.clients:
            if str(client.get("mac", "")).upper() == mac:
                return client
        return None

    def _client_name(self, mac: str) -> str:
        client = self._client(mac)
        return (client.get("name") or client.get("alias") or mac) if client else mac

    def _require_router_mode(self, what: str) -> None:
        mode = self.coordinator.data.mode
        if mode != MODE_ROUTER:
            raise ActionError("not_router_mode", f"這台裝置目前是「{mode}」模式,不是 router 模式,{what}沒有意義,先不執行。")

    def lan_network(self) -> ipaddress.IPv4Network | None:
        system = self.coordinator.data.system.get("system", {})
        try:
            return ipaddress.IPv4Network(f"{system['lan_ip']}/{system['lan_netmask']}", strict=False)
        except (KeyError, ValueError):
            return None

    async def _refresh(self) -> None:
        await self.coordinator.async_refresh()

    # ---- WiFi --------------------------------------------------------------------------
    async def set_wifi(self, iface: str, *, enabled: bool | None = None, ssid: str | None = None,
                       key: str | None = None, origin: Origin) -> None:
        """Turn an interface on/off and/or rename it / change its password (one patch to the router)."""
        current = self._iface(iface)
        patch: dict[str, Any] = {}
        try:
            if current is None:
                raise ActionError("no_such_wifi", f"找不到 WiFi 介面：{iface}")
            if enabled is not None:
                patch["enabled"] = bool(enabled)
            if ssid is not None:
                size = _byte_length(ssid)  # 802.11: 32 bytes, a Chinese character takes 3
                if size is None or _CONTROL.search(ssid) or not 1 <= size <= 32:
                    raise ActionError("bad_ssid", "WiFi 名稱（SSID）要 1～32 個位元組（一個中文字佔 3 個），不能有控制字元")
                patch["ssid"] = ssid
            if key is not None:
                size = _byte_length(key)
                if size is None or _CONTROL.search(key) or not 8 <= size <= 63:
                    raise ActionError("bad_key", "WiFi 密碼要 8～63 個位元組，不能有控制字元")
                patch["key"] = key
            if patch:
                await self._call("wifi", "set_config", {"iface_name": iface, **patch}, WIFI_APPLY_TIMEOUT)
        except ActionError as err:
            await self._record(origin, "wifi", "wifi_failed", False, iface=iface, error=str(err), code=err.code)
            raise
        if not patch:
            return
        label = patch.get("ssid") or current.get("ssid") or iface
        if "enabled" in patch:
            await self._record(origin, "wifi", "wifi_on" if patch["enabled"] else "wifi_off", ssid=label, iface=iface)
        if "ssid" in patch:
            await self._record(origin, "wifi", "wifi_ssid", ssid=patch["ssid"], iface=iface)
        if "key" in patch:
            await self._record(origin, "wifi", "wifi_key", ssid=label, iface=iface)
        await self._refresh()

    # ---- blocking (MAC blacklist) --------------------------------------------------------
    async def _valid_mac(self, raw: str, origin: Origin, action: str, msg: str, **args: Any) -> str:
        """The normalised MAC; a malformed one is refused and logged like every other failure."""
        try:
            return normalize_mac(raw)
        except ActionError as err:
            await self._record(origin, action, msg, False, mac=str(raw)[:64], error=str(err), code=err.code, **args)
            raise

    async def set_blocked(self, mac: str, blocked: bool, *, origin: Origin) -> None:
        mac = await self._valid_mac(mac, origin, "block", "block_failed")
        name = self._client_name(mac)
        try:
            self._require_router_mode("裝置封鎖")
            mode = self.coordinator.data.blacklist_mode
            if mode != BLACKLIST_MODE:
                # 在 whitelist 模式下「加進清單」是放行而不是封鎖，語意會反過來，
                # 直接拒絕比默默做錯更安全。
                raise ActionError("not_blacklist_mode", f"路由器目前是「{mode}」模式,不是黑名單模式,封鎖的語意會反過來,先不執行。")
            if blocked:
                await self._call("black_white_list", "set_single_mac", {"mode": mode, "operate": OPERATE_ADD, "mac": mac})
            else:
                # 實測過 set_single_mac 的 operate="remove"/"delete" 都不會真的生效
                # （呼叫成功但清單沒變），解除封鎖要整批重寫清單：讀現有黑名單、
                # 濾掉這個 mac、用 set_config 送回去才會真的拿掉。讀和寫之間要鎖住，
                # 不然同時解除兩個裝置時，後寫的會把前一個的結果蓋掉。
                async with self._blocklist_lock:
                    current = await self._call("black_white_list", "get_config")
                    remaining = [m for m in (current or {}).get("black_mac", []) if m.upper() != mac]
                    await self._call("black_white_list", "set_config", {"mode": mode, "mac": remaining})
        except ActionError as err:
            await self._record(origin, "block", "block_failed", False, mac=mac, error=str(err), code=err.code)
            raise
        await self._record(origin, "block", "blocked" if blocked else "unblocked", name=name, mac=mac)
        await self._refresh()

    # ---- static IP (DHCP reservation) -----------------------------------------------------
    async def add_static_ip(self, mac: str, ip: str, name: str, *, origin: Origin) -> None:
        mac = await self._valid_mac(mac, origin, "static_ip", "static_ip_failed", ip=str(ip)[:64])
        try:
            addr = ipaddress.IPv4Address(ip.strip())
        except ValueError as err:
            error = ActionError("invalid_ip", f"IP 位址格式不正確：{ip}")
            await self._record(origin, "static_ip", "static_ip_failed", False, mac=mac, ip=str(ip)[:64], error=str(error), code=error.code)
            raise error from err
        name = name.strip()
        if not name:
            error = ActionError("bad_name", "名稱不能是空的")
            await self._record(origin, "static_ip", "static_ip_failed", False, mac=mac, ip=str(addr), error=str(error), code=error.code)
            raise error
        try:
            self._require_router_mode("固定 IP（DHCP 租約）")
            if (lan := self.lan_network()) is not None:
                router = self.coordinator.data.system.get("system", {}).get("lan_ip")
                if addr not in lan or addr in (lan.network_address, lan.broadcast_address) or str(addr) == router:
                    raise ActionError("ip_outside_lan", f"{addr} 不能用：要在路由器的 LAN 網段 {lan} 內，且不是網段位址、廣播位址或路由器自己")
            for bind in self.coordinator.data.static_binds:
                if str(bind.get("mac", "")).upper() == mac:
                    raise ActionError("mac_already_bound", f"{mac} 已經有固定 IP {bind.get('ip')}。這台路由器的 API 沒辦法移除舊的綁定，所以不重複新增")
                if bind.get("ip") == str(addr):
                    raise ActionError("ip_already_bound", f"{addr} 已經指派給 {bind.get('mac')}")
            await self._call("lan", "add_static_bind", {"mac": mac, "ip": str(addr), "name": name})
        except ActionError as err:
            await self._record(origin, "static_ip", "static_ip_failed", False, mac=mac, ip=str(addr), error=str(err), code=err.code)
            raise
        await self._record(origin, "static_ip", "static_ip_added", name=name, mac=mac, ip=str(addr))
        await self._refresh()

    # ---- forgetting an offline device ----------------------------------------------------------
    async def forget_client(self, mac: str, *, origin: Origin) -> None:
        """Remove an offline device from the router's own client database."""
        mac = await self._valid_mac(mac, origin, "forget", "forget_failed")
        name = self._client_name(mac)
        try:
            client = self._client(mac)
            if client is not None and client.get("online"):
                raise ActionError("client_online", f"{name} 目前在線上，只能清除離線的裝置")
            await self._call("clients", "remove_offline", {"mac": mac})
        except ActionError as err:
            await self._record(origin, "forget", "forget_failed", False, mac=mac, error=str(err), code=err.code)
            raise
        await self._record(origin, "forget", "client_forgotten", name=name, mac=mac)
        await self._refresh()

    # ---- reboot ------------------------------------------------------------------------------
    async def reboot(self, *, origin: Origin) -> None:
        try:
            try:
                await self._call("system", "reboot")
            except ActionError as err:
                # a router that is going down may cut the connection instead of answering: that is the reboot working
                if not isinstance(err.__cause__, GlinetDisconnected):
                    raise
        except ActionError as err:
            await self._record(origin, "reboot", "reboot_failed", False, error=str(err), code=err.code)
            raise
        await self._record(origin, "reboot", "rebooted")
