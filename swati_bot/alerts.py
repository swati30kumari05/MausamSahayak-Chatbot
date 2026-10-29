"""Decide which farmers receive high-risk alerts and SMS fallbacks (Swati's Bot).

Contains priority rules, UNKNOWN handling (never treated as safe), anti-spam filters,
and SMS fallback dispatch for critical RED alerts.
"""
from dataclasses import dataclass
from typing import List, Optional

from . import formatters, sms

LEVEL = {"GREEN": 0, "UNKNOWN": 1, "YELLOW": 2, "ORANGE": 3, "RED": 4}


@dataclass
class Notification:
    chat_id: int
    text: str
    sms_to: Optional[str] = None
    sms_text: Optional[str] = None


def should_notify(alert: dict) -> bool:
    """Filter whether an alert change is critical enough to trigger an automatic push notification."""
    lvl = alert.get("level", 0)
    prev = alert.get("previous_level", 0)
    kind = alert.get("kind", "flood")

    # Heat alerts: heat YELLOW is common in summer, so only notify for ORANGE/RED and relief drops
    if kind == "heat":
        return (lvl >= LEVEL["ORANGE"] and lvl > prev) or (prev >= LEVEL["ORANGE"] and lvl < prev)

    # Flood alerts: notify on any escalation (including UNKNOWN status when sensors go offline)
    if lvl > prev:
        return lvl >= LEVEL["UNKNOWN"]

    # When elevated flood risk is lowered, notify so farmers know situation improved
    return prev >= LEVEL["ORANGE"] and lvl < prev


def plan_notifications(store, alerts: list, node_names: dict) -> List[Notification]:
    """Given a list of new alerts, builds targeted notification plans for subscribed farmers."""
    out = []
    for a in alerts:
        if not should_notify(a):
            continue

        node_id = a.get("node_id", "")
        name = node_names.get(node_id, node_id)
        subscribers = store.subscribers_for(node_id)

        for u in subscribers:
            lang = u.get("lang", "hi")
            telegram_text = formatters.format_alert(lang, a, name)
            n = Notification(chat_id=u["chat_id"], text=telegram_text)

            # SMS fallback for critical RED alerts when valid phone number is registered
            is_red = (a.get("level_name") == "RED" or a.get("level", 0) >= LEVEL["RED"])
            is_escalation = a.get("level", 0) > a.get("previous_level", 0)
            user_phone = u.get("phone")

            if is_red and is_escalation and sms.valid_phone(user_phone):
                n.sms_to = user_phone
                n.sms_text = formatters.format_sms(lang, a, name)

            out.append(n)

    return out
