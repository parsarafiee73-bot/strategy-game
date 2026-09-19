import os
import logging
import random
import string

import requests
import psycopg
from psycopg.rows import dict_row
from flask import Flask, request, jsonify


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL",
    "https://strategy-game-3.onrender.com",
).rstrip("/")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# TRANSLATIONS
# ============================================================

TEXT = {
    "fa": {
        "welcome": "🎮 به بازی استراتژیک خوش آمدی!",
        "choose_language": "زبان بازی را انتخاب کن:",
        "language_saved": "زبان با موفقیت تغییر کرد.",
        "main_menu": "منوی اصلی:",
        "new_game": "🎮 بازی جدید",
        "join_game": "🔑 ورود به بازی",
        "my_game": "👤 بازی من",
        "settings": "⚙️ تنظیمات",
        "help": "❓ راهنما",
        "back": "🔙 بازگشت",
        "language": "🌐 زبان",
        "persian": "🇮🇷 فارسی",
        "english": "🇬🇧 English",
        "enter_code": "کد بازی را ارسال کن.",
        "invalid_code": "کد بازی معتبر نیست.",
        "game_created": "بازی ساخته شد!",
        "game_code": "کد بازی:",
        "share_code": "این کد را برای بازیکنان دیگر بفرست.",
        "joined": "با موفقیت وارد بازی شدی.",
        "already_in_game": "تو در حال حاضر داخل یک بازی هستی.",
        "game_not_found": "این بازی پیدا نشد.",
        "game_full": "ظرفیت بازی تکمیل شده است.",
        "game_started": "بازی شروع شده است.",
        "not_enough_players": "برای شروع حداقل ۲ بازیکن لازم است.",
        "select_country": "کشور خودت را انتخاب کن:",
        "country_taken": "این کشور قبلاً انتخاب شده است.",
        "country_selected": "کشور تو انتخاب شد:",
        "all_ready": "همه بازیکنان کشور خود را انتخاب کرده‌اند.",
        "waiting": "منتظر انتخاب کشور بازیکنان دیگر هستیم.",
        "not_in_game": "تو در هیچ بازی فعالی نیستی.",
        "already_started": "این بازی قبلاً شروع شده است.",
        "help_text": (
            "🎮 راهنمای بازی\n\n"
            "1. بازی جدید بساز.\n"
            "2. کد بازی را برای دوستانت بفرست.\n"
            "3. آنها با گزینه ورود به بازی وارد شوند.\n"
            "4. وقتی همه آماده بودند، بازی را شروع کن.\n"
            "5. هر بازیکن یک کشور انتخاب می‌کند.\n"
        ),
        "game_info": "اطلاعات بازی",
        "players": "بازیکنان",
        "status": "وضعیت",
        "waiting_status": "در انتظار شروع",
        "active_status": "فعال",
        "no_game": "بازی فعالی نداری.",
        "game_menu": "منوی بازی:",
        "start_game": "▶️ شروع بازی",
        "country": "کشور",
        "unknown": "نامشخص",
        "error": "یک خطای داخلی رخ داد. دوباره تلاش کن.",
    },

    "en": {
        "welcome": "🎮 Welcome to the Strategy Game!",
        "choose_language": "Choose your game language:",
        "language_saved": "Language changed successfully.",
        "main_menu": "Main Menu:",
        "new_game": "🎮 New Game",
        "join_game": "🔑 Join Game",
        "my_game": "👤 My Game",
        "settings": "⚙️ Settings",
        "help": "❓ Help",
        "back": "🔙 Back",
        "language": "🌐 Language",
        "persian": "🇮🇷 فارسی",
        "english": "🇬🇧 English",
        "enter_code": "Send the game code.",
        "invalid_code": "Invalid game code.",
        "game_created": "Game created!",
        "game_code": "Game code:",
        "share_code": "Send this code to the other players.",
        "joined": "You joined the game successfully.",
        "already_in_game": "You are already in a game.",
        "game_not_found": "Game not found.",
        "game_full": "The game is full.",
        "game_started": "The game has already started.",
        "not_enough_players": "At least 2 players are required.",
        "select_country": "Choose your country:",
        "country_taken": "This country has already been selected.",
        "country_selected": "Your country:",
        "all_ready": "All players have selected their countries.",
        "waiting": "Waiting for the other players.",
        "not_in_game": "You are not in an active game.",
        "already_started": "This game has already started.",
        "help_text": (
            "🎮 Game Guide\n\n"
            "1. Create a new game.\n"
            "2. Send the game code to your friends.\n"
            "3. They can join using Join Game.\n"
            "4. Start the game when everyone is ready.\n"
            "5. Each player chooses a country.\n"
        ),
        "game_info": "Game Information",
        "players": "Players",
        "status": "Status",
        "waiting_status": "Waiting to start",
        "active_status": "Active",
        "no_game": "You don't have an active game.",
        "game_menu": "Game Menu:",
        "start_game": "▶️ Start Game",
        "country": "Country",
        "unknown": "Unknown",
        "error": "An internal error occurred. Try again.",
    },
}


# ============================================================
# COUNTRIES
# ============================================================

COUNTRIES = {
    "iran": {
        "fa": "ایران",
        "en": "Iran",
    },
    "turkey": {
        "fa": "ترکیه",
        "en": "Turkey",
    },
    "russia": {
        "fa": "روسیه",
        "en": "Russia",
    },
    "china": {
        "fa": "چین",
        "en": "China",
    },
    "india": {
        "fa": "هند",
        "en": "India",
    },
    "germany": {
        "fa": "آلمان",
        "en": "Germany",
    },
    "france": {
        "fa": "فرانسه",
        "en": "France",
    },
    "italy": {
        "fa": "ایتالیا",
        "en": "Italy",
    },
    "spain": {
        "fa": "اسپانیا",
        "en": "Spain",
    },
    "uk": {
        "fa": "بریتانیا",
        "en": "United Kingdom",
    },
    "usa": {
        "fa": "آمریکا",
        "en": "United States",
    },
    "japan": {
        "fa": "ژاپن",
        "en": "Japan",
    },
}


# ============================================================
# DATABASE
# ============================================================

def get_db():
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    )


def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id BIGINT PRIMARY KEY,
                    language VARCHAR(10) NOT NULL DEFAULT 'fa'
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS games (
                    id SERIAL PRIMARY KEY,
                    code VARCHAR(20) UNIQUE NOT NULL,
                    owner_id BIGINT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'waiting',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                    country VARCHAR(50),
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(game_id, user_id)
                )
                """
            )

        conn.commit()


# ============================================================
# USER / LANGUAGE
# ============================================================

def get_language(user_id):
    with get_db() as conn:
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
                return row["language"]

            cur.execute(
                """
                INSERT INTO user_preferences
                (user_id, language)
                VALUES (%s, 'fa')
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,),
            )

        conn.commit()

    return "fa"


def set_language(user_id, language):
    if language not in ("fa", "en"):
        language = "fa"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_preferences
                (user_id, language)
                VALUES (%s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET language = EXCLUDED.language
                """,
                (user_id, language),
            )

        conn.commit()


def tr(user_id, key):
    language = get_language(user_id)
    return TEXT[language].get(key, key)


# ============================================================
# TELEGRAM API
# ============================================================

def telegram_api(method, data=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    try:
        response = requests.post(
            url,
            json=data or {},
            timeout=15,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as exc:
        logger.exception(
            "Telegram API error: %s",
            exc,
        )
        return {
            "ok": False,
            "error": str(exc),
        }


def send_message(
    chat_id,
    text,
    reply_markup=None,
):
    data = {
        "chat_id": chat_id,
        "text": text,
    }

    if reply_markup:
        data["reply_markup"] = reply_markup

    return telegram_api(
        "sendMessage",
        data,
    )


def answer_callback(callback_id):
    return telegram_api(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id,
        },
    )


# ============================================================
# KEYBOARDS
# ============================================================

def language_keyboard():
    return {
        "inline_keyboard": [
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
        ]
    }


def main_keyboard(user_id):
    return {
        "keyboard": [
            [
                {
                    "text": tr(user_id, "new_game"),
                },
                {
                    "text": tr(user_id, "join_game"),
                },
            ],
            [
                {
                    "text": tr(user_id, "my_game"),
                },
                {
                    "text": tr(user_id, "settings"),
                },
            ],
            [
                {
                    "text": tr(user_id, "help"),
                },
            ],
        ],
        "resize_keyboard": True,
    }


def settings_keyboard(user_id):
    return {
        "keyboard": [
            [
                {
                    "text": tr(user_id, "language"),
                },
            ],
            [
                {
                    "text": tr(user_id, "back"),
                },
            ],
        ],
        "resize_keyboard": True,
    }


def game_keyboard(user_id):
    return {
        "keyboard": [
            [
                {
                    "text": tr(user_id, "start_game"),
                },
            ],
            [
                {
                    "text": tr(user_id, "back"),
                },
            ],
        ],
        "resize_keyboard": True,
    }


def country_keyboard():
    rows = []
    row = []

    for key, data in COUNTRIES.items():
        row.append(
            {
                "text": f"{data['fa']} / {data['en']}",
                "callback_data": f"country:{key}",
            }
        )

        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    return {
        "inline_keyboard": rows,
    }


# ============================================================
# GAME HELPERS
# ============================================================

def generate_game_code():
    while True:
        code = "".join(
            random.choices(
                string.ascii_uppercase + string.digits,
                k=6,
            )
        )

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id
                    FROM games
                    WHERE code = %s
                    """,
                    (code,),
                )

                exists = cur.fetchone()

        if not exists:
            return code


def get_player_game(user_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    g.id,
                    g.code,
                    g.owner_id,
                    g.status,
                    p.country
                FROM games g
                JOIN players p
                    ON p.game_id = g.id
                WHERE p.user_id = %s
                  AND g.status != 'finished'
                ORDER BY g.id DESC
                LIMIT 1
                """,
                (user_id,),
            )

            return cur.fetchone()


def get_game_by_code(code):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM games
                WHERE code = %s
                """,
                (code.upper(),),
            )

            return cur.fetchone()


def get_game_players(game_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM players
                WHERE game_id = %s
                ORDER BY id
                """,
                (game_id,),
            )

            return cur.fetchall()


# ============================================================
# /start
# ============================================================

def command_start(message):
    user = message["from"]
    user_id = user["id"]
    chat_id = message["chat"]["id"]

    get_language(user_id)

    send_message(
        chat_id,
        tr(user_id, "welcome")
        + "\n\n"
        + tr(user_id, "choose_language"),
        language_keyboard(),
    )


# ============================================================
# /help
# ============================================================

def command_help(message):
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]

    send_message(
        chat_id,
        tr(user_id, "help_text"),
        main_keyboard(user_id),
    )


# ============================================================
# NEW GAME
# ============================================================

def command_new_game(message):
    user = message["from"]
    user_id = user["id"]
    chat_id = message["chat"]["id"]

    existing = get_player_game(user_id)

    if existing:
        send_message(
            chat_id,
            tr(user_id, "already_in_game"),
            game_keyboard(user_id),
        )
        return

    code = generate_game_code()

    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO games
                (code, owner_id, status)
                VALUES (%s, %s, 'waiting')
                RETURNING id
                """,
                (
                    code,
                    user_id,
                ),
            )

            game = cur.fetchone()

            cur.execute(
                """
                INSERT INTO players
                (game_id, user_id, username)
                VALUES (%s, %s, %s)
                """,
                (
                    game["id"],
                    user_id,
                    user.get("username")
                    or user.get("first_name")
                    or "Player",
                ),
            )

        conn.commit()

    send_message(
        chat_id,
        (
            f"{tr(user_id, 'game_created')}\n\n"
            f"{tr(user_id, 'game_code')} "
            f"`{code}`\n\n"
            f"{tr(user_id, 'share_code')}"
        ),
        game_keyboard(user_id),
    )


# ============================================================
# JOIN GAME
# ============================================================

def command_join_game(message):
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]

    existing = get_player_game(user_id)

    if existing:
        send_message(
            chat_id,
            tr(user_id, "already_in_game"),
        )
        return

    send_message(
        chat_id,
        tr(user_id, "enter_code"),
    )


def process_join_code(message):
    user = message["from"]
    user_id = user["id"]
    chat_id = message["chat"]["id"]

    code = message.get("text", "").strip().upper()

    if not code:
        return

    game = get_game_by_code(code)

    if not game:
        send_message(
            chat_id,
            tr(user_id, "invalid_code"),
        )
        return

    if game["status"] != "waiting":
        send_message(
            chat_id,
            tr(user_id, "game_started"),
        )
        return

    with get_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM players
                WHERE game_id = %s
                """,
                (game["id"],),
            )

            count = cur.fetchone()["count"]

            if count >= 12:
                send_message(
                    chat_id,
                    tr(user_id, "game_full"),
                )
                return

            cur.execute(
                """
                SELECT id
                FROM players
                WHERE game_id = %s
                  AND user_id = %s
                """,
                (
                    game["id"],
                    user_id,
                ),
            )

            if cur.fetchone():
                send_message(
                    chat_id,
                    tr(user_id, "already_in_game"),
                )
                return

            cur.execute(
                """
                INSERT INTO players
                (game_id, user_id, username)
                VALUES (%s, %s, %s)
                """,
                (
                    game["id"],
                    user_id,
                    user.get("username")
                    or user.get("first_name")
                    or "Player",
                ),
         
