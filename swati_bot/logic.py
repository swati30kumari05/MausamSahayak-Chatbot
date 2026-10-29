"""Conversation and business logic, independent of Telegram API (Swati's Bot).

Handles conversational user flows, language matching, location validation,
and invokes the centralized api_client and store modules.
"""
import re
from dataclasses import dataclass

from . import formatters, i18n, intents, sms
from .api_client import ApiError
from .i18n import t

LATLON = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$")


@dataclass
class Reply:
    text: str
    ask_location: bool = False
    ask_language: bool = False
    ask_irrigation: bool = False
    show_menu: bool = False


class BotLogic:
    def __init__(self, api, store):
        self.api = api
        self.store = store

    # ---------------------------------------------------------------- Helpers
    def lang(self, chat_id: int) -> str:
        """Get stored language for user, defaulting to Hindi."""
        u = self.store.get_user(chat_id)
        return i18n.norm_lang(u.get("lang")) if u else "hi"

    def _resolve_lang(self, chat_id: int, query_text: str | None = None) -> str:
        """Resolve language from query if typed in Hindi/English, else fall back to user preference."""
        if query_text:
            detected = intents.detect_language(query_text)
            if detected:
                return detected
        return self.lang(chat_id)

    def _station(self, chat_id: int, lang: str | None = None):
        """Returns (user_dict, None) if user has a valid field station, else (None, Reply)."""
        active_lang = lang or self.lang(chat_id)
        u = self.store.get_user(chat_id)

        if not u or u.get("lat") is None:
            return None, Reply(
                t(active_lang, "need_location") + "\n\n" + t(active_lang, "ask_location"),
                ask_location=True
            )

        if not u.get("node_id"):
            name = u.get("node_name") or "-"
            km = u.get("distance_km") or "?"
            return None, Reply(
                t(active_lang, "location_far", name=name, km=km),
                ask_location=True
            )

        return u, None

    def _api_down(self, chat_id: int, lang: str | None = None) -> Reply:
        active_lang = lang or self.lang(chat_id)
        return Reply(t(active_lang, "api_down"))

    # --------------------------------------------------------------- Commands
    def start(self, chat_id: int) -> Reply:
        """Entry point /start: introduces bot and asks for language selection."""
        if self.store.get_user(chat_id) is None:
            self.store.upsert_user(chat_id, lang="hi")

        welcome_text = t("hi", "welcome") + "\n\n" + t("en", "welcome")
        return Reply(welcome_text, ask_language=True, show_menu=True)

    def menu(self, chat_id: int, lang: str | None = None) -> Reply:
        """Display the main farmer menu."""
        active_lang = lang or self.lang(chat_id)
        return Reply(t(active_lang, "menu_title"), show_menu=True)

    def set_language(self, chat_id: int, lang: str) -> Reply:
        """Update language preference for the user."""
        lang = i18n.norm_lang(lang)
        u = self.store.upsert_user(chat_id, lang=lang)
        text = t(lang, "language_set")

        if u.get("lat") is None:
            return Reply(text + "\n\n" + t(lang, "ask_location"), ask_location=True, show_menu=True)

        return Reply(text, show_menu=True)

    def ask_location(self, chat_id: int, lang: str | None = None) -> Reply:
        """Request the farmer to share location via Telegram location button."""
        active_lang = lang or self.lang(chat_id)
        return Reply(t(active_lang, "ask_location"), ask_location=True)

    def set_location(self, chat_id: int, lat: float, lon: float, lang: str | None = None) -> Reply:
        """Process received GPS coordinates and map to the nearest IoT field station."""
        active_lang = lang or self.lang(chat_id)

        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return Reply(t(active_lang, "ask_location"), ask_location=True)

        try:
            res = self.api.nearest(lat, lon)
        except ApiError as e:
            if getattr(e, "status", None) == 404:
                self.store.upsert_user(chat_id, lat=lat, lon=lon, node_id=None)
                return Reply(t(active_lang, "no_stations"), show_menu=True)
            return self._api_down(chat_id, active_lang)

        node = res.get("node") or {}
        km = res.get("distance_km", 0.0)
        name = node.get("name") or node.get("node_id") or "Station"
        within_range = res.get("within_range", False)

        if not within_range:
            self.store.upsert_user(chat_id, lat=lat, lon=lon, node_id=None, node_name=name, distance_km=km, subscribed=0)
            return Reply(t(active_lang, "location_far", name=name, km=km), show_menu=True)

        self.store.upsert_user(chat_id, lat=lat, lon=lon, node_id=node.get("node_id"), node_name=name, distance_km=km)
        return Reply(t(active_lang, "location_saved", name=name, km=km), show_menu=True)

    def current(self, chat_id: int, lang: str | None = None) -> Reply:
        """Fetch current weather and overall risk summary for the connected field station."""
        active_lang = lang or self.lang(chat_id)
        u, bad = self._station(chat_id, active_lang)
        if bad:
            return bad

        try:
            risk = self.api.risk(u["node_id"])
        except ApiError:
            return self._api_down(chat_id, active_lang)

        msg = formatters.format_current(active_lang, risk, u["node_name"], u["distance_km"])
        msg += "\n\n" + t(active_lang, "disclaimer")
        return Reply(msg, show_menu=True)

    def sensors(self, chat_id: int, lang: str | None = None) -> Reply:
        """Fetch real-time field IoT sensor conditions (temperature, humidity, soil moisture, water level)."""
        active_lang = lang or self.lang(chat_id)
        u, bad = self._station(chat_id, active_lang)
        if bad:
            return bad

        try:
            risk = self.api.risk(u["node_id"])
            reading = risk.get("reading") or {}
            age = risk.get("minutes_since_last")
        except ApiError:
            return self._api_down(chat_id, active_lang)

        msg = formatters.format_sensors(active_lang, reading, u["node_name"], u["distance_km"], age_min=age)
        msg += "\n\n" + t(active_lang, "disclaimer")
        return Reply(msg, show_menu=True)

    def forecast(self, chat_id: int, lang: str | None = None) -> Reply:
        """Fetch upcoming 24h-48h weather forecast."""
        active_lang = lang or self.lang(chat_id)
        u, bad = self._station(chat_id, active_lang)
        if bad:
            return bad

        try:
            f_data = self.api.forecast(u["lat"], u["lon"])
        except ApiError:
            return self._api_down(chat_id, active_lang)

        msg = formatters.format_forecast(active_lang, f_data, u["node_name"])
        return Reply(msg, show_menu=True)

    def risk(self, chat_id: int, lang: str | None = None) -> Reply:
        """Fetch heat-risk and flood/waterlogging-risk assessment."""
        active_lang = lang or self.lang(chat_id)
        u, bad = self._station(chat_id, active_lang)
        if bad:
            return bad

        try:
            risk = self.api.risk(u["node_id"])
        except ApiError:
            return self._api_down(chat_id, active_lang)

        msg = formatters.format_risk(active_lang, risk, u["node_name"], u["distance_km"])
        return Reply(msg, show_menu=True)

    def crop(self, chat_id: int, irrigated: bool | None = None, lang: str | None = None) -> Reply:
        """Provide crop recommendations with irrigation context and safety guidance."""
        active_lang = lang or self.lang(chat_id)
        u, bad = self._station(chat_id, active_lang)
        if bad:
            return bad

        if irrigated is None:
            return Reply(t(active_lang, "crop_ask"), ask_irrigation=True)

        try:
            advice = self.api.crop_advice(u["lat"], u["lon"], irrigated)
        except ApiError as e:
            if getattr(e, "status", None) == 404:
                return Reply(t(active_lang, "no_station_crop"), show_menu=True)
            return self._api_down(chat_id, active_lang)

        msg = formatters.format_crop(active_lang, advice)
        return Reply(msg, show_menu=True)

    def subscribe(self, chat_id: int, lang: str | None = None) -> Reply:
        """Subscribe user to automatic high-risk Telegram notifications."""
        active_lang = lang or self.lang(chat_id)
        u, bad = self._station(chat_id, active_lang)
        if bad:
            return bad

        self.store.upsert_user(chat_id, subscribed=1)
        return Reply(t(active_lang, "subscribed", name=u["node_name"]), show_menu=True)

    def unsubscribe(self, chat_id: int, lang: str | None = None) -> Reply:
        """Unsubscribe user from notifications."""
        active_lang = lang or self.lang(chat_id)
        self.store.upsert_user(chat_id, subscribed=0)
        return Reply(t(active_lang, "unsubscribed"), show_menu=True)

    def set_phone(self, chat_id: int, arg: str, lang: str | None = None) -> Reply:
        """Save or remove mobile phone number for critical RED alert SMS fallback."""
        active_lang = lang or self.lang(chat_id)
        arg = (arg or "").strip().replace(" ", "")

        if arg.lower() in ("remove", "delete", "हटाएँ", "हटाएं", "band"):
            self.store.upsert_user(chat_id, phone=None)
            return Reply(t(active_lang, "phone_removed"), show_menu=True)

        if not sms.valid_phone(arg):
            return Reply(t(active_lang, "phone_invalid"), show_menu=True)

        self.store.upsert_user(chat_id, phone=arg)
        return Reply(t(active_lang, "phone_saved"), show_menu=True)

    def help(self, chat_id: int, lang: str | None = None) -> Reply:
        """Show farmer help guide and supported commands."""
        active_lang = lang or self.lang(chat_id)
        return Reply(t(active_lang, "help"), show_menu=True)

    # ------------------------------------------------------------- Free Text
    def handle_text(self, chat_id: int, text: str) -> Reply:
        """Route natural language messages by detecting intent and language."""
        raw_text = (text or "").strip()

        # 1. Coordinate check: e.g. "28.40, 77.31"
        m = LATLON.match(raw_text)
        if m:
            return self.set_location(chat_id, float(m.group(1)), float(m.group(2)))

        # 2. Detect language (Hindi / English) of the specific question
        lang = self._resolve_lang(chat_id, raw_text)

        # 3. Intent Detection
        intent = intents.detect_intent(raw_text)

        handlers = {
            "weather": lambda cid: self.current(cid, lang),
            "sensors": lambda cid: self.sensors(cid, lang),
            "forecast": lambda cid: self.forecast(cid, lang),
            "flood": lambda cid: self.risk(cid, lang),
            "heat": lambda cid: self.risk(cid, lang),
            "crop": lambda cid: self.crop(cid, None, lang),
            "location": lambda cid: self.ask_location(cid, lang),
            "language": lambda cid: Reply(t("hi", "welcome") + "\n\n" + t("en", "welcome"), ask_language=True),
            "menu": lambda cid: self.menu(cid, lang),
            "subscribe": lambda cid: self.subscribe(cid, lang),
            "unsubscribe": lambda cid: self.unsubscribe(cid, lang),
            "help": lambda cid: self.help(cid, lang),
            "greeting": self.start,
        }

        handler = handlers.get(intent)
        if handler:
            return handler(chat_id)

        return Reply(t(lang, "unknown"), show_menu=True)
