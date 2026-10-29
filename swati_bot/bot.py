"""Telegram front-end interface for MausamSahayak (Swati's Bot).

Sets up Telegram commands, persistent quick-reply menus, inline callback queries,
location updates, and periodic background risk-alert polling.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Enable running directly via `python bot.py` from inside swati_bot directory
if __package__ is None or __package__ == "":
    pkg_dir = Path(__file__).resolve().parent
    parent = pkg_dir.parent
    for p in (str(parent), str(pkg_dir)):
        if p not in sys.path:
            sys.path.insert(0, p)
    __package__ = "swati_bot"

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import alerts as alerts_mod
from . import sms
from .api_client import ApiClient, ApiError
from .config import Config
from .i18n import t
from .logic import BotLogic, Reply
from .store import Store

log = logging.getLogger("bot")


def build_farmer_menu(lang: str) -> ReplyKeyboardMarkup:
    """Build persistent, easy-to-tap keyboard menu for farmers."""
    buttons = [
        [
            KeyboardButton(t(lang, "menu_weather")),
            KeyboardButton(t(lang, "menu_forecast")),
        ],
        [
            KeyboardButton(t(lang, "menu_sensors")),
            KeyboardButton(t(lang, "menu_crop")),
        ],
        [
            KeyboardButton(t(lang, "menu_risk")),
            KeyboardButton(t(lang, "menu_location")),
        ],
        [
            KeyboardButton(t(lang, "menu_subscribe")),
            KeyboardButton(t(lang, "menu_language")),
        ],
        [
            KeyboardButton(t(lang, "menu_help")),
        ]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def markup_for(reply: Reply, lang: str):
    """Determine the appropriate Telegram markup for the response."""
    if reply.ask_location:
        return ReplyKeyboardMarkup(
            [[KeyboardButton(t(lang, "share_location_button"), request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    if reply.ask_language:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("हिन्दी 🇮🇳", callback_data="lang:hi"),
                InlineKeyboardButton("English 🇬🇧", callback_data="lang:en"),
            ]
        ])

    if reply.ask_irrigation:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(t(lang, "yes"), callback_data="crop:1"),
                InlineKeyboardButton(t(lang, "no"), callback_data="crop:0"),
            ]
        ])

    if reply.show_menu:
        return build_farmer_menu(lang)

    return None


def build_app(token: str, logic: BotLogic, store: Store, api: ApiClient, sender, poll_s: int = 60) -> Application:
    """Constructs and configures the Telegram Application instance."""

    async def send(update: Update, reply: Reply):
        chat_id = update.effective_chat.id
        user_lang = logic.lang(chat_id)
        markup = markup_for(reply, user_lang)
        await update.effective_chat.send_message(
            reply.text,
            reply_markup=markup,
            parse_mode="Markdown" if ("*" in reply.text or "_" in reply.text) else None,
        )

    def cmd(fn_name: str):
        async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            cid = update.effective_chat.id
            fn = getattr(logic, fn_name)
            res = await asyncio.to_thread(fn, cid)
            await send(update, res)
        return handler

    async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
        arg = " ".join(context.args) if context.args else ""
        cid = update.effective_chat.id
        res = logic.set_phone(cid, arg)
        await send(update, res)

    async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
        loc = update.message.location
        cid = update.effective_chat.id
        res = await asyncio.to_thread(logic.set_location, cid, loc.latitude, loc.longitude)
        await send(update, res)

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        cid = update.effective_chat.id
        res = await asyncio.to_thread(logic.handle_text, cid, text)
        await send(update, res)

    async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        await q.answer()
        kind, _, val = q.data.partition(":")
        cid = update.effective_chat.id

        if kind == "lang":
            res = logic.set_language(cid, val)
            await send(update, res)
        elif kind == "crop":
            irrigated = (val == "1")
            res = await asyncio.to_thread(logic.crop, cid, irrigated)
            await send(update, res)

    async def alert_job(context: ContextTypes.DEFAULT_TYPE):
        """Periodic background task that checks for active risk alerts and pushes notifications."""
        try:
            last_id = store.get_meta("last_alert_id")
            if last_id is None:
                # First run: seed with existing alerts so we do not spam old history
                existing = await asyncio.to_thread(api.alerts, 0)
                max_id = max([a["id"] for a in existing], default=0) if existing else 0
                store.set_meta("last_alert_id", max_id)
                return

            since = int(store.get_meta("last_alert_id", "0"))
            new_alerts = await asyncio.to_thread(api.alerts, since)
        except ApiError as e:
            log.warning("Alert poll failed: %s", e)
            return
        except Exception:
            log.exception("Unexpected error in alert_job")
            return

        if not new_alerts:
            return

        notifications = alerts_mod.plan_notifications(store, new_alerts, store.node_names())
        for n in notifications:
            try:
                await context.bot.send_message(n.chat_id, n.text, parse_mode="Markdown")
            except Exception:
                log.exception("Failed to send alert to Telegram chat %s", n.chat_id)

            # Critical RED alert SMS fallback
            if n.sms_to:
                await asyncio.to_thread(sender.send, n.sms_to, n.sms_text)

        store.set_meta("last_alert_id", max(a.get("id", 0) for a in new_alerts))

    # Initialize Bot Application
    app = Application.builder().token(token).build()

    # Register Command Handlers
    commands = [
        ("start", "start"),
        ("menu", "menu"),
        ("weather", "current"),
        ("now", "current"),
        ("sensors", "sensors"),
        ("forecast", "forecast"),
        ("risk", "risk"),
        ("crop", "crop"),
        ("subscribe", "subscribe"),
        ("unsubscribe", "unsubscribe"),
        ("location", "ask_location"),
        ("language", "start"),
        ("help", "help"),
    ]
    for name, fn in commands:
        app.add_handler(CommandHandler(name, cmd(fn)))

    app.add_handler(CommandHandler("phone", phone))
    app.add_handler(MessageHandler(filters.LOCATION, on_location))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # Register Periodic Alert Job if JobQueue is available
    if app.job_queue:
        app.job_queue.run_repeating(alert_job, interval=poll_s, first=10)
    else:
        log.warning("JobQueue not available. Automatic periodic alerts are disabled.")

    return app


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    print("=" * 65)
    print("  MausamSahayak Telegram Bot (Swati's Module)")
    print(f"  Mode: {'MOCK API (Offline/Viva Mode)' if Config.MOCK_API else f'LIVE API ({Config.API_BASE_URL})'}")
    print(f"  SMS Provider: {Config.SMS_PROVIDER.upper()}")
    print("=" * 65)

    if not Config.TELEGRAM_TOKEN:
        print("\n[!] Error: TELEGRAM_TOKEN is not set.")
        print("    1. Create a bot with @BotFather on Telegram.")
        print("    2. Copy your token.")
        print("    3. Put it in .env: TELEGRAM_TOKEN=your_token_here")
        print("    4. Run again: python -m swati_bot.bot\n")
        sys.exit(1)

    api = ApiClient(
        base_url=Config.API_BASE_URL,
        mock=Config.MOCK_API,
        demo_scenario=Config.DEMO_SCENARIO
    )
    store = Store(Config.BOT_DB)
    logic = BotLogic(api, store)
    sender = sms.make_sender_from_env()

    app = build_app(
        token=Config.TELEGRAM_TOKEN,
        logic=logic,
        store=store,
        api=api,
        sender=sender,
        poll_s=Config.ALERT_POLL_S,
    )

    log.info("Starting Telegram bot polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
