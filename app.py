import os
import json
import random
import string
import logging

import requests
import psycopg
from psycopg.rows import dict_row
from flask import Flask, request, jsonify


# ============================================================
# CONFIG
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("strategy-game")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", "10000"))

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}/"

app = Flask(__name__)


# ============================================================
# TRANSLATIONS
# ============================================================

T = {
    "fa": {
        "welcome": (
            "🌍 <b>بازی استراتژی</b>\n\n"
            "به بازی خوش آمدید.\n"
            "برای دیدن دستورات /help را بزنید."
        ),
        "help": (
            "<b>دستورات</b>\n\n"
            "/newgame - ساخت بازی\n"
            "/join - ورود به بازی\n"
            "/startgame - شروع بازی توسط میزبان\n"
            "/menu - منوی اصلی\n"
            "/help - راهنما"
        ),
        "choose_language": "🌐 زبان را انتخاب کنید:",
        "language_saved": "✅ زبان تغییر کرد.",
        "settings": "⚙️ تنظیمات",
        "change_language": "🌐 تغییر زبان",
        "menu": "🎮 <b>منوی بازی</b>",
        "newgame_created": (
            "🎮 بازی ساخته شد!\n"
            "کد بازی: <b>{code}</b>\n\n"
            "بازیکنان دیگر /join را بزنند."
        ),
        "game_exists": (
            "یک بازی فعال وجود دارد.\n"
            "کد: <b>{code}</b>"
        ),
        "no_game": (
            "بازی فعالی وجود ندارد. "
            "ابتدا /newgame را بزنید."
        ),
        "joined": "✅ {name} وارد بازی شد.",
        "already_joined": "شما قبلاً وارد بازی شده‌اید.",
        "game_started_join": (
            "این بازی شروع شده و دیگر امکان ورود وجود ندارد."
        ),
        "host_only": "فقط میزبان می‌تواند بازی را شروع کند.",
        "already_started": "بازی قبلاً شروع شده است.",
        "select_country": "🗺️ کشور خود را انتخاب کنید:",
        "must_join": "ابتدا با /join وارد بازی شوید.",
        "already_country": "شما قبلاً کشور انتخاب کرده‌اید.",
        "country_taken": "این کشور قبلاً انتخاب شده است.",
        "country_selected": "✅ کشور شما: <b>{country}</b>",
        "all_selected": (
            "✅ همه کشور خود را انتخاب کردند. "
            "بازی شروع شد!"
        ),
        "unknown": "دستور نامعتبر است. /help را بزنید.",
        "not_available": "این بخش هنوز پیاده‌سازی نشده است.",
        "status": "📊 وضعیت کشور",
        "world": "🌍 جهان",
        "buildings": "🏗️ ساختمان‌ها",
        "research": "🔬 تحقیقات",
        "leaderboard": "🏆 جدول امتیازات",
        "attack": "⚔️ عملیات",
        "strike": "🚀 حمله",
        "back": "⬅️ بازگشت",
        "language_current": "زبان فعلی: فارسی",
    },

    "en": {
        "welcome": (
            "🌍 <b>Strategy Game</b>\n\n"
            "Welcome to the game.\n"
            "Use /help to see the commands."
        ),
        "help": (
            "<b>Commands</b>\n\n"
            "/newgame - Create a game\n"
            "/join - Join the game\n"
            "/startgame - Host starts the game\n"
            "/menu - Main menu\n"
            "/help - Help"
        ),
        "choose_language": "🌐 Choose your language:",
        "language_saved": "✅ Language changed.",
        "settings": "⚙️ Settings",
        "change_language": "🌐 Change Language",
        "menu": "🎮 <b>Game Menu</b>",
        "newgame_created": (
            "🎮 Game created!\n"
            "Game code: <b>{code}</b>\n\n"
            "Other players should use /join."
        ),
        "game_exists": (
            "An active game already exists.\n"
            "Code: <b>{code}</b>"
        ),
        "no_game": (
            "There is no active game. "
            "Use /newgame first."
        ),
        "joined": "✅ {name} joined the game.",
        "already_joined": "You have already joined the game.",
        "game_started_join": (
            "This game has already started. "
            "New players cannot join."
        ),
        "host_only": "Only the host can start the game.",
        "already_started": "The game has already started.",
        "select_country": "🗺️ Choose your country:",
        "must_join": "Use /join before choosing a country.",
        "already_country": "You have already selected a country.",
        "country_taken": "That country has already been selected.",
        "country_selected": "✅ Your country: <b>{country}</b>",
        "all_selected": (
            "✅ Everyone selected a country. "
            "The game has started!"
        ),
        "unknown": "Unknown command. Use /help.",
        "not_available": "This section is not implemented yet.",
        "status": "📊 Country Status",
        "world": "🌍 World",
        "buildings": "🏗️ Buildings",
        "research": "🔬 Research",
        "leaderboard": "🏆 Leaderboard",
        "attack": "⚔️ Operations",
        "strike": "🚀 Strike",
        "back": "⬅️ Back",
        "language_current": "Current language: English",
    },
}


# ============================================================
# COUNTRIES
# ============================================================

COUNTRIES = {
    "IR": (
        "🇮🇷",
        {"fa": "ایران", "en": "Iran"},
        1000, 500, 300, 800, 1000, 200
    ),

    "TR": (
        "🇹🇷",
        {"fa": "ترکیه", "en": "Turkey"},
        1200, 600, 350, 200, 1100, 220
    ),

    "RU": (
        "🇷🇺",
        {"fa": "روسیه", "en": "Russia"},
        1500, 700, 600, 1500, 2000, 500
    ),

    "CN": (
        "🇨🇳",
        {"fa": "چین", "en": "China"},
        2000, 1000, 800, 400, 3000, 600
    ),

    "IN": (
        "🇮🇳",
        {"fa": "هند", "en": "India"},
        1300, 900, 400, 150, 2500, 400
    ),

    "DE": (
        "🇩🇪",
        {"fa": "آلمان", "en": "Germany"},
        1800, 500, 700, 100, 900, 300
    ),

    "FR": (
        "🇫🇷",
        {"fa": "فرانسه", "en": "France"},
        1600, 550, 500, 120, 800, 280
    ),

    "GB": (
        "🇬🇧",
        {"fa": "بریتانیا", "en": "United Kingdom"},
        1700, 450, 450, 150, 750, 260
    ),

    "JP": (
        "🇯🇵",
        {"fa": "ژاپن", "en": "Japan"},
        1900, 400, 650, 50, 1300, 320
    ),

    "US": (
        "🇺🇸",
        {"fa": "ایالات متحده", "en": "United States"},
        2500, 1200, 900, 700, 3500, 700
    ),

    "BR": (
        "🇧🇷",
        {"fa": "برزیل", "en": "Brazil"},
        1100, 800, 300, 300, 2200, 250
    ),

    "EG": (
        "🇪🇬",
        {"fa": "مصر", "en": "Egypt"},
        900, 400, 200, 150, 1100, 230
    ),
}


# ============================================================
# TEXT HELPERS
# ============================================================

def text(lang, key, **kwargs):
    if lang not in T:
        lang = "fa"

    value = T[lang].get(key, key)

    try:
        return value.format(**kwargs)
    except Exception:
        return value


def country_name(code, lang):
    if code not in COUNTRIES:
        return code

    flag, names, *_ = COUNTRIES[code]

    return f"{flag} {names[lang]}"


def game_code():
    alphabet = string.ascii_uppercase + string.digits

    return "".join(
        random.choice(alphabet)
        for _ in range(5)
    )


# ============================================================
# TELEGRAM
# ============================================================

def tg(method, payload=None):
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing")
        return None

    try:
        response = requests.post(
            TG_API + method,
            json=payload or {},
            timeout=15,
        )

        data = response.json()

        if not data.get("ok"):
            logger.warning(
                "Telegram error: %s",
                data,
            )

        return data

    except Exception:
        logger.exception(
            "Telegram request failed"
        )
        return None


def send(chat_id, message, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if keyboard is not None:
        payload["reply_markup"] = keyboard

    return tg(
        "sendMessage",
        payload,
    )


def answer_callback(callback_id, message=None):
    payload = {
        "callback_query_id": callback_id,
    }

    if message:
        payload["text"] = message

    return tg(
        "answerCallbackQuery",
        payload,
    )


# ============================================================
# KEYBOARDS
# ============================================================

def keyboard(rows):
    return {
        "inline_keyboard": rows
    }


def language_keyboard():
    return keyboard([
        [
            {
                "text": "🇮🇷 فارسی",
                "callback_data": "lang:fa",
            },
            {
                "text": "🇬🇧 English",
                "callback_data": "lang:en",
            },
        ]
    ])


def main_keyboard(lang):
    return keyboard([
        [
            {
                "text": text(lang, "status"),
                "callback_data": "menu:status",
            },
            {
                "text": text(lang, "world"),
                "callback_data": "menu:world",
            },
        ],
        [
            {
                "text": text(lang, "buildings"),
                "callback_data": "menu:buildings",
            },
            {
                "text": text(lang, "research"),
                "callback_data": "menu:research",
            },
        ],
        [
            {
                "text": text(lang, "attack"),
                "callback_data": "menu:attack",
            },
            {
                "text": text(lang, "strike"),
                "callback_data": "menu:strike",
            },
        ],
        [
            {
                "text": text(lang, "leaderboard"),
                "callback_data": "menu:leaderboard",
            },
            {
                "text": text(lang, "settings"),
                "callback_data": "menu:settings",
            },
        ],
    ])


def settings_keyboard(lang):
    return keyboard([
        [
            {
                "text": text(
                    lang,
                    "change_language",
                ),
                "callback_data": "settings:language",
            }
        ],
        [
            {
                "text": text(
                    lang,
                    "back",
                ),
                "callback_data": "menu:back",
            }
        ],
    ])


def back_keyboard(lang):
    return keyboard([
        [
            {
                "text": text(
                    lang,
                    "back",
                ),
                "callback_data": "menu:back",
            }
        ]
    ])


def country_keyboard(taken, lang):
    rows = []
    row = []

    for code, data in COUNTRIES.items():

        if code in taken:
            continue

        flag, names, *_ = data

        row.append({
            "text": f"{flag} {names[lang]}",
            "callback_data": f"country:{code}",
        })

        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    return keyboard(rows)


# ============================================================
# DATABASE
# ============================================================

def init_db():

    if not DATABASE_URL:
        logger.warning(
            "DATABASE_URL is missing; database disabled"
        )
        return

    try:

        with psycopg.connect(
            DATABASE_URL
        ) as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS games (
                        id SERIAL PRIMARY KEY,
                        chat_id BIGINT NOT NULL,
                        code TEXT UNIQUE NOT NULL,
                        host_id BIGINT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'waiting',
                        turn INTEGER NOT NULL DEFAULT 1,
                        created_at TIMESTAMP DEFAULT NOW()
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
                        country TEXT,
                        ready BOOLEAN NOT NULL DEFAULT FALSE,
                        score INTEGER NOT NULL DEFAULT 0,
                        UNIQUE(game_id, user_id)
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS countries (
                        id SERIAL PRIMARY KEY,
                        game_id INTEGER NOT NULL
                            REFERENCES games(id)
                            ON DELETE CASCADE,
                        country TEXT NOT NULL,
                        owner_id BIGINT,
                        money BIGINT NOT NULL DEFAULT 0,
                        food BIGINT NOT NULL DEFAULT 0,
                        steel BIGINT NOT NULL DEFAULT 0,
                        oil BIGINT NOT NULL DEFAULT 0,
                        population BIGINT NOT NULL DEFAULT 0,
                        army BIGINT NOT NULL DEFAULT 0,
                        morale INTEGER NOT NULL DEFAULT 100,
                        score INTEGER NOT NULL DEFAULT 0,
                        buildings JSONB NOT NULL DEFAULT '{}',
                        research JSONB NOT NULL DEFAULT '{}',
                        UNIQUE(game_id, country)
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        user_id BIGINT PRIMARY KEY,
                        language TEXT NOT NULL DEFAULT 'fa',
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    ALTER TABLE user_preferences
                    ADD COLUMN IF NOT EXISTS updated_at
                    TIMESTAMP DEFAULT NOW()
                    """
                )

            conn.commit()

        logger.info(
            "Database tables verified/created successfully."
        )

    except Exception:
        logger.exception(
            "Database initialization failed"
        )


def get_lang(user_id):

    if not DATABASE_URL:
        return "fa"

    try:

        with psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
        ) as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT language
                    FROM user_preferences
                    WHERE user_id=%s
                    """,
                    (user_id,),
                )

                row = cur.fetchone()

                if row and row["language"] in T:
                    return row["language"]

    except Exception:
        logger.exception(
            "get_lang failed"
        )

    return "fa"


def set_lang(user_id, lang):

    if lang not in T:
        return

    if not DATABASE_URL:
        return

    with psycopg.connect(
        DATABASE_URL
    ) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO user_preferences(
                    user_id,
                    language
                )
                VALUES (%s, %s)

                ON CONFLICT(user_id)
                DO UPDATE SET
                    language=EXCLUDED.language,
                    updated_at=NOW()
                """,
                (
                    user_id,
                    lang,
                ),
            )

        conn.commit()


def active_game(cur, chat_id):

    cur.execute(
        """
        SELECT *
        FROM games
        WHERE chat_id=%s
        AND status!='finished'
        ORDER BY id DESC
        LIMIT 1
        """,
        (chat_id,),
    )

    return cur.fetchone()


def player_in_game(
    cur,
    game_id,
    user_id,
):

    cur.execute(
        """
        SELECT *
        FROM players
        WHERE game_id=%s
        AND user_id=%s
        """,
        (
            game_id,
            user_id,
        ),
    )

    return cur.fetchone()


# ============================================================
# COMMANDS
# ============================================================

def cmd_start(message):

    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]

    lang = get_lang(user_id)

    send(
        chat_id,
        text(lang, "welcome"),
        main_keyboard(lang),
    )

    send(
        chat_id,
        text(lang, "choose_language"),
        language_keyboard(),
    )


def cmd_help(message):

    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]

    lang = get_lang(user_id)

    send(
        chat_id,
        text(lang, "help"),
    )


def cmd_menu(message):

    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]

    lang = get_lang(user_id)

    send(
        chat_id,
        text(lang, "menu"),
        main_keyboard(lang),
    )


def cmd_newgame(message):

    chat_id = message["chat"]["id"]
    user = message["from"]

    lang = get_lang(
        user["id"]
    )

    try:

        with psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
        ) as conn:

            with conn.cursor() as cur:

                old = active_game(
                    cur,
                    chat_id,
                )

                if old:
                    send(
                        chat_id,
                        text(
                            lang,
                            "game_exists",
                            code=old["code"],
                        ),
                    )
                    return

                code = game_code()

                cur.execute(
                    """
                    INSERT INTO games(
                        chat_id,
                        code,
                        host_id
                    )
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (
                        chat_id,
                        code,
                        user["id"],
                    ),
                )

                game = cur.fetchone()

                cur.execute(
                    """
                    INSERT INTO players(
                        game_id,
                        user_id,
                        username
                    )
                    VALUES (%s, %s, %s)
                    """,
                    (
                        game["id"],
                        user["id"],
                        user.get(
                            "username"
                        )
                        or user.get(
                            "first_name",
                            "Player",
                        ),
                    ),
                )
                
