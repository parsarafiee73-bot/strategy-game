import os
import random
import string
import logging

import requests
import psycopg
from psycopg import errors as pg_errors
from flask import Flask, request, jsonify


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL",
    "https://strategy-game-3.onrender.com"
)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

PORT = int(os.getenv("PORT", "10000"))

DEFAULT_LANGUAGE = "fa"

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[11:]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("strategy-game")

app = Flask(__name__)

TELEGRAM_API = (
    "https://api.telegram.org/bot" + BOT_TOKEN
    if BOT_TOKEN
    else None
)


# ============================================================
# COUNTRIES
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


def country_name(code, lang):
    if not code:
        return "—"

    for country in COUNTRIES:
        if country["code"] == code:
            return country[lang]

    return code


# ============================================================
# TRANSLATIONS
# ============================================================

TEXTS = {
    "fa": {
        "welcome": (
            "🎮 به بازی استراتژی خوش آمدید!\n\n"
            "از منوی زیر استفاده کنید."
        ),
        "help": (
            "📖 راهنما\n\n"
            "🎮 ساخت بازی: ساخت یک بازی جدید\n"
            "🔑 ورود به بازی: ورود با کد بازی\n"
            "📋 بازی من: مشاهده وضعیت بازی\n"
            "🌐 زبان: تغییر زبان\n\n"
            "/start\n"
            "/help\n"
            "/newgame\n"
            "/join"
        ),
        "new_game": "🎮 ساخت بازی",
        "join_game": "🔑 ورود به بازی",
        "my_game": "📋 بازی من",
        "help_btn": "ℹ️ راهنما",
        "language": "🌐 زبان",
        "choose_language": "لطفاً زبان را انتخاب کنید:",
        "language_fa": "🇮🇷 فارسی",
        "language_en": "🇬🇧 English",
        "language_changed": "✅ زبان به فارسی تغییر کرد.",
        "new_game_created": (
            "✅ بازی ساخته شد!\n\n"
            "🔑 کد بازی: <b>{code}</b>\n\n"
            "این کد را برای دوستانتان بفرستید."
        ),
        "start_game": "▶️ شروع بازی",
        "join_prompt": "🔑 کد ۶ کاراکتری بازی را ارسال کنید:",
        "invalid_code": "❌ کد باید دقیقاً ۶ حرف یا عدد باشد.",
        "game_not_found": "❌ بازی پیدا نشد.",
        "already_joined": "⚠️ شما قبلاً عضو این بازی هستید.",
        "game_started_join": "❌ این بازی قبلاً شروع شده است.",
        "joined": "✅ با موفقیت وارد بازی شدید.",
        "only_owner": "❌ فقط سازنده بازی می‌تواند آن را شروع کند.",
        "need_players": "❌ برای شروع حداقل ۲ بازیکن لازم است.",
        "started": "🚀 بازی شروع شد!",
        "choose_country": "🌍 کشور خود را انتخاب کنید:",
        "country_taken": "❌ این کشور قبلاً انتخاب شده است.",
        "country_selected": "✅ کشور شما: {country}",
        "country_already": "⚠️ شما قبلاً کشور {country} را انتخاب کرده‌اید.",
        "no_game": "⚠️ شما در هیچ بازی‌ای نیستید.",
        "db_error": "⚠️ خطا در اتصال به پایگاه داده.",
        "unknown": "متوجه نشدم. از دکمه‌های زیر استفاده کنید.",
    },

    "en": {
        "welcome": (
            "🎮 Welcome to the Strategy Game!\n\n"
            "Use the menu below."
        ),
        "help": (
            "📖 Help\n\n"
            "🎮 New Game: create a new game\n"
            "🔑 Join Game: join using a game code\n"
            "📋 My Game: view your game\n"
            "🌐 Language: change language\n\n"
            "/start\n"
            "/help\n"
            "/newgame\n"
            "/join"
        ),
        "new_game": "🎮 New Game",
        "join_game": "🔑 Join Game",
        "my_game": "📋 My Game",
        "help_btn": "ℹ️ Help",
        "language": "🌐 Language",
        "choose_language": "Please choose your language:",
        "language_fa": "🇮🇷 فارسی",
        "language_en": "🇬🇧 English",
        "language_changed": "✅ Language changed to English.",
        "new_game_created": (
            "✅ Game created!\n\n"
            "🔑 Game code: <b>{code}</b>\n\n"
            "Send this code to your friends."
        ),
        "start_game": "▶️ Start Game",
        "join_prompt": "🔑 Send the 6-character game code:",
        "invalid_code": "❌ The code must contain exactly 6 letters or digits.",
        "game_not_found": "❌ Game not found.",
        "already_joined": "⚠️ You are already in this game.",
        "game_started_join": "❌ This game has already started.",
        "joined": "✅ You joined the game successfully.",
        "only_owner": "❌ Only the game owner can start the game.",
        "need_players": "❌ At least 2 players are required.",
        "started": "🚀 Game started!",
        "choose_country": "🌍 Choose your country:",
        "country_taken": "❌ This country has already been selected.",
        "country_selected": "✅ Your country: {country}",
        "country_already": "⚠️ You already selected {country}.",
        "no_game": "⚠️ You are not currently in a game.",
        "db_error": "⚠️ Database connection error.",
        "unknown": "I didn't understand. Please use the buttons.",
    }
}


def t(lang, key, **kwargs):
    if lang not in TEXTS:
        lang = DEFAULT_LANGUAGE

    text = TEXTS[lang].get(key, key)

    if kwargs:
        text = text.format(**kwargs)

    return text


# ============================================================
# DATABASE
# ============================================================

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing")

    return psycopg.connect(DATABASE_URL)


def init_db():
    if not DATABASE_URL:
        logger.error("DATABASE_URL is missing")
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
                    CREATE UNIQUE INDEX IF NOT EXISTS
                    players_game_country_unique
                    ON players(game_id, country)
                    WHERE country IS NOT NULL
                    """
                )

        logger.info("Database initialized")

    except Exception:
        logger.exception("Database initialization failed")


# ============================================================
# USER SETTINGS
# ============================================================

def get_language(user_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    "SELECT language FROM user_preferences WHERE user_id = %s",
                    (user_id,)
                )

                row = cur.fetchone()

                if row and row[0] in TEXTS:
                    return row[0]

                cur.execute(
                    """
                    INSERT INTO user_preferences
                    (user_id, language, pending_action)
                    VALUES (%s, %s, NULL)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (user_id, DEFAULT_LANGUAGE)
                )

        return DEFAULT_LANGUAGE

    except Exception:
        logger.exception("Could not get language")
        return DEFAULT_LANGUAGE


def set_language(user_id, lang):
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
                    (user_id, lang)
                )

        return True

    except Exception:
        logger.exception("Could not set language")
        return False


def set_pending(user_id, action):
    try:
        lang = get_language(user_id)

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
                    (user_id, lang, action)
                )

        return True

    except Exception:
        logger.exception("Could not set pending action")
        return False


def get_pending(user_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT pending_action
                    FROM user_preferences
                    WHERE user_id = %s
                    """,
                    (user_id,)
                )

                row = cur.fetchone()

                if row:
                    return row[0]

    except Exception:
        logger.exception("Could not get pending action")

    return None


def clear_pending(user_id):
    return set_pending(user_id, None)


# ============================================================
# GAME DATABASE FUNCTIONS
# ============================================================

def generate_code():
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=6))


def create_game(user_id, username, chat_id):
    for _ in range(20):

        code = generate_code()

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:

                    cur.execute(
                        """
                        INSERT INTO games
                        (code, owner_id, status)
                        VALUES (%s, %s, 'waiting')
                        RETURNING id
                        """,
                        (code, user_id)
                    )

                    game_id = cur.fetchone()[0]

                    cur.execute(
                        """
                        INSERT INTO players
                        (game_id, user_id, username, chat_id, country)
                        VALUES (%s, %s, %s, %s, NULL)
                        """,
                        (
                            game_id,
                            user_id,
                            username,
                            chat_id
                        )
                    )

            return game_id, code

        except pg_errors.UniqueViolation:
            continue

        except Exception:
            logger.exception("Could not create game")
            return None, None

    return None, None


def get_game_by_code(code):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT id, code, owner_id, status
                    FROM games
                    WHERE code = %s
                    """,
                    (code.upper(),)
                )

                return cur.fetchone()

    except Exception:
        logger.exception("Could not get game")
        return None


def get_user_game(user_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        g.id,
                        g.code,
                        g.owner_id,
                        g.status
                    FROM games g
                    JOIN players p
                        ON p.game_id = g.id
                    WHERE p.user_id = %s
                    ORDER BY g.id DESC
                    LIMIT 1
                    """,
                    (user_id,)
                )

                return cur.fetchone()

    except Exception:
        logger.exception("Could not get user game")
        return None


def get_players(game_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT user_id, username, chat_id, country
                    FROM players
                    WHERE game_id = %s
                    ORDER BY id
                    """,
                    (game_id,)
                )

                return cur.fetchall()

    except Exception:
        logger.exception("Could not get players")
        return []


def join_game(game_id, user_id, username, chat_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT status
                    FROM games
                    WHERE id = %s
                    """,
                    (game_id,)
                )

                game = cur.fetchone()

                if not game:
                    return "not_found"

                if game[0] != "waiting":
                    return "started"

                cur.execute(
                    """
                    SELECT id
                    FROM players
                    WHERE game_id = %s
                    AND user_id = %s
                    """,
                    (game_id, user_id)
                )

                if cur.fetchone():
                    return "already"

                cur.execute(
                    """
                    INSERT INTO players
                    (game_id, user_id, username, chat_id, country)
                    VALUES (%s, %s, %s, %s, NULL)
                    """,
                    (
                        game_id,
                        user_id,
                        username,
                        chat_id
                    )
                )

        return "ok"

    except Exception:
        logger.exception("Could not join game")
        return "error"


def start_game(game_id, user_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT owner_id, status
                    FROM games
                    WHERE id = %s
                    """,
                    (game_id,)
                )

                game = cur.fetchone()

                if not game:
                    return "not_found"

                owner_id, status = game

                if owner_id != user_id:
                    return "owner"

                if status != "waiting":
                    return "started"

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM players
                    WHERE game_id = %s
                    """,
                    (game_id,)
                )

                count = cur.fetchone()[0]

                if count < 2:
                    return "players"

                cur.execute(
                    """
                    UPDATE games
                    SET status = 'active'
                    WHERE id = %s
                    """,
                    (game_id,)
                )

        return "ok"

    except Exception:
        logger.exception("Could not start game")
        return "error"


def get_taken_countries(game_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT country
                    FROM players
                    WHERE game_id = %s
                    AND country IS NOT NULL
                    """,
                    (game_id,)
                )

                return {
                    row[0]
                    for row in cur.fetchall()
                    if row[0]
                }

    except Exception:
        logger.exception("Could not get taken countries")
        return set()


def choose_country(game_id, user_id, code):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT country
                    FROM players
                    WHERE game_id = %s
                    AND user_id = %s
                    """,
                    (game_id, user_id)
                )

                player = cur.fetchone()

                if not player:
                    return "not_member", None

                if player[0]:
                    return "already", player[0]

                cur.execute(
                    """
                    SELECT user_id
                    FROM players
                    WHERE game_id = %s
                    AND country = %s
                    """,
                    (game_id, code)
                )

                if cur.fetchone():
                    return "taken", None

                cur.execute(
                    """
                    UPDATE players
                    SET country = %s
                    WHERE game_id = %s
                    AND user_id = %s
                    """,
                    (
                        code,
                        game_id,
                        user_id
                    )
                )

        return "ok", code

    except Exception:
        logger.exception("Could not choose country")
        return "error", None


# ============================================================
# TELEGRAM API
# ============================
