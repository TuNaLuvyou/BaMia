"""Tiện ích console cho các script ML (Windows mặc định dùng cp1252)."""

from __future__ import annotations

import sys


def ensure_utf8_stdout() -> None:
    """Ép stdout/stderr sang UTF-8 để in được tiếng Việt trên Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
