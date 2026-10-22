"""Constants for the WOOW GL.iNet integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "woow_glinet"

CONF_SCHEME = "scheme"
CONF_VERIFY_SSL = "verify_ssl"

DEFAULT_HOST = "192.168.8.1"
DEFAULT_USERNAME = "root"
DEFAULT_SCHEME = "https"
DEFAULT_VERIFY_SSL = False

UPDATE_INTERVAL = timedelta(seconds=30)

BLACKLIST_MODE = "black"
WHITELIST_MODE = "white"

# netmode.get_mode 的回應值。router 模式才有自己的 WAN/DHCP,clients.get_list
# 才會只看到「接這台裝置的」裝置;router 以外的模式(ap/repeater/relay/wds/mesh/
# passthrough)下,這台裝置是橋接在共用網段上,clients.get_list 會看到整個網段
# 所有裝置(不是只有自己的),WAN 流量永遠是 0,固定 IP(DHCP)也不會真的生效。
MODE_ROUTER = "router"

OPERATE_ADD = "add"

MANUFACTURER = "GL.iNet"

SERVICE_ADD_STATIC_IP = "add_static_ip"
SERVICE_REMOVE_STATIC_IP = "remove_static_ip"

ATTR_MAC = "mac"
ATTR_IP = "ip"
ATTR_NAME = "name"
