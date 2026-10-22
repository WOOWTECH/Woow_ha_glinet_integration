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

OPERATE_ADD = "add"

MANUFACTURER = "GL.iNet"

SERVICE_ADD_STATIC_IP = "add_static_ip"
SERVICE_REMOVE_STATIC_IP = "remove_static_ip"

ATTR_MAC = "mac"
ATTR_IP = "ip"
ATTR_NAME = "name"
