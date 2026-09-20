import json
import logging
import os
import random
import secrets
import string
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request
import psycopg
from psycopg.rows import dict_row


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
ADMIN_KEY = os.getenv("ADMIN_KEY", "").strip()
PORT = int(os.getenv("PORT", "10000"))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

logger = logging.getLogger("strategy-game")


# ============================================================
# TRANSLATIONS
# ============================================================

TEXTS = {
    "fa": {
        "welcome": (
            "سلام {name}!\n\n"
            "به بازی استراتژی چندنفره خوش آمدی.\n\n"
            "از دکمه‌های پایین برای ساخت یا پیوستن به بازی استفاده کن."
        ),

        "welcome_private": (
            "سلام {name}!\n\n"
            "بازی را می‌توانی از اینجا مدیریت کنی و بعد در گروه وارد لابی شوی."
        ),

        "choose_language": "زبان را انتخاب کن:",

        "language_saved": "زبان ذخیره شد.",

        "help": (
            "راهنما\n\n"
            "🎮 ساخت بازی: یک لابی جدید می‌سازد.\n"
            "🔑 پیوستن به بازی: با کد ۶ حرفی وارد لابی می‌شوی.\n"
            "🌍 کشور: کشور آزاد را برای بازی انتخاب می‌کنی.\n"
            "📋 بازی من: وضعیت بازی فعلی را می‌بینی.\n"
            "📖 قوانین: اقتصاد، تحقیق، صنعت و دیپلماسی را مدیریت کن و امتیاز بیشتری بگیر.\n\n"
            "حداقل ۲ بازیکن برای شروع لازم است."
        ),

        "rules": (
            "قوانین نسخه فعلی\n\n"
            "• هر بازیکن یک کشور انتخاب می‌کند.\n"
            "• بازی نوبتی است.\n"
            "• در هر نوبت ۳ اقدام داری.\n"
            "• اقدام‌ها: ساخت صنعت، تحقیق، تجارت و دیپلماسی.\n"
            "• پایان هر نوبت درآمد و منابع پایه تولید می‌شود.\n"
            "• بازی در ۳۰ نوبت کل تمام می‌شود.\n"
            "• امتیاز بر اساس پول، صنعت، تحقیق، ثبات و جمعیت محاسبه می‌شود."
        ),

        "unknown": "دستور یا پیام نامشخص است. از دکمه‌های پایین استفاده کن.",

        "need_group": (
            "این گزینه را بهتر است داخل گروهی که بازی در آن برگزار می‌شود اجرا کنی."
        ),

        "game_created": (
            "بازی ساخته شد ✅\n\n"
            "کد بازی: <code>{code}</code>\n"
            "سازنده: {name}\n\n"
            "کد را برای بقیه بازیکن‌ها بفرست."
        ),

        "game_already": (
            "تو همین الان در یک بازی فعال هستی: <code>{code}</code>."
        ),

        "join_enter_code": "کد ۶ حرفی بازی را بفرست.",

        "invalid_code": "کد باید دقیقاً ۶ حرف یا عدد باشد.",

        "game_not_found": (
            "چنین بازی‌ای پیدا نشد یا بازی دیگر در وضعیت انتظار نیست."
        ),

        "joined": (
            "وارد بازی شدی ✅\n\n{game}"
        ),

        "already_in_game": "تو از قبل داخل این بازی هستی.",

        "country_open": "یک کشور آزاد انتخاب کن:",

        "country_taken": (
            "این کشور قبلاً توسط بازیکن دیگری انتخاب شده است."
        ),

        "country_saved": (
            "کشور {country} برای تو ثبت شد ✅"
        ),

        "need_country": (
            "قبل از شروع، همه بازیکن‌ها باید کشورشان را انتخاب کنند."
        ),

        "not_owner": (
            "فقط سازنده بازی می‌تواند آن را شروع کند."
        ),

        "need_players": (
            "برای شروع حداقل ۲ بازیکن لازم است."
        ),

        "game_started": (
            "بازی شروع شد 🚀\n\nنوبت اول: {player}"
        ),

        "not_your_turn": (
            "الان نوبت تو نیست. نوبت: {player}"
        ),

        "not_running": (
            "بازی در حال اجرا نیست."
        ),

        "action_done": (
            "اقدام انجام شد ✅\n\n{summary}"
        ),

        "not_enough_money": (
            "پول کافی نیست. موجودی فعلی: {money}"
        ),

        "not_enough_actions": (
            "اقدام‌های این نوبت تمام شده‌اند. نوبت را تمام کن."
        ),

        "turn_ended": (
            "نوبت {turn} تمام شد. نوبت بعد: {player}"
        ),

        "game_finished": (
            "بازی تمام شد 🏁\n\n{results}"
        ),

        "no_game": (
            "فعلاً در هیچ بازی فعالی نیستی."
        ),

        "status": "{game}",

        "players_title": "بازیکنان",

        "lobby": "لابی بازی",

        "running": "بازی در حال اجرا",

        "finished": "بازی تمام شده",

        "waiting": "در انتظار بازیکن",

        "owner": "سازنده",

        "turn": "نوبت",

        "round": "دوره",

        "actions": "اقدام‌های باقی‌مانده",

        "money": "پول",

        "industry": "صنعت",

        "science": "تحقیق",

        "stability": "ثبات",

        "population": "جمعیت",

        "country": "کشور",

        "no_country": "انتخاب نشده",

        "start_game": "شروع بازی",

        "choose_country": "🌍 انتخاب کشور",

        "join_button": "🔑 پیوستن به بازی",

        "create_button": "🎮 ساخت بازی",

        "my_game": "📋 بازی من",

        "language_button": "🌐 زبان",

        "help_button": "❓ راهنما",

        "rules_button": "📖 قوانین",

        "game_menu": "🎯 بازی",

        "build": "🏭 ساخت صنعت",

        "research": "🔬 تحقیق",

        "trade": "💰 تجارت",

        "diplomacy": "🤝 دیپلماسی",

        "end_turn": "⏭️ پایان نوبت",

        "back": "🔙 بازگشت",

        "cancel": "❌ لغو",

        "private_tip": (
            "برای هماهنگی بهتر، این پیام را داخل گروه بازی اجرا کن."
        ),

        "admin_only": "این مسیر مدیریتی است.",

        "migrated": "Database migration completed.",
    },

    "en": {
        "welcome": (
            "Hi {name}!\n\n"
            "Welcome to the multiplayer strategy game.\n\n"
            "Use the buttons below to create or join a game."
        ),

        "welcome_private": (
            "Hi {name}!\n\n"
            "You can manage the game here and then play in your group."
        ),

        "choose_language": "Choose your language:",

        "language_saved": "Language saved.",

        "help": (
            "Help\n\n"
            "🎮 Create Game: create a new lobby.\n"
            "🔑 Join Game: join a lobby with a 6-character code.\n"
            "🌍 Country: choose an available country.\n"
            "📋 My Game: show your current game.\n"
            "📖 Rules: manage economy, research, industry and diplomacy.\n\n"
            "At least 2 players are required to start."
        ),

        "rules": (
            "Current rules\n\n"
            "• Each player chooses one country.\n"
            "• The game is turn-based.\n"
            "• You have 3 actions per turn.\n"
            "• Actions: industry, research, trade and diplomacy.\n"
            "• Each completed turn generates base income and resources.\n"
            "• The game ends after 30 total turns.\n"
            "• Score uses money, industry, research, stability and population."
        ),

        "unknown": (
            "I didn't understand that. Please use the buttons."
        ),

        "need_group": (
            "This option works best inside the group where the game will be played."
        ),

        "game_created": (
            "Game created ✅\n\n"
            "Game code: <code>{code}</code>\n"
            "Owner: {name}\n\n"
            "Send the code to the other players."
        ),

        "game_already": (
            "You are already in an active game: <code>{code}</code>."
        ),

        "join_enter_code": (
            "Send the 6-character game code."
        ),

        "invalid_code": (
            "The code must be exactly 6 letters or digits."
        ),

        "game_not_found": (
            "That game was not found or is no longer waiting."
        ),

        "joined": (
            "You joined the game ✅\n\n{game}"
        ),

        "already_in_game": (
            "You are already in this game."
        ),

        "country_open": (
            "Choose an available country:"
        ),

        "country_taken": (
            "That country has already been chosen."
        ),

        "country_saved": (
            "Country {country} saved ✅"
        ),

        "need_country": (
            "Everyone must choose a country before the game can start."
        ),

        "not_owner": (
            "Only the game owner can start the game."
        ),

        "need_players": (
            "At least 2 players are required."
        ),

        "game_started": (
            "Game started 🚀\n\nFirst turn: {player}"
        ),

        "not_your_turn": (
            "It is not your turn. Current turn: {player}"
        ),

        "not_running": (
            "The game is not running."
        ),

        "action_done": (
            "Action completed ✅\n\n{summary}"
        ),

        "not_enough_money": (
            "Not enough money. Current balance: {money}"
        ),

        "not_enough_actions": (
            "You have no actions left. End your turn."
        ),

        "turn_ended": (
            "Turn {turn} ended. Next: {player}"
        ),

        "game_finished": (
            "Game finished 🏁\n\n{results}"
        ),

        "no_game": (
            "You are not in an active game."
        ),

        "status": "{game}",

        "players_title": "Players",

        "lobby": "Game lobby",

        "running": "Game running",

        "finished": "Game finished",

        "waiting": "Waiting for players",

        "owner": "Owner",

        "turn": "Turn",

        "round": "Round",

        "actions": "Actions left",

        "money": "Money",

        "industry": "Industry",

        "science": "Research",

        "stability": "Stability",

        "population": "Population",

        "country": "Country",

        "no_country": "Not selected",

        "start_game": "Start Game",

        "choose_country": "🌍 Choose Country",

        "join_button": "🔑 Join Game",

        "create_button": "🎮 Create Game",

        "my_game": "📋 My Game",

        "language_button": "🌐 Language",

        "help_button": "❓ Help",

        "rules_button": "📖 Rules",

        "game_menu": "🎯 Game",

        "build": "🏭 Build Industry",

        "research": "🔬 Research",

        "trade": "💰 Trade",

        "diplomacy": "🤝 Diplomacy",

        "end_turn": "⏭️ End Turn",

        "back": "🔙 Back",

        "cancel": "❌ Cancel",

        "private_tip": (
            "For coordination, run this message inside your game group."
        ),

        "admin_only": (
            "This is an administrative route."
        ),

        "migrated": (
            "Database migration completed."
        ),
    },
}


# ============================================================
# COUNTRIES
# ============================================================

COUNTRIES = {
    "IR": {
        "fa": "ایران",
        "en": "Iran",
        "industry": 11,
        "science": 4,
        "stability": 68,
        "population": 85,
    },

    "US": {
        "fa": "ایالات متحده",
        "en": "United States",
        "industry": 18,
        "science": 10,
        "stability": 72,
        "population": 90,
    },

    "CN": {
        "fa": "چین",
        "en": "China",
        "industry": 17,
        "science": 8,
        "stability": 74,
        "population": 95,
    },

    "DE": {
        "fa": "آلمان",
        "en": "Germany",
        "industry": 16,
        "science": 9,
        "stability": 78,
        "population": 55,
    },

    "FR": {
        "fa": "فرانسه",
        "en": "France",
        "industry": 14,
        "science": 8,
        "stability": 76,
        "population": 52,
    },

    "TR": {
        "fa": "ترکیه",
        "en": "Türkiye",
        "industry": 12,
        "science": 5,
        "stability": 66,
        "population": 60,
    },

    "JP": {
        "fa": "ژاپن",
        "en": "Japan",
        "industry": 15,
        "science": 10,
        "stability": 82,
        "population": 50,
    },

    "IN": {
        "fa": "هند",
        "en": "India",
        "industry": 13,
        "science": 7,
        "stability": 67,
        "population": 100,
    },

    "BR": {
        "fa": "برزیل",
        "en": "Brazil",
        "industry": 10,
        "science": 4,
        "stability": 65,
        "population": 72,
    },

    "CA": {
        "fa": "کانادا",
        "en": "Canada",
        "industry": 11,
        "science": 8,
        "stability": 80,
        "population": 38,
    },

    "EG": {
        "fa": "مصر",
        "en": "Egypt",
        "industry": 9,
        "science": 3,
        "stability": 63,
        "population": 68,
    },

    "KR": {
        "fa": "کره جنوبی",
        "en": "South Korea",
        "industry": 15,
        "science": 10,
        "stability": 79,
        "population": 48,
    },
}


# ============================================================
# HELPERS
# ============================================================

def t(user_id: int, key: str, **kwargs: Any) -> str:
    language = get_language(user_id)

    value = (
        TEXTS
        .get(language, TEXTS["en"])
        .get(key, key)
    )

    return value.format(**kwargs)


def country_name(
    code: Optional[str],
    language: str = "en"
) -> str:

    if not code or code not in COUNTRIES:
        return TEXTS.get(
            language,
            TEXTS["en"]
        )["no_country"]

    return COUNTRIES[code][language]


def display_name(user: Dict[str, Any]) -> str:
    first = (
        user.get("first_name") or ""
    ).strip()

    last = (
        user.get("last_name") or ""
    ).strip()

    username = (
        user.get("username") or ""
    ).strip()

    full = " ".join(
        x for x in (first, last)
        if x
    ).strip()

    if full:
        return full

    if username:
        return f"@{username}"

    return str(
        user.get("id", "Player")
    )


@contextmanager
def get_conn():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is missing"
        )

    conn = psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row
    )

    try:
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def generate_code(length: int = 6) -> str:
    alphabet = (
        string.ascii_uppercase +
        string.digits
    )

    return "".join(
        secrets.choice(alphabet)
        for _ in range(length)
    )


# ============================================================
# DATABASE / MIGRATION
# ============================================================

def column_exists(
    cur,
    table: str,
    column: str
) -> bool:

    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        """,
        (table, column),
    )

    return cur.fetchone() is not None


def add_column_if_missing(
    cur,
    table: str,
    column: str,
    definition: str
):
    if not column_exists(
        cur,
        table,
        column
    ):

        cur.execute(
            f'ALTER TABLE "{table}" '
            f'ADD COLUMN "{column}" {definition}'
        )

        logger.info(
            "Added missing column %s.%s",
            table,
            column
        )


def init_db():

    with get_conn() as conn:

        with conn.cursor() as cur:

            # ------------------------------------------------
            # USER PREFERENCES
            # ------------------------------------------------

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id BIGINT PRIMARY KEY,
                    language TEXT NOT NULL DEFAULT 'fa',
                    pending_action TEXT,
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )

            # ------------------------------------------------
            # GAMES
            # ------------------------------------------------

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS games (
                    id SERIAL PRIMARY KEY,
                    code VARCHAR(6) UNIQUE NOT NULL,
                    owner_id BIGINT,
                    status TEXT NOT NULL DEFAULT 'waiting',
                    total_turn INTEGER NOT NULL DEFAULT 0,
                    current_player_id BIGINT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )

            # ------------------------------------------------
            # PLAYERS
            # ------------------------------------------------

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    game_id INTEGER NOT NULL
                        REFERENCES games(id)
                        ON DELETE CASCADE,

                    user_id BIGINT NOT NULL,

                    username TEXT,

                    first_name TEXT,

                    chat_id BIGINT,

                    country VARCHAR(2),

                    money INTEGER NOT NULL DEFAULT 1000,

                    industry INTEGER NOT NULL DEFAULT 10,

                    science INTEGER NOT NULL DEFAULT 0,

                    stability INTEGER NOT NULL DEFAULT 70,

                    population INTEGER NOT NULL DEFAULT 50,

                    actions_left INTEGER NOT NULL DEFAULT 3,

                    score INTEGER NOT NULL DEFAULT 0,

                    joined_at TIMESTAMP NOT NULL DEFAULT NOW(),

                    UNIQUE(game_id, user_id)
                )
                """
            )

            # ------------------------------------------------
            # AUTOMATIC MIGRATION
            # ------------------------------------------------

            add_column_if_missing(
                cur,
                "user_preferences",
                "pending_action",
                "TEXT"
            )

            add_column_if_missing(
                cur,
                "user_preferences",
                "updated_at",
                "TIMESTAMP NOT NULL DEFAULT NOW()"
            )

            add_column_if_missing(
                cur,
                "games",
                "owner_id",
                "BIGINT"
            )

            add_column_if_missing(
                cur,
                "games",
                "total_turn",
                "INTEGER NOT NULL DEFAULT 0"
            )

            add_column_if_missing(
                cur,
                "games",
                "current_player_id",
                "BIGINT"
            )

            add_column_if_missing(
                cur,
                "games",
                "created_at",
                "TIMESTAMP NOT NULL DEFAULT NOW()"
            )

            add_column_if_missing(
                cur,
                "games",
                "updated_at",
                "TIMESTAMP NOT NULL DEFAULT NOW()"
            )

            add_column_if_missing(
                cur,
                "players",
                "username",
                "TEXT"
            )

            add_column_if_missing(
                cur,
                "players",
                "first_name",
                "TEXT"
            )

       # ============================================================
# USER SETTINGS
# ============================================================

def get_language(user_id: int) -> str:
    with get_conn() as conn:
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

            if not row:
                cur.execute(
                    """
                    INSERT INTO user_preferences
                        (user_id, language)
                    VALUES (%s, 'fa')
                    ON CONFLICT (user_id)
                    DO NOTHING
                    """,
                    (user_id,)
                )

                return "fa"

            language = row["language"]

            if language not in ("fa", "en"):
                return "fa"

            return language


def set_language(
    user_id: int,
    language: str
):
    if language not in ("fa", "en"):
        language = "fa"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_preferences
                    (user_id, language)
                VALUES (%s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    language = EXCLUDED.language,
                    updated_at = NOW()
                """,
                (user_id, language)
            )


def get_pending_action(
    user_id: int
) -> Optional[str]:

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

            if not row:
                return None

            return row["pending_action"]


def set_pending_action(
    user_id: int,
    action: Optional[str]
):

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO user_preferences
                    (user_id, pending_action)
                VALUES (%s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    pending_action = EXCLUDED.pending_action,
                    updated_at = NOW()
                """,
                (user_id, action)
            )


# ============================================================
# GAME DATABASE FUNCTIONS
# ============================================================

def create_game(
    owner_id: int,
    chat_id: Optional[int],
    username: Optional[str],
    first_name: Optional[str]
) -> Dict[str, Any]:

    for _ in range(20):

        code = generate_code(6)

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:

                    cur.execute(
                        """
                        INSERT INTO games (
                            code,
                            owner_id,
                            status,
                            total_turn
                        )
                        VALUES (
                            %s,
                            %s,
                            'waiting',
                            0
                        )
                        RETURNING *
                        """,
                        (
                            code,
                            owner_id
                        )
                    )

                    game = cur.fetchone()

                    cur.execute(
                        """
                        INSERT INTO players (
                            game_id,
                            user_id,
                            username,
                            first_name,
                            chat_id,
                            money,
                            industry,
                            science,
                            stability,
                            population,
                            actions_left,
                            score
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            1000,
                            10,
                            0,
                            70,
                            50,
                            3,
                            0
                        )
                        """,
                        (
                            game["id"],
                            owner_id,
                            username,
                            first_name,
                            chat_id
                        )
                    )

                    return game

        except psycopg.errors.UniqueViolation:
            continue

    raise RuntimeError(
        "Could not generate a unique game code."
    )


def get_game_by_code(
    code: str
) -> Optional[Dict[str, Any]]:

    code = code.strip().upper()

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM games
                WHERE code = %s
                """,
                (code,)
            )

            return cur.fetchone()


def get_game_by_id(
    game_id: int
) -> Optional[Dict[str, Any]]:

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM games
                WHERE id = %s
                """,
                (game_id,)
            )

            return cur.fetchone()


def get_user_game(
    user_id: int
) -> Optional[Dict[str, Any]]:

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT g.*
                FROM games g
                JOIN players p
                    ON p.game_id = g.id
                WHERE p.user_id = %s
                  AND g.status IN (
                      'waiting',
                      'running'
                  )
                ORDER BY g.id DESC
                LIMIT 1
                """,
                (user_id,)
            )

            return cur.fetchone()


def get_players(
    game_id: int
) -> List[Dict[str, Any]]:

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM players
                WHERE game_id = %s
                ORDER BY id ASC
                """,
                (game_id,)
            )

            return cur.fetchall()


def get_player(
    game_id: int,
    user_id: int
) -> Optional[Dict[str, Any]]:

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM players
                WHERE game_id = %s
                  AND user_id = %s
                LIMIT 1
                """,
                (
                    game_id,
                    user_id
                )
            )

            return cur.fetchone()


def get_player_by_id(
    player_id: int
) -> Optional[Dict[str, Any]]:

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM players
                WHERE id = %s
                LIMIT 1
                """,
                (player_id,)
            )

            return cur.fetchone()


def add_player_to_game(
    game_id: int,
    user_id: int,
    chat_id: Optional[int],
    username: Optional[str],
    first_name: Optional[str]
) -> Dict[str, Any]:

    with get_conn() as conn:
        with conn.cursor() as cur:

            # Check game
            cur.execute(
                """
                SELECT *
                FROM games
                WHERE id = %s
                FOR UPDATE
                """,
                (game_id,)
            )

            game = cur.fetchone()

            if not game:
                raise ValueError(
                    "GAME_NOT_FOUND"
                )

            if game["status"] != "waiting":
                raise ValueError(
                    "GAME_NOT_WAITING"
                )

            # Already joined?
            cur.execute(
                """
                SELECT *
                FROM players
                WHERE game_id = %s
                  AND user_id = %s
                """,
                (
                    game_id,
                    user_id
                )
            )

            existing = cur.fetchone()

            if existing:
                return existing

            # Maximum 12 players
            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM players
                WHERE game_id = %s
                """,
                (game_id,)
            )

            count = cur.fetchone()["count"]

            if count >= 12:
                raise ValueError(
                    "GAME_FULL"
                )

            cur.execute(
                """
                INSERT INTO players (
                    game_id,
                    user_id,
                    username,
                    first_name,
                    chat_id,
                    money,
                    industry,
                    science,
                    stability,
                    population,
                    actions_left,
                    score
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    1000,
                    10,
                    0,
                    70,
                    50,
                    3,
                    0
                )
                RETURNING *
                """,
                (
                    game_id,
                    user_id,
                    username,
                    first_name,
                    chat_id
                )
            )

            return cur.fetchone()


def set_player_country(
    game_id: int,
    user_id: int,
    country: str
):

    country = country.upper()

    if country not in COUNTRIES:
        raise ValueError(
            "INVALID_COUNTRY"
        )

    with get_conn() as conn:
        with conn.cursor() as cur:

            # Lock game
            cur.execute(
                """
                SELECT *
                FROM games
                WHERE id = %s
                FOR UPDATE
                """,
                (game_id,)
            )

            game = cur.fetchone()

            if not game:
                raise ValueError(
                    "GAME_NOT_FOUND"
                )

            if game["status"] != "waiting":
                raise ValueError(
                    "GAME_NOT_WAITING"
                )

            # Make sure player exists
            cur.execute(
                """
                SELECT *
                FROM players
                WHERE game_id = %s
                  AND user_id = %s
                """,
                (
                    game_id,
                    user_id
                )
            )

            player = cur.fetchone()

            if not player:
                raise ValueError(
                    "NOT_PLAYER"
                )

            # Is country already taken?
            cur.execute(
                """
                SELECT user_id
                FROM players
                WHERE game_id = %s
                  AND country = %s
                  AND user_id <> %s
                """,
                (
                    game_id,
                    country,
                    user_id
                )
            )

            taken = cur.fetchone()

            if taken:
                raise ValueError(
                    "COUNTRY_TAKEN"
                )

            base = COUNTRIES[country]

            cur.execute(
                """
                UPDATE players
                SET
                    country = %s,
                    industry = %s,
                    science = %s,
                    stability = %s,
                    population = %s,
                    score = 0
                WHERE game_id = %s
                  AND user_id = %s
                """,
                (
                    country,
                    base["industry"],
                    base["science"],
                    base["stability"],
                    base["population"],
                    game_id,
                    user_id
                )
            )


def get_taken_countries(
    game_id: int
) -> List[str]:

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

            return [
                row["country"]
                for row in cur.fetchall()
            ]


def all_players_have_country(
    game_id: int
) -> bool:

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT COUNT(*) AS total,
                       COUNT(country) AS selected
                FROM players
                WHERE game_id = %s
                """,
                (game_id,)
            )

            row = cur.fetchone()

            return (
                row["total"] > 0
                and
                row["total"] == row["selected"]
            )


def calculate_score(
    player: Dict[str, Any]
) -> int:

    return int(
        player["money"] // 20
        + player["industry"] * 5
        + player["science"] * 8
        + player["stability"] * 2
        + player["population"]
    )


def refresh_player_score(
    game_id: int,
    user_id: int
):

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM players
                WHERE game_id = %s
                  AND user_id = %s
                """,
                (
                    game_id,
                    user_id
                )
            )

            player = cur.fetchone()

            if not player:
                return

            score = calculate_score(player)

            cur.execute(
                """
                UPDATE players
                SET score = %s
                WHERE game_id = %s
                  AND user_id = %s
                """,
                (
                    score,
                    game_id,
                    user_id
                )
            )


def refresh_all_scores(
    game_id: int
):

    players = get_players(game_id)

    with get_conn() as conn:
        with conn.cursor() as cur:

            for player in players:

                score = calculate_score(player)

                cur.execute(
                    """
                    UPDATE players
                    SET score = %s
                    WHERE id = %s
                    """,
                    (
                        score,
                        player["id"]
                    )
                )


# ============================================================
# GAME STATUS / FORMATTING
# ============================================================

def game_status_text(
    game: Dict[str, Any],
    language: str
) -> str:

    players = get_players(
        game["id"]
    )

    status_map = {
        "waiting": TEXTS[language]["waiting"],
        "running": TEXTS[language]["running"],
        "finished": TEXTS[language]["finished"],
    }

    status_text = status_map.get(
        game["status"],
        game["status"]
    )

    lines = [
        f"<b>{TEXTS[language]['lobby']}</b>",
        "",
        f"🎟 <b>Code:</b> <code>{game['code']}</code>",
        f"📌 <b>Status:</b> {status_text}",
    ]

    if game["status"] == "running":
        lines.append(
            f"🔄 <b>{TEXTS[language]['turn']}:</b> "
            f"{game['total_turn']}"
        )

        current = get_player_by_id(
            game["current_player_id"]
        ) if game["current_player_id"] else None

        if current:
            current_name = (
                current.get("first_name")
                or current.get("username")
                or str(current["user_id"])
            )

            lines.append(
                f"🎯 <b>Current:</b> {current_name}"
            )

    lines.extend([
        "",
        f"<b>{TEXTS[language]['players_title']}:</b>"
    ])

    for index, player in enumerate(
        players,
        start=1
    ):

        name = (
            player.get("first_name")
            or (
                "@" + player["username"]
                if player.get("username")
                else str(player["user_id"])
            )
        )

        country = country_name(
            player.get("country"),
            language
        )

        marker = ""

        if player["user_id"] == game["owner_id"]:
            marker = " 👑"

        lines.append(
            f"{index}. {name}{marker} — {country}"
        )

        if game["status"] == "running":
            lines.append(
                f"   💰 {player['money']} | "
                f"🏭 {player['industry']} | "
                f"🔬 {player['science']} | "
                f"🛡 {player['stability']} | "
                f"👥 {player['population']} | "
                f"⭐ {player['score']}"
            )

    return "\n".join(lines)


def final_results_text(
    game_id: int,
    language: str
) -> str:

    players = get_players(game_id)

    players.sort(
        key=lambda p: calculate_score(p),
        reverse=True
    )

    lines = []

    for index, player in enumerate(
        players,
        start=1
    ):

        score = calculate_score(player)

        name = (
            player.get("first_name")
            or (
                "@" + player["username"]
                if player.get("username")
                else str(player["user_id"])
            )
        )

        country = country_name(
            player.get("country"),
            language
        )

        lines.append(
            f"{index}. <b>{name}</b> "
            f"({country}) — ⭐ {score}"
        )

    return "\n".join(lines)


# ============================================================
# START GAME
# ============================================================

def start_game(
    game_id: int,
    owner_id: int
) -> Dict[str, Any]:

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM games
                WHERE id = %s
                FOR UPDATE
                """,
                (game_id,)
            )

            game = cur.fetchone()

            if not game:
                raise ValueError(
                    "GAME_NOT_FOUND"
                )

            if game["owner_id"] != owner_id:
                raise ValueError(
                    "NOT_OWNER"
                )

            if game["status"] != "waiting":
                raise ValueError(
                    "GAME_NOT_WAITING"
                )

            # Check number of players
            cur.execute(
                """
                SELECT *
                FROM players
                WHERE game_id = %s
                ORDER BY id ASC
                """,
                (game_id,)
            )

            players = cur.fetchall()

            if len(players) < 2:
                raise ValueError(
                    "NOT_ENOUGH_PLAYERS"
                )

            # Everyone must choose a country
            for player in players:

                if not player["country"]:
                    raise ValueError(
                        "COUNTRY_NOT_SELECTED"
                    )

            # First player starts the game
            first_player = players[0]

            # Reset actions for all players
            cur.execute(
                """
                UPDATE players
                SET actions_left = 3
                WHERE game_id = %s
                """,
                (game_id,)
            )

            # Start game
            cur.execute(
                """
                UPDATE games
                SET
                    status = 'running',
                    total_turn = 1,
                    current_player_id = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (
                    first_player["id"],
                    game_id
                )
            )

            started_game = cur.fetchone()

            return started_game

 
          # ============================================================
# GAME ACTIONS
# ============================================================

ACTION_COSTS = {
    "build": 250,
    "research": 200,
    "trade": 150,
    "diplomacy": 180,
}


def can_take_action(
    player: Dict[str, Any]
) -> bool:

    return (
        player["actions_left"] > 0
    )


def perform_build(
    game_id: int,
    user_id: int
) -> Dict[str, Any]:

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM players
                WHERE game_id = %s
                  AND user_id = %s
                FOR UPDATE
                """,
                (
                    game_id,
                    user_id
                )
            )

            player = cur.fetchone()

            if not player:
                raise ValueError(
                    "NOT_PLAYER"
                )

            if not can_take_action(player):
                raise ValueError(
                    "NO_ACTIONS"
                )

            cost = ACTION_COSTS["build"]

            if player["money"] < cost:
                raise ValueError(
                    "NOT_ENOUGH_MONEY"
                )

            new_industry = (
                player["industry"] + 2
            )

            new_money = (
                player["money"] - cost
            )

            new_actions = (
                player["actions_left"] - 1
            )

            cur.execute(
                """
                UPDATE players
                SET
                    money = %s,
                    industry = %s,
                    actions_left = %s
                WHERE id = %s
                RETURNING *
                """,
                (
                    new_money,
                    new_industry,
                    new_actions,
                    player["id"]
                )
            )

            updated = cur.fetchone()

            score = calculate_score(
                updated
            )

            cur.execute(
                """
                UPDATE players
                SET score = %s
                WHERE id = %s
                """,
                (
                    score,
                    player["id"]
                )
            )

            updated["score"] = score

            return updated


def perform_research(
    game_id: int,
    user_id: int
) -> Dict[str, Any]:

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM players
                WHERE game_id = %s
                  AND user_id = %s
                FOR UPDATE
                """,
                (
                    game_id,
                    user_id
                )
            )

            player = cur.fetchone()

            if not player:
                raise ValueError(
                    "NOT_PLAYER"
                )

            if not can_take_action(player):
                raise ValueError(
                    "NO_ACTIONS"
                )

            cost = ACTION_COSTS["research"]

            if player["money"] < cost:
                raise ValueError(
                    "NOT_ENOUGH_MONEY"
                )

            new_science = (
                player["science"] + 3
            )

            new_money = (
                player["money"] - cost
            )

            new_actions = (
                player["actions_left"] - 1
            )

            cur.execute(
                """
                UPDATE players
                SET
                    money = %s,
                    science = %s,
                    actions_left = %s
                WHERE id = %s
                RETURNING *
                """,
                (
                    new_money,
                    new_science,
                    new_actions,
                    player["id"]
                )
            )

            updated = cur.fetchone()

            score = calculate_score(
                updated
            )

            cur.execute(
                """
                UPDATE players
                SET score = %s
                WHERE id = %s
                """,
                (
                    score,
                    player["id"]
                )
            )

            updated["score"] = score

            return updated


def perform_trade(
    game_id: int,
    user_id: int
) -> Dict[str, Any]:

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM players
                WHERE game_id = %s
                  AND user_id = %s
                FOR UPDATE
                """,
                (
                    game_id,
                    user_id
                )
            )

            player = cur.fetchone()

            if not player:
                raise ValueError(
                    "NOT_PLAYER"
                )

            if not can_take_action(player):
                raise ValueError(
                    "NO_ACTIONS"
                )

            cost = ACTION_COSTS["trade"]

            if player["money"] < cost:
                raise ValueError(
                    "NOT_ENOUGH_MONEY"
                )

            # Trade consumes money but creates
            # additional cash immediately.
            profit = 300

            new_money = (
                player["money"]
                - cost
                + profit
            )

            new_stability = min(
                100,
                player["stability"] + 1
            )

            new_actions = (
                player["actions_left"] - 1
            )

            cur.execute(
                """
                UPDATE players
                SET
                    money = %s,
                    stability = %s,
                    actions_left = %s
                WHERE id = %s
                RETURNING *
                """,
                (
                    new_money,
                    new_stability,
                    new_actions,
                    player["id"]
                )
            )

            updated = cur.fetchone()

            score = calculate_score(
                updated
            )

            cur.execute(
                """
                UPDATE players
                SET score = %s
                WHERE id = %s
                """,
                (
                    score,
                    player["id"]
                )
            )

            updated["score"] = score

            return updated


def perform_diplomacy(
    game_id: int,
    user_id: int
) -> Dict[str, Any]:

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM players
                WHERE game_id = %s
                  AND user_id = %s
                FOR UPDATE
                """,
                (
                    game_id,
                    user_id
                )
            )

            player = cur.fetchone()

            if not player:
                raise ValueError(
                    "NOT_PLAYER"
                )

            if not can_take_action(player):
                raise ValueError(
                    "NO_ACTIONS"
                )

            cost = ACTION_COSTS["diplomacy"]

            if player["money"] < cost:
                raise ValueError(
                    "NOT_ENOUGH_MONEY"
                )

            new_money = (
                player["money"] - cost
            )

            new_stability = min(
                100,
                player["stability"] + 8
            )

            new_actions = (
                player["actions_left"] - 1
            )

            cur.execute(
                """
                UPDATE players
                SET
                    money = %s,
                    stability = %s,
                    actions_left = %s
                WHERE id = %s
                RETURNING *
                """,
                (
                    new_money,
                    new_stability,
                    new_actions,
                    player["id"]
                )
            )

            updated = cur.fetchone()

            score = calculate_score(
                updated
            )

            cur.execute(
                """
                UPDATE players
                SET score = %s
                WHERE id = %s
                """,
                (
                    score,
                    player["id"]
                )
            )

            updated["score"] = score

            return updated


# ============================================================
# TURN SYSTEM
# ============================================================

def end_turn(
    game_id: int,
    user_id: int
) -> Dict[str, Any]:

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM games
                WHERE id = %s
                FOR UPDATE
                """,
                (game_id,)
            )

            game = cur.fetchone()

            if not game:
                raise ValueError(
                    "GAME_NOT_FOUND"
                )

            if game["status"] != "running":
                raise ValueError(
                    "NOT_RUNNING"
                )

            cur.execute(
                """
                SELECT *
                FROM players
                WHERE game_id = %s
                ORDER BY id ASC
                """,
                (game_id,)
            )

            players = cur.fetchall()

            current_player = None

            for player in players:
                if player["id"] == game["current_player_id"]:
                    current_player = player
                    break

            if not current_player:
                raise ValueError(
                    "CURRENT_PLAYER_NOT_FOUND"
                )

            if current_player["user_id"] != user_id:
                raise ValueError(
                    "NOT_YOUR_TURN"
                )

            # -----------------------------------------------
            # END CURRENT PLAYER TURN
            # -----------------------------------------------

            income = (
                100
                + current_player["industry"] * 12
                + current_player["science"] * 5
            )

            stability_bonus = max(
                0,
                current_player["stability"] - 50
            )

            income += stability_bonus

            new_money = (
                current_player["money"]
                + income
            )

            new_population = min(
                200,
                current_player["population"]
                + max(
                    1,
                    current_player["population"] // 50
                )
            )

            cur.execute(
                """
                UPDATE players
                SET
                    money = %s,
                    population = %s,
                    actions_left = 3
                WHERE id = %s
                RETURNING *
                """,
                (
                    new_money,
                    new_population,
                    current_player["id"]
                )
            )

            updated_current = cur.fetchone()

            # -----------------------------------------------
            # DETERMINE NEXT PLAYER
            # -----------------------------------------------

            player_ids = [
                p["id"]
                for p in players
            ]

            try:
                current_index = player_ids.index(
                    current_player["id"]
                )
            except ValueError:
                current_index = 0

            next_index = (
                current_index + 1
            ) % len(player_ids)

            next_player = players[next_index]

            # -----------------------------------------------
            # A ROUND IS COMPLETED WHEN WE RETURN
            # TO THE FIRST PLAYER
            # -----------------------------------------------

            new_total_turn = game["total_turn"]

            if next_index == 0:
                new_total_turn += 1

            # -----------------------------------------------
            # GAME END
            # -----------------------------------------------

            if new_total_turn > 30:

                # Refresh all scores first.
                for player in players:

                    cur.execute(
                        """
                        SELECT *
                        FROM players
                        WHERE id = %s
                        """,
                        (player["id"],)
                    )

                    fresh = cur.fetchone()

                    score = calculate_score(
                        fresh
                    )

                    cur.execute(
                        """
                        UPDATE players
                        SET score = %s
                        WHERE id = %s
                        """,
                        (
                            score,
                            player["id"]
                        )
                    )

                cur.execute(
                    """
                    UPDATE games
                    SET
                        status = 'finished',
                        total_turn = %s,
                        current_player_id = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        new_total_turn,
                        game_id
                    )
                )

                return {
                    "game": cur.fetchone(),
                    "finished": True,
                    "income": income,
                    "next_player": None,
                }

            # -----------------------------------------------
            # NORMAL NEXT TURN
            # -----------------------------------------------

            cur.execute(
                """
                UPDATE games
                SET
                    total_turn = %s,
                    current_player_id = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (
                    new_total_turn,
                    next_player["id"],
                    game_id
                )
            )

            updated_game = cur.fetchone()

            return {
                "game": updated_game,
                "finished": False,
                "income": income,
                "next_player": next_player,
            }


# ============================================================
# TELEGRAM API
# ============================================================

def telegram_request(
    method: str,
    payload: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:

    if not BOT_TOKEN:
        logger.error(
            "BOT_TOKEN is missing."
        )
        return None

    url = (
        f"{TELEGRAM_API}/{method}"
    )

    data = json.dumps(
        payload or {}
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            req,
            timeout=30
        ) as response:

            raw = response.read().decode(
                "utf-8"
            )

            result = json.loads(raw)

            if not result.get("ok"):
                logger.error(
                    "Telegram API error: %s",
                    result
                )

            return result

    except urllib.error.HTTPError as exc:

        body = exc.read().decode(
            "utf-8",
            errors="replace"
        )

        logger.error(
            "Telegram HTTP error %s: %s",
            exc.code,
            body
        )

        return None

    except Exception:

        logger.exception(
            "Telegram request failed: %s",
            method
        )

        return None


def send_message(
    chat_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None
):

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    return telegram_request(
        "sendMessage",
        payload
    )


def edit_message(
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None
):

    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    return telegram_request(
        "editMessageText",
        payload
    )


def answer_callback(
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False
):

    payload = {
        "callback_query_id": callback_query_id,
        "show_alert": show_alert,
    }

    if text:
        payload["text"] = text

    return telegram_request(
        "answerCallbackQuery",
        payload
    )


# ============================================================
# TELEGRAM KEYBOARDS
# ============================================================

def main_keyboard(
    language: str
) -> Dict[str, Any]:

    text = TEXTS[language]

    return {
        "keyboard": [
            [
                {
                    "text": text["create_button"]
                },
                {
                    "text": text["join_button"]
                }
            ],
            [
                {
                    "text": text["my_game"]
                },
                {
                    "text": text["game_menu"]
                }
            ],
            [
                {
                    "text": text["help_button"]
                },
                {
                    "text": text["rules_button"]
                }
            ],
            [
                {
                    "text": text["language_button"]
                }
            ]
        ],
        "resize_keyboard": True
    }


def language_keyboard() -> Dict[str, Any]:

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


def game_keyboard(
    language: str
) -> Dict[str, Any]:

    text = TEXTS[language]

    return {
        "inline_keyboard": [
            [
                {
                    "text": text["choose_country"],
                    "callback_data": "game:country"
                }
            ],
            [
                {
                    "text": text["start_game"],
                    "callback_data": "game:start"
                }
            ],
            [
                {
                    "text": text["back"],
                    "callback_data": "game:back"
                }
            ]
        ]
    }


def running_keyboard(
    language: str
) -> Dict[str, Any]:

    text = TEXTS[language]

    # ============================================================
# TELEGRAM USER HELPERS
# ============================================================

def get_user_from_message(message: Dict[str, Any]) -> Dict[str, Any]:
    user = message.get("from", {})

    return {
        "id": int(user.get("id", 0)),
        "username": user.get("username"),
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
    }


def get_user_from_callback(
    callback: Dict[str, Any]
) -> Dict[str, Any]:

    user = callback.get("from", {})

    return {
        "id": int(user.get("id", 0)),
        "username": user.get("username"),
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
    }


def get_chat_id_from_message(
    message: Dict[str, Any]
) -> Optional[int]:

    chat = message.get("chat")

    if not chat:
        return None

    return int(chat.get("id"))


def get_chat_id_from_callback(
    callback: Dict[str, Any]
) -> Optional[int]:

    message = callback.get("message")

    if not message:
        return None

    chat = message.get("chat")

    if not chat:
        return None

    return int(chat.get("id"))


# ============================================================
# TEXT HELPERS
# ============================================================

def user_language(user_id: int) -> str:
    return get_language(user_id)


def status_for_user(
    user_id: int
) -> Optional[str]:

    game = get_user_game(user_id)

    if not game:
        return None

    language = user_language(user_id)

    return game_status_text(
        game,
        language
    )


def send_game_status(
    chat_id: int,
    game_id: int,
    language: str
):

    game = get_game_by_id(game_id)

    if not game:
        send_message(
            chat_id,
            TEXTS[language]["game_not_found"],
            main_keyboard(language)
        )
        return

    text = game_status_text(
        game,
        language
    )

    if game["status"] == "waiting":

        send_message(
            chat_id,
            text,
            game_keyboard(language)
        )

    elif game["status"] == "running":

        send_message(
            chat_id,
            text,
            running_keyboard(language)
        )

    else:

        send_message(
            chat_id,
            text,
            main_keyboard(language)
        )


def game_lobby_text(
    game_id: int,
    language: str
) -> str:

    game = get_game_by_id(game_id)

    if not game:
        return TEXTS[language]["game_not_found"]

    players = get_players(game_id)

    text = (
        f"<b>🎮 {TEXTS[language]['lobby']}</b>\n\n"
        f"🔑 <b>Code:</b> <code>{game['code']}</code>\n"
        f"👥 <b>Players:</b> {len(players)}/12\n\n"
    )

    for index, player in enumerate(players, start=1):

        name = (
            player.get("first_name")
            or player.get("username")
            or str(player["user_id"])
        )

        country = country_name(
            player["country"],
            language
        )

        if player["user_id"] == game["owner_id"]:
            name = f"👑 {name}"

        text += (
            f"{index}. {name}"
            f" — {country}\n"
        )

    text += (
        "\n"
        f"{TEXTS[language]['private_tip']}"
    )

    return text


# ============================================================
# START COMMAND
# ============================================================

def handle_start(
    message: Dict[str, Any]
):

    user = get_user_from_message(message)
    user_id = user["id"]

    chat_id = get_chat_id_from_message(
        message
    )

    if not chat_id:
        return

    language = user_language(
        user_id
    )

    # Private chat
    if message.get("chat", {}).get("type") == "private":

        send_message(
            chat_id,
            TEXTS[language]["welcome_private"],
            main_keyboard(language)
        )

        return

    # Group chat
    send_message(
        chat_id,
        TEXTS[language]["welcome"],
        main_keyboard(language)
    )


# ============================================================
# HELP / RULES
# ============================================================

def handle_help(
    chat_id: int,
    user_id: int
):

    language = user_language(
        user_id
    )

    send_message(
        chat_id,
        TEXTS[language]["help"],
        main_keyboard(language)
    )


def handle_rules(
    chat_id: int,
    user_id: int
):

    language = user_language(
        user_id
    )

    send_message(
        chat_id,
        TEXTS[language]["rules"],
        main_keyboard(language)
    )


# ============================================================
# CREATE GAME
# ============================================================

def handle_create_game(
    message: Dict[str, Any]
):

    user = get_user_from_message(message)
    user_id = user["id"]

    chat_id = get_chat_id_from_message(
        message
    )

    if not chat_id:
        return

    language = user_language(
        user_id
    )

    existing = get_user_game(
        user_id
    )

    if existing:

        send_message(
            chat_id,
            TEXTS[language]["game_already"],
            game_keyboard(language)
            if existing["status"] == "waiting"
            else running_keyboard(language)
        )

        return

    try:

        game = create_game(
            owner_id=user_id,
            chat_id=chat_id,
            username=user.get("username"),
            first_name=user.get("first_name", "")
        )

        text = (
            f"<b>🎮 {TEXTS[language]['game_created']}</b>\n\n"
            f"🔑 Code: <code>{game['code']}</code>\n\n"
            f"{game_lobby_text(game['id'], language)}"
        )

        send_message(
            chat_id,
            text,
            game_keyboard(language)
        )

    except Exception:

        logger.exception(
            "Could not create game."
        )

        send_message(
            chat_id,
            "❌ Database error. Please try again.",
            main_keyboard(language)
        )


# ============================================================
# JOIN GAME
# ============================================================

def handle_join_request(
    chat_id: int,
    user_id: int
):

    language = user_language(
        user_id
    )

    set_pending_action(
        user_id,
        "join_game"
    )

    send_message(
        chat_id,
        TEXTS[language]["join_enter_code"],
        main_keyboard(language)
    )


def handle_join_code(
    message: Dict[str, Any],
    code: str
):

    user = get_user_from_message(
        message
    )

    user_id = user["id"]

    chat_id = get_chat_id_from_message(
        message
    )

    if not chat_id:
        return

    language = user_language(
        user_id
    )

    code = code.strip().upper()

    game = get_game_by_code(
        code
    )

    if not game:

        send_message(
            chat_id,
            TEXTS[language]["game_not_found"],
            main_keyboard(language)
        )

        return

    try:

        player = add_player_to_game(
            game_id=game["id"],
            user_id=user_id,
            chat_id=chat_id,
            username=user.get("username"),
            first_name=user.get("first_name", "")
        )

        set_pending_action(
            user_id,
            None
        )

        send_message(
            chat_id,
            TEXTS[language]["joined"],
            game_keyboard(language)
        )

        # Update lobby in the group.
        send_message(
            game["chat_id"],
            game_lobby_text(
                game["id"],
                language
            ),
            game_keyboard(language)
        )

    except ValueError as exc:

        error = str(exc)

        if error == "GAME_NOT_WAITING":
            key = "game_already"

        elif error == "GAME_FULL":
            key = "game_already"

        elif error == "ALREADY_IN_GAME":
            key = "already_in_game"

        else:
            key = "game_not_found"

        send_message(
            chat_id,
            TEXTS[language][key],
            main_keyboard(language)
        )

    except Exception:

        logger.exception(
            "Join game failed."
        )

        send_message(
            chat_id,
            "❌ Database error. Please try again.",
            main_keyboard(language)
        )


# ============================================================
# GAME STATUS
# ============================================================

def handle_my_game(
    chat_id: int,
    user_id: int
):

    language = user_language(
        user_id
    )

    game = get_user_game(
        user_id
    )

    if not game:

        send_message(
            chat_id,
            TEXTS[language]["no_game"],
            main_keyboard(language)
        )

        return

    if game["status"] == "waiting":

        send_message(
            chat_id,
            game_lobby_text(
                game["id"],
                language
            ),
            game_keyboard(language)
        )

    elif game["status"] == "running":

        send_message(
            chat_id,
            game_status_text(
                game,
                language
            ),
            running_keyboard(language)
        )

    else:

        send_message(
            chat_id,
            final_results_text(
                game["id"],
                language
            ),
            main_keyboard(language)
        )


# ============================================================
# COUNTRY SELECTION
# ============================================================

def handle_country_menu(
    chat_id: int,
    user_id: int,
    message_id: Optional[int] = None
):

    language = user_language(
        user_id
    )

    game = get_user_game(
        user_id
    )

    if not game:

        send_message(
            chat_id,
            TEXTS[language]["no_game"],
            main_keyboard(language)
        )

        return

    if game["status"] != "waiting":

        send_message(
            chat_id,
            TEXTS[language]["not_running"],
            main_keyboard(language)
        )

        return

    player = get_player(
        game["id"],
        user_id
    )

    if not player:

        send_message(
            chat_id,
            TEXTS[language]["need_group"],
            main_keyboard(language)
        )

        return

    keyboard = country_inline_keyboard(
        game["id"],
        language
    )

    text = (
        f"<b>🌍 {TEXTS[language]['choose_country']}</b>\n\n"
        f"{TEXTS[language]['country_open']}"
    )

    if message_id:

        edit_message(
            chat_id,
            message_id,
            text,
            keyboard
        )

    else:

        send_message(
            chat_id,
            text,
            keyboard
        )


def handle_country_choice(
    chat_id: int,
    user_id: int,
    country: str,
    message_id: Optional[int] = None
):

    language = user_language(
        user_id
    )

    game = get_user_game(
        user_id
    )

    if not game:

        answer = TEXTS[language]["no_game"]

        send_message(
            chat_id,
            answer,
            main_keyboard(language)
        )

        return

    try:

        player = set_player_country(
            game["id"],
            user_id,
            country
        )

        country_title = country_name(
            country,
            language
        )

        text = (
            f"✅ <b>{TEXTS[language]['country_saved']}</b>\n\n"
            f"🌍 {country_title}\n"
            f"🏭 Industry: {player['industry']}\n"
            f"🔬 Science: {player['science']}\n"
            f"🛡 Stability: {player['stability']}\n"
            f"👥 Population: {player['population']}"
        )

        if message_id:

            edit_message(
                chat_id,
                message_id,
                text,
                game_keyboard(language)
            )

        else:

            send_message(
                chat_id,
                text,
                game_keyboard(language)
            )

        # Update lobby.
        send_message(
            game["chat_id"],
            game_lobby_text(
                game["id"],
                language
            ),
            game_keyboard(language)
        )

    except ValueError as exc:

        error = str(exc)

        if error == "COUNTRY_TAKEN":
            key = "country_taken"

        elif error == "INVALID_COUNTRY":
            key = "country_open"

        else:
            key = "game_not_found"

        answer = TEXTS[language][key]

        send_message(
            chat_id,
            answer,
            country_inline_keyboard(
                game["id"],
                language
            )
        )

    except Exception:

        logger.exception(
            "Country selection failed."
        )

        send_message(
            chat_id,
            "❌ Database error.",
            main_keyboard(language)
        )


# ============================================================
# START GAME
# ============================================================

def handle_start_game(
    chat_id: int,
    user_id: int
):

    language = user_language(
        user_id
    )

    game = get_user_game(
        user_id
    )

    if not game:

        send_message(
            chat_id,
            TEXTS[language]["no_game"],
            main_keyboard(language)
        )

        return

    try:

        started = start_game(
            game["id"],
            user_id
        )

        players = get_players(
            started["id"]
        )

        current = get_player_by_id(
            started["current_player_id"]
        )

        current_name = (
            current.get("first_name")
            or current.get("username")
            or str(current["user_id"])
        )

        text = (
            f"🚀 <b>{TEXTS[language]['game_started']}</b>\n\n"
            f"👥 Players: {len(players)}\n"
            f"🔄 Turn: {started['total_turn']}\n\n"
            f"🎯 Current player: <b>{current_name}</b>"
        )

        send_message(
            chat_id,
            text,
            running_keyboard(language)
        )

    except ValueError as exc:

        error = str(exc)

        if error == "NOT_OWNER":
            key = "not_owner"

        elif error == "NOT_ENOUGH_PLAYERS":
            key = "need_players"

        elif error == "COUNTRY_NOT_SELECTED":
            key = "need_country"

        else:
            key = "game_already"

        send_message(
            chat_id,
            TEXTS[language][key],
            game_keyboard(language)
        )

    except Exception:

        logger.exception(
            "Start game failed."
        )

        send_message(
            chat_id,
            "❌ Database error.",
            main_keyboard(language)
        )


# ============================================================
# ACTION HANDLER
# ============================================================

def handle_action(
    chat_id: int,
    user_id: int,
    action: str
):

    language = user_language(
        user_id
    )

    game = get_user_game(
        user_id
    )

    if not game:

        send_message(
            chat_id,
            TEXTS[language]["no_game"],
            main_keyboard(language)
        )

        return

    if game["status"] != "running":

        send_message(
            chat_id,
            TEXTS[language]["not_running"],
            main_keyboard(language)
        )

        return

    try:

        # Make sure it is actually this player's turn.
        if game["current_player_id"]:

            current = get_player_by_id(
                game["current_player_id"]
            )

            if (
                not current
                or current["user_id"] != user_id
            ):

                send_message(
                    chat_id,
                    TEXTS[language]["not_your_turn"],
                    running_keyboard(language)
                )

                return

        if action == "build":

            player = perform_build(
                game["id"],
                user_id
            )

            result = (
                f"🏭 <b>{TEXTS[language]['build']}</b>\n\n"
                f"💰 Money: {player['money']}\n"
                f"🏭 Industry: {player['industry']}\n"
                f"⚡ Actions: {player['actions_left']}"
            )

        elif action == "research":

            player = perform_research(
                game["id"],
                user_id
            )

            result = (
                f"🔬 <b>{TEXTS[language]['research']}</b>\n\n"
                f"💰 Money: {player['money']}\n"
                f"🔬 Science: {player['science']}\n"
                f"⚡ Actions: {player['actions_left']}"
            )

        elif action == "trade":

            player = perform_trade(
                game["id"],
                user_id
            )

            result = (
                f"💱 <b>{TEXTS[language]['trade']}</b>\n\n"
                f"💰 Money: {player['money']}\n"
                f"🛡 Stability: {player['stability']}\n"
                f"⚡ Actions: {player['actions_left']}"
            )

        elif action == "diplomacy":

            player = perform_diplomacy(
                game["id"],
                user_id
            )

            result = (
                f"🤝 <b>{TEXTS[language]['diplomacy']}</b>\n\n"
                f"💰 Money: {player['money']}\n"
                f"🛡 Stability: {player['stability']}\n"
                f"⚡ Actions: {player['actions_left']}"
            )

        elif action == "end_turn":

            result_data = end_turn(
                game["id"],
                user_id
            )

            if result_data["finished"]:

                send_message(
                    chat_id,
                    final_results_text(
                        game["id"],
                        language
                    ),
                    main_keyboard(language)
                )

                return

            next_player = (
                result_data["next_player"]
            )

            next_name = (
                next_player.get("first_name")
                or next_player.get("username")
                or str(next_player["user_id"])
            )

            result = (
                f"🔄 <b>{TEXTS[language]['turn_ended']}</b>\n\n"
                f"💰 Income: +{result_data['income']}\n"
                f"💰 New balance: "
                f"{get_player(game['id'], user_id)['money']}\n\n"
                f"🎯 Next player: <b>{next_name}</b>"
            )

        else:

            return

        send_message(
            chat_id,
            result,
            running_keyboard(language)
        )

    except ValueError as exc:

        error = str(exc)

        if error == "NOT_ENOUGH_MONEY":
            key = "not_enough_money"

        elif error == "NO_ACTIONS":
            key = "not_enough_actions"

        elif error == "NOT_YOUR_TURN":
            key = "not_your_turn"

        elif error == "NOT_RUNNING":
            key = "not_running"

        elif error == "NOT_PLAYER":
            key = "no_game"

        else:
            key = "unknown"

        send_message(
            chat_id,
            TEXTS[language][key],
            running_keyboard(language)
        )

    except Exception:

        logger.exception(
            "Action failed."
        )

        send_message(
            chat_id,
            "❌ Database error.",
            running_keyboard(language)
        )


# ============================================
# ============================================================
# FLASK ROUTES
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "service": "strategy-game"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok"
    })


@app.route("/telegram", methods=["POST"])
def telegram_webhook():

    if WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")

        if secret != WEBHOOK_SECRET:
            return jsonify({
                "ok": False,
                "error": "unauthorized"
            }), 403

    update = request.get_json(silent=True)

    if not update:
        return jsonify({
            "ok": False,
            "error": "empty_update"
        }), 400

    try:
        process_update(update)

    except Exception:
        logger.exception("Error while processing Telegram update")

    return jsonify({
        "ok": True
    })


@app.route("/set-webhook", methods=["GET", "POST"])
def set_webhook():

    if not BOT_TOKEN:
        return jsonify({
            "ok": False,
            "error": "BOT_TOKEN is missing"
        }), 500

    if not WEBHOOK_URL:
        return jsonify({
            "ok": False,
            "error": "WEBHOOK_URL is missing"
        }), 500

    webhook_url = f"{WEBHOOK_URL}/telegram"

    result = telegram_request(
        "setWebhook",
        {
            "url": webhook_url,
            "secret_token": WEBHOOK_SECRET
        }
    )

    return jsonify(result)


@app.route("/webhook-info", methods=["GET"])
def webhook_info():

    result = telegram_request("getWebhookInfo")

    return jsonify(result)


@app.route("/bot-info", methods=["GET"])
def bot_info():

    result = telegram_request("getMe")

    return jsonify(result)
    
# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "ok": False,
        "error": "not_found"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    logger.exception("Internal server error")

    return jsonify({
        "ok": False,
        "error": "internal_server_error"
    }), 500


# ============================================================
# STARTUP
# ============================================================

try:
    init_db()
    logger.info("Database initialized successfully")

except Exception:
    logger.exception("Database initialization failed")


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=PORT
    )
