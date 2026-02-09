"""Pagination helpers with hard caps."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Response


DEFAULT_PAGE_SIZE = 50
DEFAULT_MAX_PAGE_SIZE = 200


def get_max_page_size() -> int:
    raw = os.getenv("API_MAX_PAGE_SIZE", str(DEFAULT_MAX_PAGE_SIZE))
    try:
        val = int(raw)
    except Exception:
        val = DEFAULT_MAX_PAGE_SIZE
    if val < 1:
        return DEFAULT_MAX_PAGE_SIZE
    return val


def clamp_page_size(page_size: int) -> int:
    max_size = get_max_page_size()
    if page_size < 1:
        return 1
    return min(page_size, max_size)


def clamp_limit(limit: int) -> int:
    max_size = get_max_page_size()
    if limit < 1:
        return 1
    return min(limit, max_size)


def set_pagination_headers(
    response: Optional[Response],
    *,
    total: Optional[int],
    page: int,
    page_size: int,
) -> None:
    if not response:
        return
    if total is not None:
        response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
