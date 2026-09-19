import os
import json
import string
import random
import logging
from datetime import datetime

from flask import Flask, request, jsonify
import requests
import psycopg
from psycopg.rows import dict_row

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("geostrategy")

# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
PORT = int(os.environ.get("PORT", "10000"))

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}/" if BOT_TOKEN else ""

if not BOT_TOKEN:
    logger.warning(
        "BOT_TOKEN is not set. Telegram calls will fail until it is configured."
    )

if not DATABASE_URL:
    logger.warning(
        "DATABASE_URL is not set. Database calls will fail until it is configured."
    )

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Languages / translations
# ---------------------------------------------------------------------------

LANGS = ("fa", "en")

TEXT = {
    "fa": {
        "language_name": "فارسی",
        "choose_language": "🌐 زبان خود را انتخاب کنید:",
        "language_saved": "✅ زبان شما روی فارسی تنظیم شد.",
        "welcome": (
            "🌍 <b>بازی استراتژی ژئوپلیتیک</b>\n\n"
            "به رهبر بازی خوش آمدید. کشور خود را بسازید، تحقیق کنید و در یک بازی نوبتی رقابت کنید.\n\n"
            "برای دیدن دستورات /help را بزنید یا برای ساخت بازی جدید /newgame را اجرا کنید."
        ),
        "available_commands": (
            "<b>دستورات موجود</b>\n\n"
            "/newgame - ساخت بازی جدید در این چت\n"
            "/join - ورود به بازی فعال\n"
            "/startgame - شروع انتخاب کشور توسط میزبان\n"
            "/menu - باز کردن منوی اصلی\n"
            "/status - مشاهده وضعیت کشور\n"
            "/world - مشاهده وضعیت جهان\n"
            "/leaderboard - مشاهده جدول امتیازات\n"
            "/attack - عملیات زمینی\n"
            "/missile - حمله انتزاعی\n"
            "/turn - مشاهده وضعیت نوبت\n"
            "/help - نمایش همین راهنما"
        ),
        "newgame_exists": (
            "یک بازی در حال اجراست (کد: <b>{code}</b>). برای ورود /join را بزنید."
        ),
        "newgame_created": (
            "🎮 بازی جدید ساخته شد! کد: <b>{code}</b>\n\n"
            "بازیکنان دیگر برای ورود /join را بزنند. وقتی آماده بودید، میزبان /startgame را اجرا کند."
        ),
        "newgame_error": "⚠️ هنگام ساخت بازی خطایی رخ داد. دوباره تلاش کنید.",
        "no_active_game": (
            "بازی فعالی در این چت وجود ندارد. ابتدا /newgame را بزنید."
        ),
        "already_started_join": (
            "این بازی شروع شده و دیگر امکان ورود وجود ندارد."
        ),
        "already_joined": "شما قبلاً وارد این بازی شده‌اید.",
        "player_joined": "✅ {name} وارد بازی شد!",
        "join_error": "⚠️ هنگام ورود به بازی خطایی رخ داد.",
        "host_only": "فقط میزبان می‌تواند بازی را شروع کند.",
        "game_already_started": "این بازی قبلاً شروع شده است.",
        "country_selection_started": (
            "🗺️ انتخاب کشور شروع شد! هر بازیکن روی یک کشور بزند تا آن را انتخاب کند."
        ),
        "choose_country": "کشور خود را انتخاب کنید:",
        "must_join": "ابتدا باید با /join وارد بازی شوید.",
        "already_have_country": "شما قبلاً یک کشور انتخاب کرده‌اید.",
        "country_missing": "این کشور وجود ندارد.",
        "country_taken": "این کشور قبلاً انتخاب شده است.",
        "country_selected": "✅ شما <b>{country}</b> را انتخاب کردید!",
        "selection_error": "⚠️ هنگام انتخاب کشور خطایی رخ داد.",
        "all_selected": (
            "✅ همه بازیکنان کشور خود را انتخاب کرده‌اند. بازی فعال شد!"
        ),
        "unknown_command": (
            "دستور شناخته نشد. برای دیدن دستورات /help را بزن."
        ),
        "game_menu": "🎮 <b>منوی بازی</b>",
        "back_to_menu": "⬅️ بازگشت به منو",
        "settings": "⚙️ تنظیمات",
        "change_language": "🌐 تغییر زبان",
        "language_current": "زبان فعلی: فارسی",
        "country_status": "📊 وضعیت کشور",
        "world_status": "🌍 وضعیت جهان",
        "buildings": "🏗️ ساختمان‌ها",
        "research": "🔬 تحقیقات",
        "ground_operations": "⚔️ عملیات زمینی",
        "abstract_strike": "🚀 حمله انتزاعی",
        "leaderboard": "🏆 جدول امتیازات",
        "end_turn": "✅ پایان نوبت",
        "not_active": "این گزینه در نسخه فعلی فعال نیست.",
    },
    "en": {
        "language_name": "English",
        "choose_language": "🌐 Choose your language:",
        "language_saved": "✅ Your language is now set to English.",
        "welcome": (
            "🌍 <b>Geopolitical Strategy</b>\n\n"
            "Welcome, leader. Build your nation, research technology, and compete in a turn-based strategy game.\n\n"
            "Use /help to see available commands, or /newgame to start a new game."
        ),
        "available_commands": (
            "<b>Available Commands</b>\n\n"
            "/newgame - Create a new game in this chat\n"
            "/join - Join the active game\n"
            "/startgame - Host starts country selection\n"
            "/menu - Open the main game menu\n"
            "/status - View your country status\n"
            "/world - View world status\n"
            "/leaderboard - View the leaderboard\n"
            "/attack - Launch a ground operation\n"
            "/missile - Launch an abstract strike\n"
            "/turn - View turn/ready status\n"
            "/help - Show this message"
        ),
        "newgame_exists": (
            "A game is already in progress (code: <b>{code}</b>). Use /join to join it."
        ),
        "newgame_created": (
            "🎮 New game created! Code: <b>{code}</b>\n\n"
            "Other players should use /join to enter. When ready, the host can use /startgame."
        ),
        "newgame_error": (
            "⚠️ Something went wrong creating the game. Please try again."
        ),
        "no_active_game": (
            "No active game in this chat. Use /newgame to create one."
        ),
        "already_started_join": (
            "This game has already started, so new players can no longer join."
        ),
        "already_joined": "You have already joined this game.",
        "player_joined": "✅ {name} joined the game!",
        "join_error": "⚠️ Something went wrong joining the game.",
        "host_only": "Only the host can start the game.",
        "game_already_started": "The game has already started.",
        "country_selection_started": (
            "🗺️ Country selection has begun! Each player, tap a country to claim it."
        ),
        "choose_country": "Choose your country:",
        "must_join": "You must use /join before choosing a country.",
        "already_have_country": "You have already selected a country.",
        "country_missing": "That country does not exist.",
        "country_taken": "That country has already been selected.",
        "country_selected": "✅ You selected <b>{country}</b>!",
        "selection_error": (
            "⚠️ An error occurred while selecting the country."
        ),
        "all_selected": (
            "✅ All players have selected a country. The game is now active!"
        ),
        "unknown_command": (
            "Unknown command. Use /help to see available commands."
        ),
        "game_menu": "🎮 <b>Game Menu</b>",
        "back_to_menu": "⬅️ Back to Menu",
        "settings": "⚙️ Settings",
        "change_language": "🌐 Change Language",
        "language_current": "Current language: English",
        "country_status": "📊 Country Status",
        "world_status": "🌍 World Status",
        "buildings": "🏗️ Buildings",
        "research": "🔬 Research",
        "ground_operations": "⚔️ Ground Operations",
        "abstract_strike": "🚀 Abstract Strike",
        "leaderboard": "🏆 Leaderboard",
        "end_turn": "✅ End Turn",
        "not_active": "This option is not active in the current version.",
    },
}

# ---------------------------------------------------------------------------
# Countries
# ---------------------------------------------------------------------------

COUNTRIES = {
    "IR": {
        "name": {"fa": "ایران", "en": "Iran"},
        "flag": "🇮🇷",
        "money": 1000,
        "food": 500,
        "steel": 300,
        "oil": 800,
        "population": 1000,
        "army": 200,
    },
    "TR": {
        "name": {"fa": "ترکیه", "en": "Turkey"},
        "flag": "🇹🇷",
        "money": 1200,
        "food": 600,
        "steel": 350,
        "oil": 200,
        "population": 1100,
        "army": 220,
    },
    "RU": {
        "name": {"fa": "روسیه", "en": "Russia"},
        "flag": "🇷🇺",
        "money": 1500,
        "food": 700,
        "steel": 600,
        "oil": 1500,
        "population": 2000,
        "army": 500,
    },
    "CN": {
        "name": {"fa": "چین", "en": "China"},
        "flag": "🇨🇳",
        "money": 2000,
        "food": 1000,
        "steel": 800,
        "oil": 400,
        "population": 3000,
        "army": 600,
    },
    "IN": {
        "name": {"fa": "هند", "en": "India"},
        "flag": "🇮🇳",
        "money": 1300,
        "food": 900,
        "steel": 400,
        "oil": 150,
        "population": 2500,
        "army": 400,
    },
    "DE": {
        "name": {"fa": "آلمان", "en": "Germany"},
        "flag": "🇩🇪",
        "money": 1800,
        "food": 500,
        "steel": 700,
        "oil": 100,
        "population": 900,
        "army": 300,
    },
    "FR": {
        "name": {"fa": "فرانسه", "en": "France"},
        "flag": "🇫🇷",
        "money": 1600,
        "food": 550,
        "steel": 500,
        "oil": 120,
        "population": 800,
        "army": 280,
    },
    "GB": {
        "name": {"fa": "بریتانیا", "en": "United Kingdom"},
        "flag": "🇬🇧",
        "money": 1700,
        "food": 450,
        "steel": 450,
        "oil": 150,
        "population": 750,
        "army": 260,
    },
    "JP": {
        "name": {"fa": "ژاپن", "en": "Japan"},
        "flag": "🇯🇵",
        "money": 1900,
        "food": 400,
        "steel": 650,
        "oil": 50,
        "population": 1300,
        "army": 320,
    },
    "US": {
        "name": {"fa": "ایالات متحده", "en": "United States"},
        "flag": "🇺🇸",
        "money": 2500,
        "food": 1200,
        "steel": 900,
        "oil": 700,
        "population": 3500,
        "army": 700,
    },
    "BR": {
        "name": {"fa": "برزیل", "en": "Brazil"},
        "flag": "🇧🇷",
        "money": 1100,
        "food": 800,
        "steel": 300,
        "oil": 300,
        "population": 2200,
        "army": 250,
    },
    "EG": {
        "name": {"fa": "مصر", "en": "Egypt"},
        "flag": "🇪🇬",
        "money": 900,
        "food": 400,
        "steel": 200,
        "oil": 150,
        "population": 1100,
        "army": 230,
    },
}

# ---------------------------------------------------------------------------
# Buildings
# ---------------------------------------------------------------------------

BUILDINGS = {
    "factory": {
        "label": {"fa": "کارخانه", "en": "Factory"},
        "cost": {"money": 300, "steel": 100},
        "desc": {
            "fa": "+۵۰ فولاد در هر نوبت برای هر سطح",
            "en": "+50 steel/turn per level",
        },
    },
    "farm": {
        "label": {"fa": "مزرعه", "en": "Farm"},
        "cost": {"money": 200, "steel": 50},
        "desc": {
            "fa": "+۸۰ غذا در هر نوبت برای هر سطح",
            "en": "+80 food/turn per level",
        },
    },
    "refinery": {
        "label": {"fa": "پالایشگاه نفت", "en": "Oil Refinery"},
        "cost": {"money": 350, "steel": 150},
        "desc": {
            "fa": "+۶۰ نفت در هر نوبت برای هر سطح",
            "en": "+60 oil/turn per level",
        },
    },
    "research_center": {
        "label": {"fa": "مرکز تحقیقاتی", "en": "Research Center"},
        "cost": {"money": 400, "steel": 100},
        "desc": {
            "fa": "+۱۰ امتیاز تحقیق در هر نوبت برای هر سطح",
            "en": "+10 research points/turn per level",
        },
    },
    "fortification": {
        "label": {"fa": "استحکامات", "en": "Fortification"},
        "cost": {"money": 250, "steel": 200},
        "desc": {
            "fa": "+۵٪ دفاع برای هر سطح",
            "en": "+5% defense per level",
        },
    },
}

# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------

RESEARCH_FIELDS = {
    "economy": {
        "label": {"fa": "اقتصاد", "en": "Economy"},
        "base_cost": 300,
        "desc": {
            "fa": "+۱۰٪ تولید پول برای هر سطح",
            "en": "+10% money production per level",
        },
    },
    "industry": {
        "label": {"fa": "صنعت", "en": "Industry"},
        "base_cost": 300,
        "desc": {
            "fa": "+۱۰٪ تولید فولاد برای هر سطح",
            "en": "+10% steel production per level",
        },
    },
    "military": {
        "label": {"fa": "نظامی", "en": "Military"},
        "base_cost": 350,
        "desc": {
            "fa": "+۱۰٪ قدرت حمله برای هر سطح",
            "en": "+10% attack strength per level",
        },
    },
    "logistics": {
        "label": {"fa": "لجستیک", "en": "Logistics"},
        "base_cost": 250,
        "desc": {
            "fa": "−۱۰٪ هزینه نگهداری ارتش برای هر سطح",
            "en": "-10% army upkeep per level",
        },
    },
}

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_conn():
    """Open a fresh database connection."""
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        autocommit=False,
    )


def init_db():
    """Create all required tables and safe additions for existing databases."""
    if not DATABASE_URL:
        logger.warning("Skipping init_db because DATABASE_URL is not configured.")
        return

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS games (
                        id SERIAL PRIMARY KEY,
                        chat_id BIGINT NOT NULL,
                        code TEXT UNIQUE NOT NULL,
                        host_id BIGINT NOT NULL,
                        turn INTEGER NOT NULL DEFAULT 1,
                        status TEXT NOT NULL DEFAULT 'waiting',
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    );
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS players (
                        id SERIAL PRIMARY KEY,
                        game_id INTEGER NOT NULL
                            REFERENCES games(id) ON DELETE CASCADE,
                        user_id BIGINT NOT NULL,
                        username TEXT,
                        country TEXT,
                        ready BOOLEAN NOT NULL DEFAULT FALSE,
                        score INTEGER NOT NULL DEFAULT 0,
                        UNIQUE(game_id, user_id)
                    );
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS countries (
                        id SERIAL PRIMARY KEY,
                        game_id INTEGER NOT NULL
                            REFERENCES games(id) ON DELETE CASCADE,
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
                    );
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wars (
                        id SERIAL PRIMARY KEY,
                        game_id INTEGER NOT NULL
                            REFERENCES games(id) ON DELETE CASCADE,
                        attacker TEXT NOT NULL,
                        defender TEXT NOT NULL,
                        turn INTEGER NOT NULL,
                        attacker_loss BIGINT NOT NULL DEFAULT 0,
                        defender_loss BIGINT NOT NULL DEFAULT 0,
                        result TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    );
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS market_log (
                        id SERIAL PRIMARY KEY,
                        game_id INTEGER NOT NULL
                            REFERENCES games(id) ON DELETE CASCADE,
                        turn INTEGER NOT NULL,
                        seller TEXT,
                        buyer TEXT,
                        resource TEXT,
                        amount BIGINT,
                        price BIGINT,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    );
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        user_id BIGINT PRIMARY KEY,
                        language TEXT NOT NULL DEFAULT 'fa',
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    );
                    """
                )

                cur.execute(
                    """
                    ALTER TABLE user_preferences
                    ADD COLUMN IF NOT EXISTS language
                    TEXT NOT NULL DEFAULT 'fa'
                    """
                )

                cur.execute(
                    """
                    ALTER TABLE user_preferences
                    ADD COLUMN IF NOT EXISTS updated_at
                    TIMESTAMP NOT NULL DEFAULT NOW()
                    """
                )

            conn.commit()

        logger.info("Database tables verified/created successfully.")

    except Exception:
        logger.exception("Failed to initialize database tables.")


def generate_game_code(length=5):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------------------
# Language helpers
# ---------------------------------------------------------------------------

def normalize_language(language):
    return language if language in LANGS else "fa"


def get_user_language(user_id):
    if not DATABASE_URL or not user_id:
        return "fa"

    try:
        with get_c
