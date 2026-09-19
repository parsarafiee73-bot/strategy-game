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
def telegram_request(method, data=None):
    if not TELEGRAM_API:
        logger.error("BOT_TOKEN is missing")
        return None

    try:
        response = requests.post(
            f"{TELEGRAM_API}/{method}",
            json=data or {},
            timeout=20
        )

        logger.info(
            "Telegram %s -> %s",
            method,
            response.status_code
        )

        return response.json()

    except Exception:
        logger.exception("Telegram API request failed")
        return None


def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    if reply_markup:
        data["reply_markup"] = reply_markup

    return telegram_request("sendMessage", data)


def answer_callback(callback_query_id, text=None):
    data = {
        "callback_query_id": callback_query_id
    }

    if text:
        data["text"] = text

    return telegram_request("answerCallbackQuery", data)


def edit_message(chat_id, message_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }

    if reply_markup:
        data["reply_markup"] = reply_markup

    return telegram_request("editMessageText", data)


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard(lang):
    return {
        "keyboard": [
            [
                {"text": t(lang, "new_game")},
                {"text": t(lang, "join_game")}
            ],
            [
                {"text": t(lang, "my_game")},
                {"text": t(lang, "help_btn")}
            ],
            [
                {"text": t(lang, "language")}
            ]
        ],
        "resize_keyboard": True
    }


def language_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🇮🇷 فارسی",
                    "callback_data": "lang:fa"
                },
                {
                    "text": "🇬🇧 English",
                    "callback_data": "lang:en"
                }
            ]
        ]
    }


def start_game_keyboard(game_id, lang):
    return {
        "inline_keyboard": [
            [
                {
                    "text": t(lang, "start_game"),
                    "callback_data": f"start:{game_id}"
                }
            ]
        ]
    }


def country_inline_keyboard(lang, game_id, taken_codes):
    rows = []
    row = []

    for country in COUNTRIES:
        if country["code"] in taken_codes:
            continue

        row.append({
            "text": country[lang],
            "callback_data": f"country:{game_id}:{country['code']}"
        })

        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    return {
        "inline_keyboard": rows
    }


# ============================================================
# GAME STATUS
# ============================================================

def game_status_text(game_id, lang):
    players = get_players(game_id)

    lines = []

    for i, player in enumerate(players, start=1):
        user_id, username, chat_id, country = player

        name = f"@{username}" if username else str(user_id)

        if country:
            country_text = country_name(country, lang)
        else:
            country_text = "—"

        lines.append(
            f"{i}. {name} — {country_text}"
        )

    if not lines:
        return "—"

    return "\n".join(lines)


# ============================================================
# MESSAGE HANDLER
# ============================================================

def handle_message(message):
    chat = message.get("chat", {})
    user = message.get("from", {})

    chat_id = chat.get("id")
    user_id = user.get("id")

    if not chat_id or not user_id:
        return

    username = user.get("username")

    lang = get_language(user_id)

    text = message.get("text", "")
    text = text.strip()

    # --------------------------------------------------------
    # COMMANDS
    # --------------------------------------------------------

    if text.startswith("/start"):
        clear_pending(user_id)

        send_message(
            chat_id,
            t(lang, "welcome"),
            main_keyboard(lang)
        )
        return

    if text.startswith("/help"):
        send_message(
            chat_id,
            t(lang, "help"),
            main_keyboard(lang)
        )
        return

    if text.startswith("/newgame"):
        create_new_game(chat_id, user_id, username, lang)
        return

    if text.startswith("/join"):
        set_pending(user_id, "join")

        send_message(
            chat_id,
            t(lang, "join_prompt"),
            main_keyboard(lang)
        )
        return

    # --------------------------------------------------------
    # BUTTONS
    # --------------------------------------------------------

    if text == t(lang, "new_game"):
        create_new_game(chat_id, user_id, username, lang)
        return

    if text == t(lang, "join_game"):
        set_pending(user_id, "join")

        send_message(
            chat_id,
            t(lang, "join_prompt"),
            main_keyboard(lang)
        )
        return

    if text == t(lang, "language"):
        send_message(
            chat_id,
            t(lang, "choose_language"),
            language_keyboard()
        )
        return

    if text == t(lang, "help_btn"):
        send_message(
            chat_id,
            t(lang, "help"),
            main_keyboard(lang)
        )
        return

    if text == t(lang, "my_game"):
        show_my_game(chat_id, user_id, lang)
        return

    # --------------------------------------------------------
    # PENDING ACTIONS
    # --------------------------------------------------------

    pending = get_pending(user_id)

    if pending == "join":
        code = text.upper()

        if len(code) != 6 or not code.isalnum():
            send_message(
                chat_id,
                t(lang, "invalid_code"),
                main_keyboard(lang)
            )
            return

        game = get_game_by_code(code)

        if not game:
            send_message(
                chat_id,
                t(lang, "game_not_found"),
                main_keyboard(lang)
            )
            return

        game_id, game_code, owner_id, status = game

        result = join_game(
            game_id,
            user_id,
            username,
            chat_id
        )

        if result == "not_found":
            send_message(chat_id, t(lang, "game_not_found"))
            return

        if result == "started":
            send_message(chat_id, t(lang, "game_started_join"))
            return

        if result == "already":
            send_message(chat_id, t(lang, "already_joined"))
            return

        if result == "error":
            send_message(chat_id, t(lang, "db_error"))
            return

        clear_pending(user_id)

        send_message(
            chat_id,
            t(lang, "joined"),
            main_keyboard(lang)
        )

        notify_game_players(game_id, lang)

        return

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    send_message(
        chat_id,
        t(lang, "unknown"),
        main_keyboard(lang)
    )


def create_new_game(chat_id, user_id, username, lang):
    clear_pending(user_id)

    game_id, code = create_game(
        user_id,
        username,
        chat_id
    )

    if not game_id:
        send_message(
            chat_id,
            t(lang, "db_error"),
            main_keyboard(lang)
        )
        return

    send_message(
        chat_id,
        t(
            lang,
            "new_game_created",
            code=code
        ),
        start_game_keyboard(game_id, lang)
    )


def show_my_game(chat_id, user_id, lang):
    game = get_user_game(user_id)

    if not game:
        send_message(
            chat_id,
            t(lang, "no_game"),
            main_keyboard(lang)
        )
        return

    game_id, code, owner_id, status = game

    status_text = (
        "⏳ Waiting"
        if status == "waiting"
        else "🚀 Active"
    )

    players_text = game_status_text(
        game_id,
        lang
    )

    text = (
        f"🎮 <b>{code}</b>\n\n"
        f"Status: {status_text}\n\n"
        f"{players_text}"
    )

    markup = None

    if (
        owner_id == user_id
        and status == "waiting"
    ):
        markup = start_game_keyboard(
            game_id,
            lang
        )

    send_message(
        chat_id,
        text,
        markup
    )


def notify_game_players(game_id, lang):
    players = get_players(game_id)

    text = (
        "👥 <b>Players</b>\n\n"
        + game_status_text(game_id, lang)
    )

    for player in players:
        chat_id = player[2]

        if chat_id:
            send_message(
                chat_id,
                text
            )


# ============================================================
# CALLBACK HANDLER
# ============================================================

def handle_callback(callback):
    callback_id = callback.get("id")

    data = callback.get("data", "")

    message = callback.get("message", {})
    chat = message.get("chat", {})
    user = callback.get("from", {})

    chat_id = chat.get("id")
    message_id = message.get("message_id")

    user_id = user.get("id")

    if not user_id:
        return

    lang = get_language(user_id)

    # --------------------------------------------------------
    # LANGUAGE
    # --------------------------------------------------------

    if data.startswith("lang:"):
        new_lang = data.split(":", 1)[1]

        if set_language(user_id, new_lang):
            answer_callback(
                callback_id,
                "Language changed."
            )

            send_message(
                chat_id,
                t(new_lang, "language_changed"),
                main_keyboard(new_lang)
            )

        return

    # --------------------------------------------------------
    # START GAME
    # --------------------------------------------------------

    if data.startswith("start:"):
        game_id = int(
            data.split(":", 1)[1]
        )

        result = start_game(
            game_id,
            user_id
        )

        if result == "owner":
            answer_callback(
                callback_id,
                t(lang, "only_owner")
            )
            return

        if result == "players":
            answer_callback(
                callback_id,
                t(lang, "need_players")
            )
            return

        if result == "started":
            answer_callback(
                callback_id,
                t(lang, "started")
            )
            return

        if result == "not_found":
            answer_callback(
                callback_id,
                t(lang, "game_not_found")
            )
            return

        if result == "error":
            answer_callback(
                callback_id,
                t(lang, "db_error")
            )
            return

        answer_callback(
            callback_id,
            t(lang, "started")
        )

        players = get_players(game_id)

        taken = get_taken_countries(game_id)

        for player in players:
            player_chat_id = player[2]

            if not player_chat_id:
                continue

            player_lang = get_language(
                player[0]
            )

            send_message(
                player_chat_id,
                t(
                    player_lang,
                    "choose_country"
                ),
                country_inline_keyboard(
                    player_lang,
                    game_id,
                    taken
                )
            )

        return

    # --------------------------------------------------------
    # COUNTRY
    # --------------------------------------------------------

    if data.startswith("country:"):
        parts = data.split(":")

        if len(parts) != 3:
            return

        game_id = int(parts[1])
        country_code = parts[2]

        result, selected = choose_country(
            game_id,
            user_id,
            country_code
        )

        if result == "taken":
            answer_callback(
                callback_id,
                t(lang, "country_taken")
            )
            return

        if result == "already":
            answer_callback(
                callback_id,
                t(
                    lang,
                    "country_already",
                    country=country_name(
                        selected,
                        lang
                    )
                )
            )
            return

        if result == "not_member":
            answer_callback(
                callback_id,
                t(lang, "no_game")
            )
            return

        if result == "error":
            answer_callback(
                callback_id,
                t(lang, "db_error")
            )
            return

        answer_callback(
            callback_id,
            "OK"
        )

        edit_message(
            chat_id,
            message_id,
            t(
                lang,
                "country_selected",
                country=country_name(
                    selected,
                    lang
                )
            )
        )

        return


# ============================================================
# FLASK ROUTES
# ============================================================

@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "service": "strategy-game"
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "ok"
    })


@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    try:
        if WEBHOOK_SECRET:
            received_secret = request.headers.get(
                "X-Telegram-Bot-Api-Secret-Token"
            )

            if received_secret != WEBHOOK_SECRET:
                return jsonify({
                    "ok": False,
                    "error": "Unauthorized"
                }), 403

        update = request.get_json(
            silent=True
        )

        if not update:
            return jsonify({
                "ok": True
            })

        if "message" in update:
            handle_message(
                update["message"]
            )

        elif "callback_query" in update:
            handle_callback(
                update["callback_query"]
            )

        return jsonify({
            "ok": True
        })

    except Exception:
        logger.exception(
            "Webhook processing failed"
        )

        return jsonify({
            "ok": False
        }), 500


@app.route("/set-webhook")
def set_webhook():
    if not TELEGRAM_API:
        return jsonify({
            "ok": False,
            "error": "BOT_TOKEN is missing"
        }), 500

    webhook = WEBHOOK_URL.rstrip(
        "/"
    ) + "/telegram"

    data = {
        "url": webhook
    }

    if WEBHOOK_SECRET:
        data["secret_token"] = WEBHOOK_SECRET

    result = telegram_request(
        "setWebhook",
        data
    )

    return jsonify(
        result or {
            "ok": False
        }
    )


@app.route("/webhook-info")
def webhook_info():
    result = telegram_request(
        "getWebhookInfo"
    )

    return jsonify(
        result or {
            "ok": False
        }
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "ok": False,
        "error": "Not found"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    logger.exception(
        "Internal server error"
    )

    return jsonify({
        "ok": False,
        "error": "Internal server error"
    }), 500


# ============================================================
# STARTUP
# ============================================================

try:
    init_db()
except Exception:
    logger.exception(
        "Startup database initialization failed"
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=PORT
        )
