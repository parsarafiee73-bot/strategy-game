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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("strategy-game")

# ============================================================
# TRANSLATIONS
# ============================================================

TEXTS = {
    "fa": {
        "welcome": "سلام {name}!\n\nبه بازی استراتژی چندنفره خوش آمدی.\n\nاز دکمه‌های پایین برای ساخت یا پیوستن به بازی استفاده کن.",
        "welcome_private": "سلام {name}!\n\nبازی را می‌توانی از اینجا مدیریت کنی و بعد در گروه وارد لابی شوی.",
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
        "need_group": "این گزینه را بهتر است داخل گروهی که بازی در آن برگزار می‌شود اجرا کنی.",
        "game_created": "بازی ساخته شد ✅\n\nکد بازی: <code>{code}</code>\nسازنده: {name}\n\nکد را برای بقیه بازیکن‌ها بفرست.",
        "game_already": "تو همین الان در یک بازی فعال هستی: <code>{code}</code>.",
        "join_enter_code": "کد ۶ حرفی بازی را بفرست.",
        "invalid_code": "کد باید دقیقاً ۶ حرف یا عدد باشد.",
        "game_not_found": "چنین بازی‌ای پیدا نشد یا بازی دیگر در وضعیت انتظار نیست.",
        "joined": "وارد بازی شدی ✅\n\n{game}",
        "already_in_game": "تو از قبل داخل این بازی هستی.",
        "country_open": "یک کشور آزاد انتخاب کن:",
        "country_taken": "این کشور قبلاً توسط بازیکن دیگری انتخاب شده است.",
        "country_saved": "کشور {country} برای تو ثبت شد ✅",
        "need_country": "قبل از شروع، همه بازیکن‌ها باید کشورشان را انتخاب کنند.",
        "not_owner": "فقط سازنده بازی می‌تواند آن را شروع کند.",
        "need_players": "برای شروع حداقل ۲ بازیکن لازم است.",
        "game_started": "بازی شروع شد 🚀\n\nنوبت اول: {player}",
        "not_your_turn": "الان نوبت تو نیست. نوبت: {player}",
        "not_running": "بازی در حال اجرا نیست.",
        "action_done": "اقدام انجام شد ✅\n\n{summary}",
        "not_enough_money": "پول کافی نیست. موجودی فعلی: {money}",
        "not_enough_actions": "اقدام‌های این نوبت تمام شده‌اند. نوبت را تمام کن.",
        "turn_ended": "نوبت {turn} تمام شد. نوبت بعد: {player}",
        "game_finished": "بازی تمام شد 🏁\n\n{results}",
        "no_game": "فعلاً در هیچ بازی فعالی نیستی.",
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
        "private_tip": "برای هماهنگی بهتر، این پیام را داخل گروه بازی اجرا کن.",
        "admin_only": "این مسیر مدیریتی است.",
        "migrated": "Database migration completed.",
    },
    "en": {
        "welcome": "Hi {name}!\n\nWelcome to the multiplayer strategy game.\n\nUse the buttons below to create or join a game.",
        "welcome_private": "Hi {name}!\n\nYou can manage the game here and then play in your group.",
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
        "unknown": "I didn't understand that. Please use the buttons.",
        "need_group": "This option works best inside the group where the game will be played.",
        "game_created": "Game created ✅\n\nGame code: <code>{code}</code>\nOwner: {name}\n\nSend the code to the other players.",
        "game_already": "You are already in an active game: <code>{code}</code>.",
        "join_enter_code": "Send the 6-character game code.",
        "invalid_code": "The code must be exactly 6 letters or digits.",
        "game_not_found": "That game was not found or is no longer waiting.",
        "joined": "You joined the game ✅\n\n{game}",
        "already_in_game": "You are already in this game.",
        "country_open": "Choose an available country:",
        "country_taken": "That country has already been chosen.",
        "country_saved": "Country {country} saved ✅",
        "need_country": "Everyone must choose a country before the game can start.",
        "not_owner": "Only the game owner can start the game.",
        "need_players": "At least 2 players are required.",
        "game_started": "Game started 🚀\n\nFirst turn: {player}",
        "not_your_turn": "It is not your turn. Current turn: {player}",
        "not_running": "The game is not running.",
        "action_done": "Action completed ✅\n\n{summary}",
        "not_enough_money": "Not enough money. Current balance: {money}",
        "not_enough_actions": "You have no actions left. End your turn.",
        "turn_ended": "Turn {turn} ended. Next: {player}",
        "game_finished": "Game finished 🏁\n\n{results}",
        "no_game": "You are not in an active game.",
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
        "private_tip": "For coordination, run this message inside your game group.",
        "admin_only": "This is an administrative route.",
        "migrated": "Database migration completed.",
    },
}

COUNTRIES = {
    "IR": {"fa": "ایران", "en": "Iran", "industry": 11, "science": 4, "stability": 68, "population": 85},
    "US": {"fa": "ایالات متحده", "en": "United States", "industry": 18, "science": 10, "stability": 72, "population": 90},
    "CN": {"fa": "چین", "en": "China", "industry": 17, "science": 8, "stability": 74, "population": 95},
    "DE": {"fa": "آلمان", "en": "Germany", "industry": 16, "science": 9, "stability": 78, "population": 55},
    "FR": {"fa": "فرانسه", "en": "France", "industry": 14, "science": 8, "stability": 76, "population": 52},
    "TR": {"fa": "ترکیه", "en": "Türkiye", "industry": 12, "science": 5, "stability": 66, "population": 60},
    "JP": {"fa": "ژاپن", "en": "Japan", "industry": 15, "science": 10, "stability": 82, "population": 50},
    "IN": {"fa": "هند", "en": "India", "industry": 13, "science": 7, "stability": 67, "population": 100},
    "BR": {"fa": "برزیل", "en": "Brazil", "industry": 10, "science": 4, "stability": 65, "population": 72},
    "CA": {"fa": "کانادا", "en": "Canada", "industry": 11, "science": 8, "stability": 80, "population": 38},
    "EG": {"fa": "مصر", "en": "Egypt", "industry": 9, "science": 3, "stability": 63, "population": 68},
    "KR": {"fa": "کره جنوبی", "en": "South Korea", "industry": 15, "science": 10, "stability": 79, "population": 48},
}

# ============================================================
# HELPERS
# ============================================================


def t(user_id: int, key: str, **kwargs: Any) -> str:
    language = get_language(user_id)
    value = TEXTS.get(language, TEXTS["en"]).get(key, key)
    return value.format(**kwargs)


def country_name(code: Optional[str], language: str = "en") -> str:
    if not code or code not in COUNTRIES:
        return TEXTS.get(language, TEXTS["en"])["no_country"]
    return COUNTRIES[code][language]


def display_name(user: Dict[str, Any]) -> str:
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    username = (user.get("username") or "").strip()
    full = " ".join(x for x in (first, last) if x).strip()
    if full:
        return full
    if username:
        return f"@{username}"
    return str(user.get("id", "Player"))


@contextmanager
def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing")
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def generate_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ============================================================
# DATABASE / MIGRATION
# ============================================================


def column_exists(cur, table: str, column: str) -> bool:
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


def add_column_if_missing(cur, table: str, column: str, definition: str):
    if not column_exists(cur, table, column):
        cur.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}')
        logger.info("Added missing column %s.%s", table, column)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            # New/full schema. IF NOT EXISTS also keeps existing deployments alive.
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
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
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

            # Automatic migration for the older schema that caused owner_id errors.
            add_column_if_missing(cur, "user_preferences", "pending_action", "TEXT")
            add_column_if_missing(cur, "user_preferences", "updated_at", "TIMESTAMP NOT NULL DEFAULT NOW()")

            add_column_if_missing(cur, "games", "owner_id", "BIGINT")
            add_column_if_missing(cur, "games", "total_turn", "INTEGER NOT NULL DEFAULT 0")
            add_column_if_missing(cur, "games", "current_player_id", "BIGINT")
            add_column_if_missing(cur, "games", "created_at", "TIMESTAMP NOT NULL DEFAULT NOW()")
            add_column_if_missing(cur, "games", "updated_at", "TIMESTAMP NOT NULL DEFAULT NOW()")

            add_column_if_missing(cur, "players", "username", "TEXT")
            add_column_if_missing(cur, "players", "first_name", "TEXT")
            add_column_if_missing(cur, "players", "chat_id", "BIGINT")
            add_column_if_missing(cur, "players", "country", "VARCHAR(2)")
            add_column_if_missing(cur, "players", "money", "INTEGER NOT NULL DEFAULT 1000")
            add_column_if_missing(cur, "players", "industry", "INTEGER NOT NULL DEFAULT 10")
            add_column_if_missing(cur, "players", "science", "INTEGER NOT NULL DEFAULT 0")
            add_column_if_missing(cur, "players", "stability", "INTEGER NOT NULL DEFAULT 70")
            add_column_if_missing(cur, "players", "population", "INTEGER NOT NULL DEFAULT 50")
            add_column_if_missing(cur, "players", "actions_left", "INTEGER NOT NULL DEFAULT 3")
            add_column_if_missing(cur, "players", "score", "INTEGER NOT NULL DEFAULT 0")
            add_column_if_missing(cur, "players", "joined_at", "TIMESTAMP NOT NULL DEFAULT NOW()")

            # Repair owner_id for legacy games where a player row already exists.
            cur.execute(
                """
                UPDATE games g
                SET owner_id = x.user_id
                FROM (
                    SELECT DISTINCT ON (game_id) game_id, user_id
                    FROM players
                    ORDER BY game_id, id
                ) x
                WHERE g.id = x.game_id
                  AND g.owner_id IS NULL
                """
            )

            cur.execute("CREATE INDEX IF NOT EXISTS idx_games_status ON games(status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_players_game ON players(game_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_players_user ON players(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_games_owner ON games(owner_id)")

    logger.info("Database is ready")


# ============================================================
# USER SETTINGS
# ============================================================


def get_language(user_id: int) -> str:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT language FROM user_preferences WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                return row["language"] if row and row.get("language") in TEXTS else "fa"
    except Exception:
        logger.exception("Failed to read language")
        return "fa"


def set_language(user_id: int, language: str):
    if language not in TEXTS:
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_preferences (user_id, language, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET language = EXCLUDED.language,
                              updated_at = NOW()
                """,
                (user_id, language),
            )


def get_pending_action(user_id: int) -> Optional[str]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pending_action FROM user_preferences WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            return row["pending_action"] if row else None


def set_pending_action(user_id: int, action: Optional[str]):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_preferences (user_id, language, pending_action, updated_at)
                VALUES (%s, COALESCE((SELECT language FROM user_preferences WHERE user_id = %s), 'fa'), %s, NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET pending_action = EXCLUDED.pending_action,
                              updated_at = NOW()
                """,
                (user_id, user_id, action),
            )


# ============================================================
# GAME DATABASE
# ============================================================


def get_game_by_code(code: str) -> Optional[Dict[str, Any]]:
