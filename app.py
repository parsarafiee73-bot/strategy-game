import os
import re
import random
import string
import logging
from typing import Optional, Tuple, Set

import requests
import psycopg
from psycopg import errors as pg_errors
from flask import Flask, request, jsonify


# ============================================================
# Strategy Game Telegram Bot
# Python + Flask + PostgreSQL + Telegram Bot API
# Render start command:
#     gunicorn app:app
# ============================================================


# ============================================================
# Configuration
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL",
    "https://strategy-game-3.onrender.com",
)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", "10000"))

DEFAULT_LANGUAGE = "fa"

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger("strategy-game")

TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
    if BOT_TOKEN
    else None
)

app = Flask(__name__)


# ============================================================
# Countries
# ============================================================

COUNTRIES = [
    {"code": "IR", "fa": "🇮🇷 ایران", "en": "🇮🇷 Iran"},
    {"code": "US", "fa": "🇺🇸 آمریکا", "en": "🇺🇸 USA"},
    {"code": "RU", "fa": "🇷🇺 روسیه", "en": "🇷🇺 Russia"},
    {"code": "CN", "fa": "🇨🇳 چین", "en": "🇨🇳 China"},
    {"code": "DE", "fa": "🇩🇪 آلمان", "en": "🇩🇪 Germany"},
    {"code": "FR", "fa": "🇫🇷 فرانسه", "en": "🇫🇷 France"},
    {"code": "GB", "fa": "🇬🇧 بریتانیا", "en": "🇬🇧 United Kingdom"},
    {"code": "JP", "fa": "🇯🇵 ژاپن", "en": "🇯🇵 Japan"},
    {"code": "TR", "fa": "🇹🇷 ترکیه", "en": "🇹🇷 Turkey"},
    {"code": "IN", "fa": "🇮🇳 هند", "en": "🇮🇳 India"},
    {"code": "BR", "fa": "🇧🇷 برزیل", "en": "🇧🇷 Brazil"},
    {"code": "EG", "fa": "🇪🇬 مصر", "en": "🇪🇬 Egypt"},
]

COUNTRY_CODES = {country["code"] for country in COUNTRIES}


def country_name(country_code: Optional[str], lang: str) -> str:
    if not country_code:
        return "—"

    for country in COUNTRIES:
        if country["code"] == country_code:
            return country.get(lang, country["en"])

    return country_code


# ============================================================
# Translations
# ============================================================

TEXTS = {
    "fa": {
        "welcome": (
            "🎮 به بازی استراتژی خوش آمدید!\n\n"
            "از دکمه‌های زیر استفاده کنید."
        ),
        "help": (
            "📖 راهنما\n\n"
            "🎮 ساخت بازی: یک بازی جدید بسازید.\n"
            "🔑 ورود به بازی: با کد وارد بازی شوید.\n"
            "📋 بازی من: وضعیت بازی خود را ببینید.\n"
            "🌐 زبان: زبان ربات را تغییر دهید.\n\n"
            "دستورات:\n"
            "/start\n"
            "/help\n"
            "/newgame\n"
            "/join"
        ),
        "btn_new_game": "🎮 ساخت بازی",
        "btn_join_game": "🔑 ورود به بازی",
        "btn_my_game": "📋 بازی من",
        "btn_help": "ℹ️ راهنما",
        "btn_language": "🌐 زبان",
        "choose_language": "لطفاً زبان خود را انتخاب کنید:",
        "language_set": "✅ زبان به فارسی تغییر یافت.",
        "newgame_created": (
            "✅ بازی جدید ساخته شد!\n\n"
            "🔑 کد بازی: {code}\n\n"
            "این کد را با دوستان خود به اشتراک بگذارید."
        ),
        "start_game_btn": "▶️ شروع بازی",
        "join_prompt": "لطفاً کد ۶ کاراکتری بازی را ارسال کنید:",
        "join_invalid_code": (
            "❌ کد نامعتبر است.\n"
            "کد بازی باید دقیقاً ۶ حرف یا عدد باشد."
        ),
        "join_game_not_found": "❌ بازی‌ای با این کد پیدا نشد.",
        "join_already_joined": "⚠️ شما قبلاً در این بازی هستید.",
        "join_game_started_already": (
            "❌ این بازی قبلاً شروع شده و دیگر امکان ورود وجود ندارد."
        ),
        "join_success": "✅ با موفقیت وارد بازی {code} شدید.",
        "start_only_owner": "❌ فقط سازنده بازی می‌تواند آن را شروع کند.",
        "start_not_found": "❌ بازی پیدا نشد.",
        "start_need_players": "❌ برای شروع بازی حداقل ۲ بازیکن لازم است.",
        "game_started": "🚀 بازی شروع شد!",
        "game_started_notify": (
            "🚀 بازی {code} شروع شد.\n\n"
            "لطفاً کشور خود را انتخاب کنید:"
        ),
        "choose_country": "🌍 لطفاً کشور خود را انتخاب کنید:",
        "country_taken": (
            "❌ این کشور قبلاً انتخاب شده است.\n"
            "کشور دیگری انتخاب کنید."
        ),
        "country_selected": "✅ کشور شما: {country}",
        "country_already_selected": (
            "⚠️ شما قبلاً کشور {country} را انتخاب کرده‌اید."
        ),
        "no_game_selected": "⚠️ شما در حال حاضر در هیچ بازی‌ای نیستید.",
        "my_game_status": (
            "📋 بازی: {code}\n"
            "وضعیت: {status}\n"
            "تعداد بازیکنان: {count}\n\n"
            "{players}"
        ),
        "status_waiting": "⏳ در انتظار بازیکنان",
        "status_active": "🟢 فعال",
        "player_no_country": "بدون کشور",
        "owner_label": "سازنده",
        "not_understood": (
            "متوجه نشدم.\n"
            "لطفاً از دکمه‌های زیر استفاده کنید."
        ),
        "error_generic": "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
        "database_error": "⚠️ اتصال به پایگاه داده با مشکل مواجه شد.",
        "country_not_in_game": "❌ شما عضو این بازی نیستید.",
    },
    "en": {
        "welcome": (
            "🎮 Welcome to the Strategy Game!\n\n"
            "Use the buttons below."
        ),
        "help": (
            "📖 Help\n\n"
            "🎮 New Game: create a new game.\n"
            "🔑 Join Game: join a game using its code.\n"
            "📋 My Game: view your game status.\n"
            "🌐 Language: change the bot language.\n\n"
            "Commands:\n"
            "/start\n"
            "/help\n"
            "/newgame\n"
            "/join"
        ),
        "btn_new_game": "🎮 New Game",
        "btn_join_game": "🔑 Join Game",
        "btn_my_game": "📋 My Game",
        "btn_help": "ℹ️ Help",
        "btn_language": "🌐 Language",
        "choose_language": "Please choose your language:",
        "language_set": "✅ Language set to English.",
        "newgame_created": (
            "✅ New game created!\n\n"
            "🔑 Game code: {code}\n\n"
            "Share this code with your friends."
        ),
        "start_game_btn": "▶️ Start Game",
        "join_prompt": "Please send the 6-character game code:",
        "join_invalid_code": (
            "❌ Invalid game code.\n"
            "The game code must contain exactly 6 letters or digits."
        ),
        "join_game_not_found": "❌ No game was found with this code.",
        "join_already_joined": "⚠️ You are already in this game.",
        "join_game_started_already": (
            "❌ This game has already started and can no longer be joined."
        ),
        "join_success": "✅ You successfully joined game {code}.",
        "start_only_owner": "❌ Only the game owner can start the game.",
        "start_not_found": "❌ Game not found.",
        "start_need_players": "❌ At least 2 players are required to start.",
        "game_started": "🚀 The game has started!",
        "game_started_notify": (
            "🚀 Game {code} has started.\n\n"
            "Please choose your country:"
        ),
        "choose_country": "🌍 Please choose your country:",
        "country_taken": (
            "❌ This country has already been selected.\n"
            "Please choose another country."
        ),
        "country_selected": "✅ Your country: {country}",
        "country_already_selected": (
            "⚠️ You already selected {country}."
        ),
        "no_game_selected": "⚠️ You are not currently in a game.",
        "my_game_status": (
            "📋 Game: {code}\n"
            "Status: {status}\n"
            "Players: {count}\n\n"
            "{players}"
        ),
        "status_waiting": "⏳ Waiting for players",
        "status_active": "🟢 Active",
        "player_no_country": "No country",
        "owner_label": "Owner",
        "not_understood": (
            "I didn't understand that.\n"
            "Please use the buttons below."
        ),
        "error_generic": "⚠️ Something went wrong. Please try again.",
        "database_error": "⚠️ The database connection failed.",
        "country_not_in_game": "❌ You are not a member of this game.",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    if lang not in TEXTS:
        lang = DEFAULT_LANGUAGE

    text = TEXTS[lang].get(key)

    if text is None:
        text = TEXTS[DEFAULT_LANGUAGE].get(key, key)

    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            logger.exception("Translation formatting error")

    return text


# ============================================================
# Database
# ============================================================

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    return psycopg.connect(DATABASE_URL)


def init_db():
    if not DATABASE_URL:
        logger.error("DATABASE_URL is not configured")
        return

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        user_id BIGINT PRIMARY KEY,
                        language TEXT NOT NULL DEFAULT 'fa',
                        pending_action TEXT
                    )
                    """
                )

                cur.execute(
                    """
                    ALTER TABLE user_preferences
                    ADD COLUMN IF NOT EXISTS pending_action TEXT
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS games (
                        id SERIAL PRIMARY KEY,
                        code VARCHAR(6) UNIQUE NOT NULL,
                        owner_id BIGINT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'waiting',
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS players (
                        id SERIAL PRIMARY KEY,
                        game_id INTEGER NOT NULL
                            REFERENCES games(id)
                            ON DELETE CASCADE,
                        user_id BIGINT NOT NULL,
                        username TEXT,
                        chat_id BIGINT,
                        country VARCHAR(2),
                        UNIQUE(game_id, user_id)
                    )
                    """
                )

                cur.execute(
                    """
                    ALTER TABLE players
                    ADD COLUMN IF NOT EXISTS chat_id BIGINT
                    """
                )

                cur.execute(
                    """
                    ALTER TABLE players
                    ADD COLUMN IF NOT EXISTS country VARCHAR(2)
                    """
                )

                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_games_code
                    ON games(code)
                    """
                )

                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_players_game_id
                    ON players(game_id)
                    """
                )

                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_players_user_id
                    ON players(user_id)
                    """
                )

                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS
                    idx_players_game_country_unique
                    ON players(game_id, country)
                    WHERE country IS NOT NULL
                    """
                )

        logger.info("Database initialized successfully")

    except Exception:
        logger.exception("Database initialization failed")


def get_user_language(user_id: int) -> str:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT language
                    FROM user_preferences
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )

                row = cur.fetchone()

                if row:
                    return row[0] if row[0] in TEXTS else DEFAULT_LANGUAGE

                cur.execute(
                    """
                    INSERT INTO user_preferences
                        (user_id, language, pending_action)
                    VALUES (%s, %s, NULL)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (user_id, DEFAULT_LANGUAGE),
                )

        return DEFAULT_LANGUAGE

    except Exception:
        logger.exception("Failed to get user language")
        return DEFAULT_LANGUAGE


def set_user_language(user_id: int, lang: str) -> bool:
    if lang not in TEXTS:
        return False

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_preferences
                        (user_id, language, pending_action)
                    VALUES (%s, %s, NULL)
                    ON CONFLICT (user_id)
                    DO UPDATE SET language = EXCLUDED.language
                    """,
                    (user_id, lang),
                )

        return True

    except Exception:
        logger.exception("Failed to set language")
        return False


def set_pending_action(
    user_id: int,
    action: Optional[str],
) -> bool:
    try:
        lang = get_user_language(user_id)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_preferences
                        (user_id, language, pending_action)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET pending_action = EXCLUDED.pending_action
                    """,
                    (user_id, lang, action),
                )

        return True

    except Exception:
        logger.exception("Failed to set pending action")
        return False


def get_pending_action(user_id: int) -> Optional[str]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pending_action
                    FROM user_preferences
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )

                row = cur.fetchone()

                return row[0] if row else None

    except Exception:
        logger.exception("Failed to get pending action")
        return None


def clear_pending_action(user_id: int) -> bool:
    return set_pending_action(user_id, None)


def generate_game_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=6))


def create_game(
    owner_id: int,
    username: str,
    chat_id: int,
) -> Tuple[Optional[int], Optional[str]]:
    for _ in range(20):
        code = generate_game_code()

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:

                    cur.execute(
                        """
                        INSERT INTO games
                            (code, owner_id, status)
                        VALUES
                            (%s, %s, 'waiting')
                        RETURNING id
                        """,
                        (code, owner_id),
                    )

                    row = cur.fetchone()

                    if not row:
                        return None, None

                    game_id = row[0]

                    cur.execute(
                        """
                        INSERT INTO players
                            (game_id, user_id, username, chat_id, country)
                        VALUES
                            (%s, %s, %s, %s, NULL)
                        """,
                        (
                            game_id,
                            owner_id,
                            username,
                            chat_id,
                        ),
                    )

            return game_id, code

        except pg_errors.UniqueViolation:
            continue

        except Exception:
            logger.exception("Failed to create game")
            return None, None

    return None, None


def get_game_by_id(game_id: int):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, code, owner_id, status
                    FROM games
                    WHERE id = %s
                    """,
                    (game_id,),
                )

                return cur.fetchone()

    except Exception:
        logger.exception("Failed to get game by id")
        return None


def get_game_by_code(code: str):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, code, owner_id, status
                    FROM games
                    WHERE code = %s
                    """,
                    (code.upper(),),
                )

                return cur.fetchone()

    except Exception:
        logger.exception("Failed to get game by code")
        return None


def add_player_to_game(
    game_id: int,
    user_id: int,
    username: str,
    chat_id: int,
) -> Tuple[bool, Optional[str]]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT status
                    FROM games
                    WHERE id = %s
                    """,
                    (game_id,),
                )

                game = cur.fetchone()

                if not game:
                    return False, "not_found"

                if game[0] != "waiting":
                    return False, "started"

                cur.execute(
                    """
                    INSERT INTO players
                        (game_id, user_id, username, chat_id, country)
                    VALUES
                        (%s, %s, %s, %s, NULL)
                    """,
                    (
                        game_id,
                        user_id,
                        username,
                        chat_id,
                    ),
                )

        return True, None

    except pg_errors.UniqueViolation:
        return False, "already_joined"

    except Exception:
        logger.exception("Failed to add player")
        return False, "error"


def get_user_game(user_id: int):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        g.id,
                        g.code,
                        g.owner_id,
