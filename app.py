import os
import logging
import random
import string

import requests
import psycopg
from flask import Flask, request, jsonify
from psycopg.rows import dict_row


# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://strategy-game-3.onrender.com")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")


# =========================
# APP
# =========================

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =========================
# DATABASE
# =========================

def db():
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row
    )


def init_db():
    with db() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id BIGINT PRIMARY KEY,
                    language TEXT NOT NULL DEFAULT 'fa'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id SERIAL PRIMARY KEY,
                    code TEXT UNIQUE NOT NULL,
                    owner_id BIGINT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'waiting'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    game_id INTEGER NOT NULL REFERENCES games(id)
                        ON DELETE CASCADE,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    country TEXT,
                    UNIQUE(game_id, user_id)
                )
            """)

        conn.commit()


init_db()


# =========================
# TRANSLATIONS
# =========================

TEXT = {
    "fa": {
        "welcome": "🎮 به بازی استراتژیک خوش آمدی!",
        "choose": "یک گزینه را انتخاب کن:",
        "new_game": "🎮 ساخت بازی",
        "join_game": "🔑 ورود به بازی",
        "my_game": "📋 بازی من",
        "help": "ℹ️ راهنما",
        "language": "🌐 زبان",
        "game_created": "✅ بازی ساخته شد.\n\nکد بازی:",
        "send_code": "کد بازی را ارسال کن.",
        "invalid_code": "❌ کد بازی نامعتبر است.",
        "joined": "✅ با موفقیت وارد بازی شدی.",
        "not_found": "❌ بازی پیدا نشد.",
        "already_joined": "⚠️ قبلاً وارد این بازی شده‌ای.",
        "start_game": "🚀 شروع بازی",
        "waiting": "⏳ بازی هنوز شروع نشده است.",
        "started": "🚀 بازی شروع شد!",
        "choose_country": "🌍 کشور خودت را انتخاب کن:",
        "country_taken": "❌ این کشور قبلاً انتخاب شده است.",
        "country_selected": "✅ کشور تو انتخاب شد:",
        "players": "👥 بازیکنان:",
        "no_game": "❌ در هیچ بازی فعالی نیستی.",
        "help_text": (
            "راهنما:\n\n"
            "🎮 ساخت بازی: یک بازی جدید ایجاد می‌کند.\n"
            "🔑 ورود: با کد وارد بازی می‌شوی.\n"
            "🚀 شروع بازی: صاحب بازی آن را شروع می‌کند.\n"
            "🌍 بعد از شروع، هر بازیکن یک کشور انتخاب می‌کند."
        ),
        "language_fa": "🇮🇷 فارسی",
        "language_en": "🇬🇧 English",
    },

    "en": {
        "welcome": "🎮 Welcome to the strategy game!",
        "choose": "Choose an option:",
        "new_game": "🎮 New Game",
        "join_game": "🔑 Join Game",
        "my_game": "📋 My Game",
        "help": "ℹ️ Help",
        "language": "🌐 Language",
        "game_created": "✅ Game created.\n\nGame code:",
        "send_code": "Send the game code.",
        "invalid_code": "❌ Invalid game code.",
        "joined": "✅ You joined the game.",
        "not_found": "❌ Game not found.",
        "already_joined": "⚠️ You are already in this game.",
        "start_game": "🚀 Start Game",
        "waiting": "⏳ The game has not started yet.",
        "started": "🚀 Game started!",
        "choose_country": "🌍 Choose your country:",
        "country_taken": "❌ This country has already been taken.",
        "country_selected": "✅ Your country:",
        "players": "👥 Players:",
        "no_game": "❌ You are not in an active game.",
        "help_text": (
            "Help:\n\n"
            "🎮 New Game: creates a new game.\n"
            "🔑 Join: join using a game code.\n"
            "🚀 Start Game: the game owner starts the game.\n"
            "🌍 After starting, each player chooses a country."
        ),
        "language_fa": "🇮🇷 فارسی",
        "language_en": "🇬🇧 English",
    }
}


COUNTRIES = {
    "fa": [
        ("🇮🇷", "ایران"),
        ("🇺🇸", "آمریکا"),
        ("🇷🇺", "روسیه"),
        ("🇨🇳", "چین"),
        ("🇩🇪", "آلمان"),
        ("🇫🇷", "فرانسه"),
        ("🇬🇧", "بریتانیا"),
        ("🇯🇵", "ژاپن"),
        ("🇹🇷", "ترکیه"),
        ("🇮🇳", "هند"),
        ("🇧🇷", "برزیل"),
        ("🇪🇬", "مصر"),
    ],

    "en": [
        ("🇮🇷", "Iran"),
        ("🇺🇸", "USA"),
        ("🇷🇺", "Russia"),
        ("🇨🇳", "China"),
        ("🇩🇪", "Germany"),
        ("🇫🇷", "France"),
        ("🇬🇧", "UK"),
        ("🇯🇵", "Japan"),
        ("🇹🇷", "Turkey"),
        ("🇮🇳", "India"),
        ("🇧🇷", "Brazil"),
        ("🇪🇬", "Egypt"),
    ]
}


# =========================
# TELEGRAM
# =========================

def telegram(method, data=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    response = requests.post(
        url,
        json=data or {},
        timeout=20
    )

    return response.json()


def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup:
        data["reply_markup"] = reply_markup

    return telegram("sendMessage", data)


def answer_callback(callback_id):
    return telegram(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id
        }
    )


# =========================
# USER / LANGUAGE
# =========================

def get_language(user_id):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT language
                FROM user_preferences
                WHERE user_id = %s
                """,
                (user_id,)
            )

            row = cur.fetchone()

            if row:
                return row["language"]

            cur.execute(
                """
                INSERT INTO user_preferences(user_id, language)
                VALUES(%s, 'fa')
                ON CONFLICT DO NOTHING
                """,
                (user_id,)
            )

        conn.commit()

    return "fa"


def set_language(user_id, language):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_preferences(user_id, language)
                VALUES(%s, %s)
                ON CONFLICT(user_id)
                DO UPDATE SET language = EXCLUDED.language
                """,
                (user_id, language)
            )

        conn.commit()


# =========================
# KEYBOARDS
# =========================

def main_keyboard(lang):
    t = TEXT[lang]

    return {
        "keyboard": [
            [
                {"text": t["new_game"]},
                {"text": t["join_game"]}
            ],
            [
                {"text": t["my_game"]},
                {"text": t["help"]}
            ],
            [
                {"text": t["language"]}
            ]
        ],
        "resize_keyboard": True
    }


def start_game_keyboard(lang):
    return {
        "inline_keyboard": [
            [
                {
                    "text": TEXT[lang]["start_game"],
                    "callback_data": "start_game"
                }
            ]
        ]
    }


def language_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🇮🇷 فارسی",
                    "callback_data": "lang_fa"
                },
                {
                    "text": "🇬🇧 English",
                    "callback_data": "lang_en"
                }
            ]
        ]
    }


def country_keyboard(lang):
    buttons = []

    for flag, name in COUNTRIES[lang]:
        buttons.append([
            {
                "text": f"{flag} {name}",
                "callback_data": f"country:{name}"
            }
        ])

    return {
        "inline_keyboard": buttons
    }


# =========================
# GAME FUNCTIONS
# =========================

def generate_code():
    return "".join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=6
        )
    )


def create_game(user_id, username):
    while True:
        code = generate_code()

        try:
            with db() as conn:
                with conn.cursor() as cur:

                    cur.execute(
                        """
                        INSERT INTO games(code, owner_id)
                        VALUES(%s, %s)
                        RETURNING id
                        """,
                        (code, user_id)
                    )

                    game_id = cur.fetchone()["id"]

                    cur.execute(
                        """
                        INSERT INTO players(
                            game_id,
                            user_id,
                            username
                        )
                        VALUES(%s, %s, %s)
                        """,
                        (game_id, user_id, username)
                    )

                conn.commit()

            return code

        except psycopg.errors.UniqueViolation:
            continue


def get_game_by_code(code):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM games
                WHERE code = %s
                """,
                (code.upper(),)
            )

            return cur.fetchone()


def get_player_game(user_id):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    g.*,
                    p.country
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


def get_players(game_id):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, username, country
                FROM players
                WHERE game_id = %s
                ORDER BY id
                """,
                (game_id,)
            )

            return cur.fetchall()


# =========================
# START
# =========================

def handle_start(message):
    user = message["from"]
    chat_id = message["chat"]["id"]

    user_id = user["id"]
    lang = get_language(user_id)

    send_message(
        chat_id,
        TEXT[lang]["welcome"] + "\n\n" + TEXT[lang]["choose"],
        main_keyboard(lang)
    )


# =========================
# NEW GAME
# =========================

def handle_new_game(message):
    user = message["from"]
    chat_id = message["chat"]["id"]

    user_id = user["id"]
    username = user.get("username") or user.get("first_name", "Player")

    lang = get_language(user_id)

    code = create_game(user_id, username)

    send_message(
        chat_id,
        f'{TEXT[lang]["game_created"]}\n\n'
        f"🔑 `{code}`",
        start_game_keyboard(lang)
    )


# =========================
# JOIN
# =========================

def handle_join(message):
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]

    lang = get_language(user_id)

    send_message(
        chat_id,
        TEXT[lang]["send_code"]
    )


def handle_code(message):
    user = message["from"]
    chat_id = message["chat"]["id"]
    user_id = user["id"]

    code = message.get("text", "").strip().upper()

    if len(code) != 6:
        return False

    game = get_game_by_code(code)

    lang = get_language(user_id)

    if not game:
        send_message(
            chat_id,
            TEXT[lang]["invalid_code"]
        )
        return True

    with db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT id
                FROM players
                WHERE game_id = %s
                AND user_id = %s
                """,
                (game["id"], user_id)
            )

            existing = cur.fetchone()

            if existing:
                send_message(
                    chat_id,
                    TEXT[lang]["already_joined"]
                )
                return True

            cur.execute(
                """
                INSERT INTO players(
                    game_id,
                    user_id,
                    username
                )
                VALUES(%s, %s, %s)
                """,
                (
                    game["id"],
                    user_id,
                    user.get("username")
                    or user.get("first_name", "Player")
                )
            )

        conn.commit()

    send_message(
        chat_id,
        TEXT[lang]["joined"]
    )

    return True


# =========================
# MY GAME
# =========================

def handle_my_game(message):
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]

    lang = get_language(user_id)

    game = get_player_game(user_id)

    if not game:
        send_message(
            chat_id,
            TEXT[lang]["no_game"]
        )
        return

    players = get_players(game["id"])

    lines = [
        f"🎮 Game: {game['code']}",
        f"📌 Status: {game['status']}",
        "",
        TEXT[lang]["players"]
    ]

    for player in players:
        name = player["username"] or "Player"
        country = player["country"] or "—"

        lines.append(
            f"• {name} — {country}"
        )

    send_message(
        chat_id,
        "\n".join(lines)
    )


# =========================
# HELP
# =========================

def handle_help(message):
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]

    lang = get_language(user_id)

    send_message(
        chat_id,
        TEXT[lang]["help_text"]
    )


# =========================
# LANGUAGE
# =========================

def handle_language(message):
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]

    send_message(
        chat_id,
        "🌐 Language / زبان",
        language_keyboard()
    )


# =========================
# CALLBACKS
# =========================

def handle_callback(callback):
    callback_id = callback["id"]
    data = callback.get("data", "")
    user = callback["from"]

    user_id = user["id"]
    chat_id = callback["message"]["chat"]["id"]

    answer_callback(callback_id)

    # Language
    if data == "lang_fa":
        set_language(user_id, "fa")

        send_message(
            chat_id,
            TEXT["fa"]["welcome"] + "\n\n" + TEXT["fa"]["choose"],
            main_keyboard("fa")
        )
        return

    if data == "lang_en":
        set_language(user_id, "en")

        send_message(
            chat_id,
            TEXT["en"]["welcome"] + "\n\n" + TEXT["en"]["choose"],
            main_keyboard("en")
        )
        return

    lang = get_language(user_id)

    # Start game
    if data == "start_game":

        game = get_player_game(user_id)

        if not game:
            send_message(
                chat_id,
                TEXT[lang]["no_game"]
            )
            return

        if game["owner_id"] != user_id:
            send_message(
                chat_id,
                "❌ Only the game owner can start the game."
                if lang == "en"
                else "❌ فقط سازنده بازی می‌تواند بازی را شروع کند."
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
                    (game["id"],)
                )

            conn.commit()

        send_message(
            chat_id,
            TEXT[lang]["started"]
        )

        send_message(
            chat_id,
            TEXT[lang]["choose_country"],
            country_keyboard(lang)
        )

        return

    # Country
    if data.startswith("country:"):

        country = data.split(":", 1)[1]

        game = get_player_game(user_id)

        if not game:
            send_message(
                chat_id,
                TEXT[lang]["no_game"]
            )
            return

        if game["status"] != "active":
            send_message(
                chat_id,
                TEXT[lang]["waiting"]
            )
            return

        with db() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT id
                    FROM players
                    WHERE game_id = %s
                    AND country = %s
                    """,
                    (game["id"], country)
                )

                taken = cur.fetchone()

                if taken:
                    send_message(
                        chat_id,
                        TEXT[lang]["country_taken"]
                    )
                    return

                cur.execute(
                    """
                    UPDATE players
                    SET country = %s
                    WHERE game_id = %s
                    AND user_id = %s
                    """,
                    (
                        country,
                        game["id"],
                        user_id
                    )
                )

            conn.commit()

        send_message(
            chat_id,
            f'{TEXT[lang]["country_selected"]} {country}'
        )


# =========================
# TELEGRAM UPDATE
# =========================

def process_update(update):

    if "callback_query" in update:
        handle_callback(update["callback_query"])
        return

    message = update.get("message")

    if not message:
        return

    text = message.get("text", "").strip()

    if not text:
        return

    user_id = message["from"]["id"]
    lang = get_language(user_id)

    # Commands
    if text == "/start":
        handle_start(message)
        return

    if text == "/help":
        handle_help(message)
        return

    if text == "/newgame":
        handle_new_game(message)
        return

    if text == "/join":
        handle_join(message)
        return

    if text == "/startgame":
        handle_help(message)
        return

    # Buttons
    if text == TEXT[lang]["new_game"]:
        handle_new_game(message)
        return

    if text == TEXT[lang]["join_game"]:
        handle_join(message)
        return

    if text == TEXT[lang]["my_game"]:
        handle_my_game(message)
        return

    if text == TEXT[lang]["help"]:
        handle_help(message)
        return

    if text == TEXT[lang]["language"]:
        handle_language(message)
        return

    # Possible game code
    handle_code(message)


# =========================
# HEALTH
# =========================

@app.route("/")
def home():
    return "Strategy Game is running."


@app.route("/healt
