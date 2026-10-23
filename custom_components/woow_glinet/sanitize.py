"""Routers answer with whatever their Lua serialiser makes of a table: [] for "nothing", null for a missing field, and
the odd firmware sends a different type altogether. These helpers keep that from taking the integration down."""

from __future__ import annotations

import math
from typing import Any


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def dicts(value: Any) -> list[dict[str, Any]]:
    """The dict items of a list ([] for anything else)."""
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def strings(value: Any) -> list[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def text(value: Any) -> str | None:
    """`value` if it is a non-empty string."""
    return value if isinstance(value, str) and value else None


def as_float(value: Any) -> float | None:
    """A finite float, or None for anything that is not a usable number."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def as_int(value: Any) -> int:
    """An int, 0 for anything that is not a usable number."""
    number = as_float(value)
    return int(number) if number is not None else 0
