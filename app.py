import os
import logging
import random
import string

import requests
import psycopg
from psycopg.rows import dict_row
from flask import Flask, request, jsonify


BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL",
    "https://strategy-game-3.onrender.com"
).rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", "10000"))


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)

app = Flask(__name__)


# ============================================================
# TRANSLATIONS
# ============================================================

T = {
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

        "enter_code": "کد بازی را ارسال کن.",
        "invalid_code": "کد بازی معتبر نیست.",
        "game_created": "بازی ساخته شد!",
        "game_code": "کد بازی:",
        "share_code": "این کد را برای بازیکنان دیگر بفرست.",
        "joined": "با موفقیت وارد بازی شدی.",
        "already_in_game": "تو در حال حاضر داخل یک بازی هستی.",
        "game_full": "ظرفیت بازی تکمیل شده است.",
        "game_started": "بازی شروع شده است.",
        "not_enough_players": "برای شروع حداقل ۲ بازیکن لازم است.",
        "select_country": "کشور خودت را انتخاب کن:",
        "country_taken": "این کشور قبلاً انتخاب شده است.",
        "country_selected": "کشور تو:",
        "all_ready": "همه بازیکنان کشور خود را انتخاب کرده‌اند.",
        "not_in_game": "تو در هیچ بازی فعالی نیستی.",
        "already_started": "این بازی قبلاً شروع شده است.",
        "owner_only": "فقط سازنده بازی می‌تواند بازی را شروع کند.",

        "help_text": (
            "🎮 راهنمای بازی\n\n"
            "1. بازی جدید بساز.\n"
            "2. کد بازی را برای دوستانت بفرست.\n"
            "3. آنها با گزینه ورود به بازی وارد شوند.\n"
            "4. وقتی همه آماده بودند، بازی را شروع کن.\n"
            "5. هر بازیکن یک کشور انتخاب می‌کند."
        ),

        "game_info": "اطلاعات بازی",
        "players": "بازیکنان",
        "status": "وضعیت",
        "waiting_status": "در انتظار شروع",
        "active_status": "فعال",
        "no_game": "بازی فعالی نداری.",
        "start_game": "▶️ شروع بازی",
        "unknown": "نامشخص",
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

        "enter_code": "Send the game code.",
        "invalid_code": "Invalid game code.",
        "game_created": "Game created!",
        "game_code": "Game code:",
        "share_code": "Send this code to the other players.",
        "joined": "You joined the game successfully.",
        "already_in_game": "You are already in a game.",
        "game_full": "The game is full.",
        "game_started": "The game has already started.",
        "not_enough_players": "At least 2 players are required.",
        "select_country": "Choose your country:",
        "country_taken": "This country has already been selected.",
        "country_selected": "Your country:",
        "all_ready": "All players have selected their countries.",
        "not_in_game": "You are not in an active game.",
        "already_started": "This game has already started.",
        "owner_only": "Only the game owner can start the game.",

        "help_text": (
            "🎮 Game Guide\n\n"
            "1. Create a new game.\n"
            "2. Send the game code to your friends.\n"
            "3. They can join using Join Game.\n"
            "4. Start the game when everyone is ready.\n"
            "5. Each player chooses a country."
        ),

        "game_info": "Game Information",
        "players": "Players",
        "status": "Status",
        "waiting_status": "Waiting to start",
        "active_status": "Active",
        "no_game": "You don't have an active game.",
        "start_game": "▶️ Start Game",
        "unknown": "Unknown",
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

def db():
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    )


def init_db():
    with db() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id BIGINT PRIMARY KEY,
                    language VARCHAR(10) NOT NULL DEFAULT 'fa'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id SERIAL PRIMARY KEY,
                    code VARCHAR(20) UNIQUE NOT NULL,
                    owner_id BIGINT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'waiting',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
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
            """)

        conn.commit()


# ============================================================
# LANGUAGE
# ============================================================

def lang(user_id):
    with db() as conn:
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
                ON CONFLICT DO NOTHING
                """,
                (user_id,),
            )

        conn.commit()

    return "fa"


def set_lang(user_id, value):
    if value not in ("fa", "en"):
        value = "fa"

    with db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO user_preferences
                (user_id, language)
                VALUES (%s, %s)
                ON CONFLICT(user_id)
                DO UPDATE SET language = EXCLUDED.language
                """,
                (user_id, value),
            )

        conn.commit()


def text(user_id, key):
    return T[lang(user_id)].get(key, key)


# ============================================================
# TELEGRAM
# ============================================================

def tg(method, data=None):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
            json=data or {},
            timeout=15,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as exc:
        logger.exception("Telegram API error")
        return {
            "ok": False,
            "error": str(exc),
        }


def send(chat_id, message, markup=None):
    data = {
        "chat_id": chat_id,
        "text": message,
    }

    if markup:
        data["reply_markup"] = markup

    return tg("sendMessage", data)


def answer(callback_id):
    return tg(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id,
        },
    )


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard(user_id):
    return {
        "keyboard": [
            [
                {
                    "text": text(user_id, "new_game")
                },
                {
                    "text": text(user_id, "join_game")
                },
            ],
            [
                {
                    "text": text(user_id, "my_game")
                },
                {
                    "text": text(user_id, "settings")
                },
            ],
            [
                {
                    "text": text(user_id, "help")
                }
            ],
        ],
        "resize_keyboard": True,
    }


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


def settings_keyboard(user_id):
    return {
        "keyboard": [
            [
                {
                    "text": text(user_id, "language")
                }
            ],
            [
                {
                    "text": text(user_id, "back")
                }
            ],
        ],
        "resize_keyboard": True,
    }


def game_keyboard(user_id):
    return {
        "keyboard": [
            [
                {
                    "text": text(user_id, "start_game")
                }
            ],
            [
                {
                    "text": text(user_id, "back")
                }
            ],
        ],
        "resize_keyboard": True,
    }


def country_keyboard():
    rows = []
    row = []

    for key, item in COUNTRIES.items():

        row.append(
            {
                "text": f"{item['fa']} / {item['en']}",
                "callback_data": f"country:{key}",
            }
        )

        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    return {
        "inline_keyboard": rows
    }


# ============================================================
# GAME HELPERS
# ============================================================

def game_code():
    while True:

        code = "".join(
            random.choices(
                string.ascii_uppercase + string.digits,
                k=6,
            )
        )

        with db() as conn:
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


def player_game(user_id):
    with db() as conn:
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


def players(game_id):
    with db() as conn:
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


def game_by_code(code):
    with db() as conn:
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


# ============================================================
# COMMANDS
# ============================================================

def start_cmd(message):
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]

    lang(user_id)

    send(
        chat_id,
        text(user_id, "welcome")
        + "\n\n"
        + text(user_id, "choose_language"),
        language_keyboard(),
    )


def help_cmd(message):
    user_id = message["from"]["id"]

    send(
        message["chat"]["id"],
        text(user_id, "help_text"),
        main_keyboard(user_id),
    )


def new_game(message):
    user = message["from"]
    user_id = user["id"]
    chat_id = message["chat"]["id"]

    if player_game(user_id):

        send(
            chat_id,
            text(user_id, "already_in_game"),
            game_keyboard(user_id),
        )

        return

    code = game_code()

    with db() as conn:
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

            game_id = cur.fetchone()["id"]

            name = (
                user.get("username")
                or user.get("first_name")
                or "Player"
            )

            cur.execute(
                """
                INSERT INTO players
                (game_id, user_id, username)
                VALUES (%s, %s, %s)
                """,
                (
                    game_id,
                    user_id,
                    name,
                ),
            )

        conn.commit()

    send(
        chat_id,
        (
            f"{text(user_id, 'game_created')}\n\n"
            f"{text(user_id, 'game_code')} {code}\n\n"
            f"{text(user_id, 'share_code')}"
        ),
        game_keyboard(user_id),
    )


def join_prompt(message):
    user_id = message["from"]["id"]

    send(
        message["chat"]["id"],
        text(user_id, "enter_code"),
    )


def join_code(message):
    user = message["from"]
    user_id = user["id"]
    chat_id = message["chat"]["id"]

    code = message.get("text", "").strip().upper()

    game = game_by_code(code)

    if not game:

        send(
            chat_id,
            text(user_id, "invalid_code"),
        )

        return

    if game["status"] != "waiting":

        send(
            chat_id,
            text(user_id, "game_started"),
        )

        return

    if player_game(user_id):

        send(
            chat_id,
            text(user_id, "already_in_game"),
        )

        return

    with db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT COUNT(*) AS n
                FROM players
                WHERE game_id = %s
                """,
                (game["id"],),
            )

            count = cur.fetchone()["n"]

            if count >= 12:

                send(
                    chat_id,
                    text(user_id, "game_full"),
                )

                return

            name = (
                user.get("username")
                or user.get("first_name")
                or "Player"
            )

            cur.execute(
                """
                INSERT INTO players
                (game_id, user_id, username)
                VALUES (%s, %s, %s)
                """,
                (
                    game["id"],
                    user_id,
                    name,
                ),
            )

        conn.commit()

    send(
        chat_id,
        text(user_id, "joined"),
        game_keyboard(user_id),
    )


def start_game(message):
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]

    game = player_game(user_id)

    if not game:

        send(
            chat_id,
            text(user_id, "not_in_game"),
        )

        return

    if game["owner_id"] != user_id:

        send(
            chat_id,
            text(user_id, "owner_only"),
        )

        return

    if game["status"] != "waiting":

        send(
            chat_id,
            text(user_id, "already_started"),
        )

        return

    plist = players(game["id"])

    if len(plist) < 2:

        send(
            chat_id,
            text(user_id, "not_enough_players"),
        )

        return

    with db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE games
                SET status = 'active'
                WHERE id = %s
                """,
                (game["id"],),
            )

        conn.commit()

    for player in plist:

        send(
            player["user_id"],
            text(player["user_id"], "select_country"),
            country_keyboard(),
        )


def my_game(message):
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]

    game = player_game(user_id)

    if not game:

        send(
            chat_id,
            text(user_id, "no_game"),
            main_keyboard(user_id),
        )

        return

    plist = players(game["id"])

    if game["status"] == "active":
        status = text(user_id, "active_status")
    else:
        status = text(user_id, "waiting_status")

    lines = [
        text(user_id, "game_info"),
        "",
        f"{text(user_id, 'game_code')} {game['code']}",
        f"{text(user_id, 'status')}: {status}",
        "",
        f"{text(user_id, 'players')}:",
    ]

    for player in plist:

        name = player["username"] or "Player"

        if player["country"]:

            country_name = COUNTRIES.get(
                player["country"],
                {},
            ).get(
                lang(player["user_id"]),
                player["country"],
            )

        else:

            country_
