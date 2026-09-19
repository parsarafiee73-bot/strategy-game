import os
import json
import logging
import secrets

import requests
import psycopg
from flask import Flask, request, jsonify

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("strategy-game")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""


# =========================================================
# COUNTRIES
# =========================================================

COUNTRIES = {
    "ایران": {
        "flag": "🇮🇷",
        "money": 10000,
        "food": 8000,
        "steel": 5000,
        "oil": 7000,
        "population": 80,
        "army": 20,
    },
    "ترکیه": {
        "flag": "🇹🇷",
        "money": 10000,
        "food": 8000,
        "steel": 5000,
        "oil": 4000,
        "population": 70,
        "army": 18,
    },
    "روسیه": {
        "flag": "🇷🇺",
        "money": 13000,
        "food": 10000,
        "steel": 9000,
        "oil": 12000,
        "population": 140,
        "army": 30,
    },
    "چین": {
        "flag": "🇨🇳",
        "money": 16000,
        "food": 14000,
        "steel": 12000,
        "oil": 7000,
        "population": 300,
        "army": 35,
    },
    "هند": {
        "flag": "🇮🇳",
        "money": 14000,
        "food": 13000,
        "steel": 7000,
        "oil": 5000,
        "population": 280,
        "army": 28,
    },
    "آلمان": {
        "flag": "🇩🇪",
        "money": 15000,
        "food": 7000,
        "steel": 9000,
        "oil": 3000,
        "population": 60,
        "army": 18,
    },
    "فرانسه": {
        "flag": "🇫🇷",
        "money": 13000,
        "food": 8000,
        "steel": 6000,
        "oil": 4000,
        "population": 55,
        "army": 17,
    },
    "بریتانیا": {
        "flag": "🇬🇧",
        "money": 14000,
        "food": 7000,
        "steel": 6000,
        "oil": 5000,
        "population": 65,
        "army": 19,
    },
    "ژاپن": {
        "flag": "🇯🇵",
        "money": 15000,
        "food": 6000,
        "steel": 7000,
        "oil": 2500,
        "population": 55,
        "army": 16,
    },
    "آمریکا": {
        "flag": "🇺🇸",
        "money": 20000,
        "food": 12000,
        "steel": 12000,
        "oil": 14000,
        "population": 330,
        "army": 40,
    },
    "برزیل": {
        "flag": "🇧🇷",
        "money": 11000,
        "food": 12000,
        "steel": 5000,
        "oil": 6000,
        "population": 150,
        "army": 18,
    },
    "مصر": {
        "flag": "🇪🇬",
        "money": 8000,
        "food": 7000,
        "steel": 3500,
        "oil": 3000,
        "population": 100,
        "army": 14,
    },
}


# =========================================================
# BUILDINGS
# =========================================================

BUILDINGS = {
    "factory": {
        "name": "🏭 کارخانه",
        "money": 2500,
        "steel": 1200,
    },
    "farm": {
        "name": "🌾 مزرعه",
        "money": 1800,
        "steel": 500,
    },
    "oil": {
        "name": "🛢 پالایشگاه",
        "money": 3000,
        "steel": 1500,
    },
    "research": {
        "name": "🔬 مرکز پژوهش",
        "money": 4000,
        "steel": 1000,
    },
    "fort": {
        "name": "🛡 استحکامات",
        "money": 2500,
        "steel": 2000,
    },
}


# =========================================================
# RESEARCH
# =========================================================

RESEARCH = {
    "economy": {
        "name": "اقتصاد",
        "cost": 3000,
    },
    "industry": {
        "name": "صنعت",
        "cost": 3500,
    },
    "military": {
        "name": "ارتش",
        "cost": 4000,
    },
    "logistics": {
        "name": "لجستیک",
        "cost": 3000,
    },
}


# =========================================================
# DATABASE
# =========================================================

def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    return psycopg.connect(DATABASE_URL)


def init_db():
    if not DATABASE_URL:
        log.warning("DATABASE_URL is missing; DB init skipped")
        return

    try:
        with db() as con:
            with con.cursor() as cur:

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS games (
                        id BIGSERIAL PRIMARY KEY,
                        chat_id BIGINT NOT NULL,
                        code TEXT UNIQUE NOT NULL,
                        host_id BIGINT NOT NULL,
                        turn INTEGER NOT NULL DEFAULT 1,
                        status TEXT NOT NULL DEFAULT 'lobby',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS players (
                        id BIGSERIAL PRIMARY KEY,
                        game_id BIGINT NOT NULL
                            REFERENCES games(id)
                            ON DELETE CASCADE,
                        user_id BIGINT NOT NULL,
                        username TEXT,
                        country TEXT,
                        ready BOOLEAN NOT NULL DEFAULT FALSE,
                        score INTEGER NOT NULL DEFAULT 0,
                        UNIQUE(game_id, user_id),
                        UNIQUE(game_id, country)
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS countries (
                        id BIGSERIAL PRIMARY KEY,
                        game_id BIGINT NOT NULL
                            REFERENCES games(id)
                            ON DELETE CASCADE,
                        country TEXT NOT NULL,
                        owner_id BIGINT,
                        money INTEGER NOT NULL,
                        food INTEGER NOT NULL,
                        steel INTEGER NOT NULL,
                        oil INTEGER NOT NULL,
                        population INTEGER NOT NULL,
                        army INTEGER NOT NULL,
                        morale INTEGER NOT NULL DEFAULT 100,
                        score INTEGER NOT NULL DEFAULT 0,
                        buildings TEXT NOT NULL DEFAULT '{}',
                        research TEXT NOT NULL DEFAULT '{}',
                        UNIQUE(game_id, country)
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS wars (
                        id BIGSERIAL PRIMARY KEY,
                        game_id BIGINT NOT NULL
                            REFERENCES games(id)
                            ON DELETE CASCADE,
                        attacker TEXT NOT NULL,
                        defender TEXT NOT NULL,
                        turn INTEGER NOT NULL,
                        attacker_loss INTEGER NOT NULL,
                        defender_loss INTEGER NOT NULL,
                        result TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS market_log (
                        id BIGSERIAL PRIMARY KEY,
                        game_id BIGINT NOT NULL
                            REFERENCES games(id)
                            ON DELETE CASCADE,
                        turn INTEGER NOT NULL,
                        seller TEXT,
                        buyer TEXT,
                        resource TEXT,
                        amount INTEGER,
                        price INTEGER,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)

        log.info("Database initialized")

    except Exception:
        log.exception("Database initialization failed")


# =========================================================
# TELEGRAM API
# =========================================================

def tg(method, payload=None):
    if not BOT_TOKEN:
        return {
            "ok": False,
            "description": "BOT_TOKEN is not configured",
        }

    try:
        response = requests.post(
            f"{TG_API}/{method}",
            json=payload or {},
            timeout=15,
        )

        return response.json()

    except Exception as e:
        log.exception("Telegram API error")

        return {
            "ok": False,
            "description": str(e),
        }


def send(chat_id, text, keyboard=None):
    data = {
        "chat_id": chat_id,
        "text": text,
    }

    if keyboard:
        data["reply_markup"] = {
            "inline_keyboard": keyboard
        }

    return tg("sendMessage", data)


def edit(chat_id, message_id, text, keyboard=None):
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }

    if keyboard is not None:
        data["reply_markup"] = {
            "inline_keyboard": keyboard
        }

    return tg("editMessageText", data)


def answer_callback(callback_id, text=""):
    return tg(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id,
            "text": text,
        },
    )


# =========================================================
# GAME DATABASE HELPERS
# =========================================================

def game_for_chat(con, chat_id):
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT id, code, host_id, turn, status
            FROM games
            WHERE chat_id=%s
              AND status <> 'finished'
            ORDER BY id DESC
            LIMIT 1
            """,
            (chat_id,),
        )

        return cur.fetchone()


def player_for(con, game_id, user_id):
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT id, user_id, username, country, ready, score
            FROM players
            WHERE game_id=%s
              AND user_id=%s
            """,
            (game_id, user_id),
        )

        return cur.fetchone()


def owned_country(con, game_id, user_id):
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT country
            FROM players
            WHERE game_id=%s
              AND user_id=%s
            """,
            (game_id, user_id),
        )

        row = cur.fetchone()

        return row[0] if row else None


# =========================================================
# CREATE GAME
# =========================================================

def create_game(chat_id, user_id):
    code = secrets.token_hex(3).upper()

    with db() as con:
        with con.cursor() as cur:

            cur.execute(
                """
                INSERT INTO games(chat_id, code, host_id)
                VALUES(%s, %s, %s)
                RETURNING id
                """,
                (
                    chat_id,
                    code,
                    user_id,
                ),
            )

            game_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO players(game_id, user_id)
                VALUES(%s, %s)
                """,
                (
                    game_id,
                    user_id,
                ),
            )

            for name, data in COUNTRIES.items():

                cur.execute(
                    """
                    INSERT INTO countries
                    (
                        game_id,
                        country,
                        money,
                        food,
                        steel,
                        oil,
                        population,
                        army
                    )
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        game_id,
                        name,
                        data["money"],
                        data["food"],
                        data["steel"],
                        data["oil"],
                        data["population"],
                        data["army"],
                    ),
                )

    return code


# =========================================================
# KEYBOARDS
# =========================================================

def country_keyboard(game_id):
    with db() as con:
        with con.cursor() as cur:

            cur.execute(
                """
                SELECT country
                FROM countries
                WHERE game_id=%s
                  AND owner_id IS NULL
                ORDER BY country
                """,
                (game_id,),
            )

            free = [
                row[0]
                for row in cur.fetchall()
            ]

    return [
        [
            {
                "text": f'{COUNTRIES[c]["flag"]} {c}',
                "callback_data": f"pick:{c}",
            }
        ]
        for c in free
    ]


def main_keyboard():
    return [
        [
            {
                "text": "🌍 وضعیت کشور",
                "callback_data": "status",
            },
            {
                "text": "🗺 جهان",
                "callback_data": "world",
            },
        ],
        [
            {
                "text": "🏗 ساخت‌وساز",
                "callback_data": "build",
            },
            {
                "text": "🔬 پژوهش",
                "callback_data": "research",
            },
        ],
        [
            {
                "text": "⚔️ عملیات زمینی",
                "callback_data": "attack",
            },
            {
                "text": "🚀 حمله انتزاعی",
                "callback_data": "missile",
            },
        ],
        [
            {
                "text": "🏆 رتبه‌بندی",
                "callback_data": "leaderboard",
            },
            {
                "text": "⏭ پایان نوبت",
                "callback_data": "end",
            },
        ],
    ]


def build_keyboard():
    return [
        [
            {
                "text": data["name"],
                "callback_data": f"build:{key}",
            }
        ]
        for key, data in BUILDINGS.items()
    ]


def research_keyboard():
    return [
        [
            {
                "text": f'🔬 {data["name"]} — {data["cost"]:,}',
                "callback_data": f"research:{key}",
            }
        ]
        for key, data in RESEARCH.items()
    ]


def attack_keyboard(game_id, attacker):
    with db() as con:
        with con.cursor() as cur:

            cur.execute(
                """
                SELECT country
                FROM countries
                WHERE game_id=%s
                  AND owner_id IS NOT NULL
                  AND country<>%s
                ORDER BY country
                """,
                (
                    game_id,
                    attacker,
                ),
            )

            rows = [
                row[0]
                for row in cur.fetchall()
            ]

    return [
        [
            {
                "text": f'{COUNTRIES[c]["flag"]} {c}',
                "callback_data": f"attack:{c}",
            }
        ]
        for c in rows
    ]


def missile_keyboard(game_id, attacker):
    with db() as con:
        with con.cursor() as cur:

            cur.execute(
                """
                SELECT country
                FROM countries
                WHERE game_id=%s
                  AND owner_id IS NOT NULL
                  AND country<>%s
                ORDER BY country
                """,
                (
                    game_id,
                    attacker,
                ),
            )

            rows = [
                row[0]
                for row in cur.fetchall()
            ]

    return [
        [
            {
                "text": f'{COUNTRIES[c]["flag"]} {c}',
                "callback_data": f"missile:{c}",
            }
        ]
        for c in rows
    ]


# =========================================================
# STATUS
# =========================================================

def status_text(game_id, user_id):
    with db() as con:

        country = owned_country(
            con,
            game_id,
            user_id,
        )

        if not country:
            return "هنوز کشوری انتخاب نکرده‌ای."

        with con.cursor() as cur:

            cur.execute(
                """
                SELECT
                    money,
                    food,
                    steel,
                    oil,
                    population,
                    army,
                    morale,
                    score,
                    buildings,
                    research
                FROM countries
                WHERE game_id=%s
                  AND country=%s
                """,
                (
                    game_id,
                    country,
                ),
            )

            r = cur.fetchone()

    buildings = json.loads(
        r[8] or "{}"
    )

    research = json.loads(
        r[9] or "{}"
    )

    btxt = ", ".join(
        f"{BUILDINGS[k]['name']}×{v}"
        for k, v in buildings.items()
        if k in BUILDINGS
    )

    rtxt = ", ".join(
        RESEARCH[k]["name"]
        for k, v in research.items()
        if v and k in RESEARCH
    )

    if not btxt:
        btxt = "ندارد"

    if not rtxt:
        rtxt = "ندارد"

    return (
        f'{COUNTRIES[country]["flag"]} {country}\n\n'
        f"💰 پول: {r[0]:,}\n"
        f"🌾 غذا: {r[1]:,}\n"
        f"🔩 فولاد: {r[2]:,}\n"
        f"🛢 نفت: {r[3]:,}\n"
        f"👥 جمعیت: {r[4]:,}\n"
        f"⚔️ ارتش: {r[5]:,}\n"
        f"🛡 روحیه: {r[6]}%\n"
        f"🏆 امتیاز: {r[7]:,}\n\n"
        f"🏗 ساختمان‌ها: {btxt}\n"
        f"🔬 پژوهش: {rtxt}"
    )


# =========================================================
# WORLD
# =========================================================

def world_text(game_id):
    with db() as con:
        with con.cursor() as cur:

            cur.execute(
                """
                SELECT
                    country,
                    owner_id,
                    money,
                    food,
                    steel,
                    oil,
                    army,
                    morale,
                    score
                FROM countries
                WHERE game_id=%s
                ORDER BY score DESC, country
                """,
                (game_id,),
            )

            rows = cur.fetchall()

    lines = [
        "🗺 وضعیت جهان\n"
    ]

    for (
        country,
        owner,
        money,
        food,
        steel,
        oil,
        army,
        morale,
        score,
    ) in rows:

        state = (
            "👤 بازیکن"
            if owner
            else "🤖 آزاد"
        )

        lines.append(
            f'{COUNTRIES[country]["flag"]} {country} — {state}\n'
            f"  💰 {money:,} | "
            f"🌾 {food:,} | "
            f"🔩 {steel:,} | "
            f"🛢 {oil:,}\n"
            f"  ⚔️ {army:,} | "
            f"🛡 {morale}% | "
            f"🏆 {score:,}"
        )

    return "\n".join(lines)


# =========================================================
# LEADERBOARD
# =========================================================

def leaderboard_text(game_id):
    with db() as con:
        with con.cursor() as cur:

            cur.execute(
                """
                SELECT
                    p.country,
                    p.score,
                    p.username
                FROM players p
                WHERE p.game_id=%s
                  AND p.country IS NOT NULL
            
