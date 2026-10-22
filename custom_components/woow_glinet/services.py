"""Services for the WOOW GL.iNet integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .api import GlinetApiError
from .const import ATTR_IP, ATTR_MAC, ATTR_NAME, DOMAIN, SERVICE_ADD_STATIC_IP, SERVICE_REMOVE_STATIC_IP

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE_ID = "device_id"

ADD_STATIC_IP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_MAC): cv.string,
        vol.Required(ATTR_IP): cv.string,
        vol.Required(ATTR_NAME): cv.string,
    }
)

REMOVE_STATIC_IP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_MAC): cv.string,
    }
)


def async_register_services(hass: HomeAssistant) -> None:
    """Register the woow_glinet services once, even with multiple routers."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_STATIC_IP):
        return

    # imported here to avoid a circular import with __init__.py at module load time
    from . import async_get_coordinator_for_device

    async def _resolve(call: ServiceCall):
        coordinator = async_get_coordinator_for_device(hass, call.data[ATTR_DEVICE_ID])
        if coordinator is None:
            raise HomeAssistantError(f"找不到對應的 GL.iNet 路由器裝置：{call.data[ATTR_DEVICE_ID]}")
        return coordinator

    async def _async_add_static_ip(call: ServiceCall) -> None:
        coordinator = await _resolve(call)
        try:
            await coordinator.client.call(
                "lan",
                "add_static_bind",
                {
                    "mac": call.data[ATTR_MAC],
                    "ip": call.data[ATTR_IP],
                    "name": call.data[ATTR_NAME],
                },
            )
        except GlinetApiError as err:
            raise HomeAssistantError(f"設定固定 IP 失敗：{err}") from err
        await coordinator.async_request_refresh()

    async def _async_remove_static_ip(call: ServiceCall) -> None:
        # 2026-10-22 實測過：lan.remove_static_bind 不管傳什麼參數組合都回
        # "Invalid params"(還會額外帶一個沒查到合法值的 "invalid mode" 錯誤)，
        # 這個方法在這台裝置的韌體上無法透過 API 正常運作。lan 物件也沒有
        # get_config/set_config 可以整批重寫 static_bind_list 繞過去(跟
        # black_white_list 的解除封鎖不是同一種修法)。先誠實回報限制,
        # 真要移除固定 IP 綁定,目前只能 SSH 進裝置手動 uci delete。
        await _resolve(call)  # 仍檢查 device_id 有效,维持跟其他服務一致的錯誤行為
        raise HomeAssistantError(
            "這台路由器的韌體上，移除固定 IP 綁定的 API（lan.remove_static_bind）實測"
            "無法正常運作（永遠回 Invalid params）。目前沒有找到替代的 API 寫法，"
            "要移除的話請用 SSH 手動處理：uci delete dhcp.@host[N]（N 用 "
            "'uci show dhcp' 對照 mac 找出來）→ uci commit dhcp → "
            "/etc/init.d/dnsmasq restart。"
        )

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_STATIC_IP, _async_add_static_ip, schema=ADD_STATIC_IP_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_STATIC_IP,
        _async_remove_static_ip,
        schema=REMOVE_STATIC_IP_SCHEMA,
    )
