"""
sri_history_store.py
====================
Persistent History Storage Engine for SRI AI Agent.

Responsibilities:
  - Atomically append every task, chat prompt, and voice interaction to
    `sri_tasks_history.json` with a full timestamp.
  - Load all saved history on startup and merge with the in-memory
    session_state so the History panel always shows the complete log.
  - Provide helpers for clearing, searching, and rendering history
    entries in both Python (Streamlit sidebar) and JSON (for the
    sri_zero_failure_ui.py front-end panel).

Schema for each entry in sri_tasks_history.json:
  {
    "id":        "hist_<unix_ms>",
    "type":      "task" | "chat" | "voice" | "research",
    "task":      "<short label / prompt heading>",
    "details":   "<full response or detail text>",
    "timestamp": "YYYY-MM-DD HH:MM:SS",
    "iso":       "ISO-8601 datetime string"
  }
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HISTORY_FILE: str = os.path.join(os.path.dirname(__file__), "sri_tasks_history.json")
_HISTORY_LOCK: threading.Lock = threading.Lock()
_MAX_ENTRIES: int = 2000          # cap to keep the JSON file manageable


# ---------------------------------------------------------------------------
# Internal I/O helpers
# ---------------------------------------------------------------------------
def _load_raw() -> list[dict[str, Any]]:
    """Read the JSON file and always return a list (never crashes)."""
    try:
        if not os.path.exists(HISTORY_FILE):
            return []
        with open(HISTORY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Accept both legacy list format and future dict wrapper
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("entries", [])
        return []
    except Exception:
        return []


def _save_raw(entries: list[dict[str, Any]]) -> None:
    """Write entries list atomically via a temp-file rename."""
    tmp = HISTORY_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, HISTORY_FILE)
    except Exception as exc:
        print(f"[sri_history_store] Write error: {exc}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_history() -> list[dict[str, Any]]:
    """Return all saved history entries, oldest first."""
    with _HISTORY_LOCK:
        return _load_raw()


def append_entry(
    task: str,
    details: str,
    entry_type: str = "task",
) -> dict[str, Any]:
    """
    Append a new entry to the persistent JSON file and return the entry dict.

    Parameters
    ----------
    task        : Short label shown as the heading (e.g. the user prompt).
    details     : Full body text (agent reply, error, research summary…).
    entry_type  : One of "task", "chat", "voice", "research".
    """
    now = datetime.now()
    entry: dict[str, Any] = {
        "id":        f"hist_{int(now.timestamp() * 1000)}",
        "type":      entry_type,
        "task":      (task or "").strip()[:300],
        "details":   (details or "").strip()[:2000],
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "iso":       now.isoformat(),
    }
    with _HISTORY_LOCK:
        entries = _load_raw()
        entries.append(entry)
        # Trim to cap
        if len(entries) > _MAX_ENTRIES:
            entries = entries[-_MAX_ENTRIES:]
        _save_raw(entries)
    return entry


def clear_history() -> int:
    """Delete all history entries.  Returns the count that was cleared."""
    with _HISTORY_LOCK:
        old = _load_raw()
        count = len(old)
        _save_raw([])
    return count


def search_history(query: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return up to `limit` entries whose task or details contain `query`."""
    q = query.lower().strip()
    if not q:
        return load_history()[-limit:]
    all_entries = load_history()
    results = [
        e for e in all_entries
        if q in (e.get("task", "") + e.get("details", "")).lower()
    ]
    return results[-limit:]


def get_history_for_ui(limit: int = 200) -> list[dict[str, Any]]:
    """
    Return the latest `limit` entries in reverse-chronological order,
    ready to be injected into the STATE payload for sri_zero_failure_ui.
    """
    entries = load_history()
    return list(reversed(entries[-limit:]))


def build_history_sidebar_html(entries: list[dict[str, Any]]) -> str:
    """
    Build a compact HTML string for the Streamlit sidebar history viewer.
    """
    if not entries:
        return "<div style='color:#71717A;padding:16px;text-align:center;font-size:12px;'>📭 No history recorded yet.</div>"

    type_colors: dict[str, str] = {
        "task":     "#F59E0B",
        "chat":     "#10B981",
        "voice":    "#60A5FA",
        "research": "#A78BFA",
    }
    rows: list[str] = []
    for e in reversed(entries):  # newest first
        color = type_colors.get(e.get("type", "task"), "#F59E0B")
        badge = e.get("type", "task").upper()
        ts    = e.get("timestamp", "")
        task  = (e.get("task") or "").replace("<", "&lt;").replace(">", "&gt;")
        det   = (e.get("details") or "").replace("<", "&lt;").replace(">", "&gt;")
        # Truncate very long detail for sidebar view
        if len(det) > 180:
            det = det[:177] + "…"
        rows.append(
            f'<div style="background:#0E1117;border:1px solid #1E222B;'
            f'border-left:3px solid {color};border-radius:10px;'
            f'padding:10px 12px;margin-bottom:8px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">'
            f'<span style="font-size:9px;color:{color};font-weight:700;'
            f'letter-spacing:0.5px;text-transform:uppercase;">{badge}</span>'
            f'<span style="font-size:9px;color:#71717A;">⏱️ {ts}</span>'
            f'</div>'
            f'<div style="font-weight:600;color:{color};font-size:11.5px;'
            f'margin-bottom:4px;line-height:1.4;">{task}</div>'
            f'<div style="color:#D1D5DB;font-size:11px;line-height:1.45;">{det}</div>'
            f'</div>'
        )
    return "\n".join(rows)
