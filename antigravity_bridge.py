"""
antigravity_bridge.py - Lightweight wrapper for Antigravity Agent dispatch & queue management.
"""

from antigravity_bridge_listener import (
    dispatch_to_antigravity,
    load_antigravity_queue,
    save_antigravity_queue,
    get_agent_bridge_key,
    get_antigravity_webhook_url,
    AntigravityBridgeListener
)

__all__ = [
    "dispatch_to_antigravity",
    "load_antigravity_queue",
    "save_antigravity_queue",
    "get_agent_bridge_key",
    "get_antigravity_webhook_url",
    "AntigravityBridgeListener"
]

