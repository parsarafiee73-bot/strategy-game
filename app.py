import os
import json
import random
from datetime import datetime

import requests
import psycopg
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# =========================
# COUNTRIES
# =========================

COUNTRIES = {
    "iran": {
        "name": "🇮🇷 Iran",
        "money": 1200,
        "food": 900,
        "steel": 500,
        "oil": 700,
        "pop": 80,
    },
    "turkey": {
        "name": "🇹🇷 Turkey",
        "money": 1300,
        "food": 850,
        "steel": 550,
        "oil": 350,
        "pop": 85,
    },
    "iraq": {
        "name": "🇮🇶 Iraq",
        "money": 950,
        "food": 700,
        "steel": 350,
        "oil": 950,
        "pop": 45,
    },
    "germany": {
        "name": "🇩🇪 Germany",
        "money": 1800,
        "food": 650,
        "steel": 850,
        "oil": 250,
        "pop": 84,
    },
    "france": {
        "name": "🇫🇷 France",
        "money": 1650,
        "food": 800,
        "steel": 650,
        "oil": 300,
        "pop": 68,
    },
    "uk": {
        "name": "🇬🇧 UK",
        "money": 1700,
        "food": 700,
        "steel": 600,
        "oil": 450,
        "pop": 68,
    },
    "japan": {
        "name": "🇯🇵 Japan",
        "money": 1750,
        "food": 500,
        "steel": 650,
        "oil": 180,
        "pop": 124,
    },
    "india": {
        "name": "🇮🇳 India",
        "money": 1500,
        "food": 1200,
        "steel": 600,
        "oil": 500,
        "pop": 1400,
    },
    "brazil": {
        "name": "🇧🇷 Brazil",
        "money": 1250,
        "food": 1100,
        "steel": 450,
        "oil": 650,
        "pop": 215,
    },
    "usa": {
        "name": "🇺🇸 USA",
        "money": 2200,
        "food": 1000,
        "steel": 1000,
        "oil": 1000,
        "pop": 340,
    },
    "china": {
        "name": "🇨🇳 China",
        "money": 2100,
        "food": 1400,
        "steel": 1200,
        "oil": 650,
        "pop": 1400,
    },
    "russia": {
        "name": "🇷🇺 Russia",
        "money": 1500,
        "food": 850,
        "steel": 1100,
        "oil": 1400,
        "pop": 145,
    },
}


# =========================
# BUILDINGS
# =========================

BUILDINGS = {
    "farm": {
        "name": "🌾 Farm",
        "cost": {"money": 250, "steel": 60},
    },
    "factory": {
        "name": "🏭 Factory",
        "cost": {"money": 500, "steel": 150},
    },
    "steel_mill": {
        "name": "⚙️ Steel Mill",
        "cost": {"money": 450, "steel": 120},
    },
    "university": {
        "name": "🎓 University",
        "cost": {"money": 700, "steel": 180},
    },
    "bunker": {
        "name": "🛡 Bunker",
        "cost": {"money": 350, "steel": 100},
    },
    "command": {
        "name": "🏛 Command Center",
        "cost": {"money": 900, "steel": 250},
    },
}


# =========================
# RESEARCH
# =========================

RESEARCH = {
    "economy": {
        "name": "💰 Economy",
        "cost": 700,
    },
    "industry": {
        "name": "🏭 Industry",
        "cost": 700,
    },
    "military": {
        "name": "⚔️ Military",
        "cost": 800,
    },
    "logistics": {
        "name": "🚚 Logistics",
        "cost": 650,
    },
    "diplomacy": {
        "name": "🤝 Diplomacy",
        "cost": 600,
    },
}


# =========================
# DATABASE
# =========================

def db():
    return psycopg.connect(DATABASE_URL)


def init_db():
    if not DATABASE_URL:
        return

    with db() as con:
        with con.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    host_id BIGINT NOT NULL,
                    turn INT NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'lobby',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    game_id INT NOT NULL
                        REFERENCES games(id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    country TEXT,
                    ready BOOLEAN NOT NULL DEFAULT FALSE,
                    money INT NOT NULL DEFAULT 0,
                    food INT NOT NULL DEFAULT 0,
                    steel INT NOT NULL DEFAULT 0,
                    oil INT NOT NULL DEFAULT 0,
                    population INT NOT NULL DEFAULT 0,
                    army INT NOT NULL DEFAULT 0,
                    score INT NOT NULL DEFAULT 0,
                    buildings JSONB NOT NULL DEFAULT '{}'::jsonb,
                    research JSONB NOT NULL DEFAULT '{}'::jsonb,
                    UNIQUE(game_id, user_id),
                    UNIQUE(game_id, country)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS countries (
                    game_id INT NOT NULL
                        REFERENCES games(id) ON DELETE CASCADE,
                    country TEXT NOT NULL,
                    owner_id BIGINT,
                    money INT NOT NULL,
                    food INT NOT NULL,
                    steel INT NOT NULL,
                    oil INT NOT NULL,
                    population INT NOT NULL,
                    army INT NOT NULL DEFAULT 0,
                    morale INT NOT NULL DEFAULT 100,
                    score INT NOT NULL DEFAULT 0,
                    buildings JSONB NOT NULL DEFAULT '{}'::jsonb,
                    research JSONB NOT NULL DEFAULT '{}'::jsonb,
                    PRIMARY KEY(game_id, country)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS wars (
                    id SERIAL PRIMARY KEY,
                    game_id INT NOT NULL
                        REFERENCES games(id) ON DELETE CASCADE,
                    attacker TEXT NOT NULL,
                    defender TEXT NOT NULL,
                    turn INT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS market_log (
                    id SERIAL PRIMARY KEY,
                    game_id INT NOT NULL
                        REFERENCES games(id) ON DELETE CASCADE,
                    turn INT NOT NULL,
                    country TEXT NOT NULL,
                    action TEXT NOT NULL,
                    amount INT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)


# =========================
# TELEGRAM
# =========================

def tg(method, data=None):
    if not BOT_TOKEN:
        return {}

    try:
        response = requests.post(
            f"{TG_API}/{method}",
            json=data or {},
            timeout=20,
        )
        return response.json()
    except Exception as e:
        print("TELEGRAM ERROR:", repr(e))
        return {}


def send(chat_id, text, keyboard=None):
    data = {
        "chat_id": chat_id,
        "text": text,
    }

    if keyboard:
        data["reply_markup"] = json.dumps(keyboard)

    return tg("sendMessage", data)


def answer_callback(callback_id, text=""):
    return tg(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id,
            "text": text,
        },
    )


# =========================
# MENUS
# =========================

def main_menu():
    return {
        "inline_keyboard": [
            [
                {"text": "🌍 World", "callback_data": "world"},
                {"text": "🏳️ Country", "callback_data": "country"},
            ],
            [
                {"text": "📊 Status", "callback_data": "status"},
                {"text": "🏆 Leaderboard", "callback_data": "leaderboard"},
            ],
            [
                {"text": "🏗 Build", "callback_data": "build_menu"},
                {"text": "🔬 Research", "callback_data": "research_menu"},
            ],
            [
                {"text": "⚔️ Attack", "callback_data": "attack_menu"},
                {
                    "text": "🚀 Abstract Strike",
                    "callback_data": "missile_menu",
                },
            ],
            [
                {"text": "👨‍✈️ Recruit", "callback_data": "recruit"},
                {"text": "✅ End Turn", "callback_data": "endturn"},
            ],
        ]
    }


def build_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "🌾 Farm", "callback_data": "build:farm"},
                {"text": "🏭 Factory", "callback_data": "build:factory"},
            ],
            [
                {
                    "text": "⚙️ Steel Mill",
                    "callback_data": "build:steel_mill",
                },
                {
                    "text": "🎓 University",
                    "callback_data": "build:university",
                },
            ],
            [
                {"text": "🛡 Bunker", "callback_data": "build:bunker"},
                {"text": "🏛 Command", "callback_data": "build:command"},
            ],
        ]
    }


def research_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "💰 Economy",
                    "callback_data": "research:economy",
                },
                {
                    "text": "🏭 Industry",
                    "callback_data": "research:industry",
                },
            ],
            [
                {
                    "text": "⚔️ Military",
                    "callback_data": "research:military",
                },
                {
                    "text": "🚚 Logistics",
                    "callback_data": "research:logistics",
                },
            ],
            [
                {
                    "text": "🤝 Diplomacy",
                    "callback_data": "research:diplomacy",
                }
            ],
        ]
    }


# =========================
# GAME HELPERS
# =========================

def get_player(con, game_id, user_id):
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM players
            WHERE game_id=%s AND user_id=%s
            """,
            (game_id, user_id),
        )
        return cur.fetchone()


def get_active_game(con, user_id):
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT g.*
            FROM games g
            JOIN players p ON p.game_id=g.id
            WHERE p.user_id=%s
              AND g.status <> 'finished'
            ORDER BY g.id DESC
            LIMIT 1
            """,
            (user_id,),
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
              AND country IS NOT NULL
            """,
            (game_id, user_id),
        )

        row = cur.fetchone()
        return row[0] if row else None


def country_info(con, game_id, country):
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM countries
            WHERE game_id=%s AND country=%s
            """,
            (game_id, country),
        )
        return cur.fetchone()


# =========================
# GAME CREATION
# =========================

def create_game(user_id, username):
    with db() as con:
        with con.cursor() as cur:

            cur.execute(
                """
                INSERT INTO games(name, host_id)
                VALUES(%s, %s)
                RETURNING id
                """,
                (
                    f"Game {datetime.utcnow().strftime('%H:%M:%S')}",
                    user_id,
                ),
            )

            game_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO players(game_id, user_id, username)
                VALUES(%s, %s, %s)
                """,
                (game_id, user_id, username),
            )

            for key, country in COUNTRIES.items():
                cur.execute(
                    """
                    INSERT INTO countries(
                        game_id,
                        country,
                        money,
                        food,
                        steel,
                        oil,
                        population
                    )
                    VALUES(%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        game_id,
                        key,
                        country["money"],
                        country["food"],
                        country["steel"],
                        country["oil"],
                        country["pop"],
                    ),
                )

            return game_id


def join_game(game_id, user_id, username):
    with db() as con:
        with con.cursor() as cur:
            cur.execute(
                """
                INSERT INTO players(game_id, user_id, username)
                VALUES(%s, %s, %s)
                ON CONFLICT(game_id, user_id)
                DO UPDATE SET username=EXCLUDED.username
                """,
                (game_id, user_id, username),
            )


# =========================
# COUNTRY
# =========================

def assign_country(game_id, user_id, country):
    if country not in COUNTRIES:
        return False, "Invalid country."

    with db() as con:
        with con.cursor() as cur:

            cur.execute(
                """
                SELECT owner_id
                FROM countries
                WHERE game_id=%s AND country=%s
                """,
                (game_id, country),
            )

            row = cur.fetchone()

            if not row:
                return False, "Country does not exist."

            if row[0] is not None:
                return False, "This country is already taken."

            cur.execute(
                """
                SELECT country
                FROM players
                WHERE game_id=%s
                  AND user_id=%s
                """,
                (game_id, user_id),
            )

            existing = cur.fetchone()

            if existing and existing[0]:
                return False, "You already selected a country."

            cur.execute(
                """
                UPDATE countries
                SET owner_id=%s
                WHERE game_id=%s
                  AND country=%s
                """,
                (user_id, game_id, country),
            )

            cur.execute(
                """
                UPDATE players
                SET country=%s
                WHERE game_id=%s
                  AND user_id=%s
                """,
                (country, game_id, user_id),
            )

            return True, f"You selected {COUNTRIES[country]['name']}."


def country_keyboard(con, game_id):
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT country, owner_id
            FROM countries
            WHERE game_id=%s
            ORDER BY country
            """,
            (game_id,),
        )

        rows = cur.fetchall()

    buttons = []

    for country, owner in rows:
        if owner is None:
            buttons.append(
                {
                    "text": COUNTRIES[country]["name"],
                    "callback_data": f"pick:{country}",
                }
            )

    return {
        "inline_keyboard": [
            buttons[i:i + 2]
            for i in range(0, len(buttons), 2)
        ]
    }


# =========================
# STATUS / WORLD
# =========================

def status_text(con, game_id, user_id):
    player = get_player(con, game_id, user_id)

    if not player:
        return "You are not in a game."

    country = player[4]

    if not country:
        return "You have not selected a country yet."

    country_data = country_info(con, game_id, country)

    if not country_data:
        return "Country data not found."

    return (
        f"{COUNTRIES[country]['name']}\n\n"
        f"💰 Money: {country_data[3]}\n"
        f"🌾 Food: {country_data[4]}\n"
        f"⚙️ Steel: {country_data[5]}\n"
        f"🛢 Oil: {country_data[6]}\n"
        f"👥 Population: {country_data[7]}\n"
        f"⚔️ Army: {country_data[8]}\n"
        f"🛡 Morale: {country_data[9]}\n"
        f"🏆 Score: {country_data[10]}"
    )


def world_text(con, game_id):
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
                population,
                army,
                morale,
                score
            FROM countries
            WHERE game_id=%s
            ORDER BY score DESC
            """,
            (game_id,),
        )

        rows = cur.fetchall()

    lines = ["🌍 WORLD", ""]

    for row in rows:
        country = row[0]
        owner = "👤" if row[1] else "⚪"

        lines.append(
            f"{owner} {COUNTRIES[country]['name']} — "
            f"💰{row[2]} "
            f"⚔️{row[7]} "
            f"🛡{row[8]} "
            f"🏆{row[9]}"
        )

    return "\n".join(lines)


def leaderboard_text(con, game_id):
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT country, score, army, morale
            FROM countries
            WHERE game_id=%s
            ORDER BY score DESC
            LIMIT 10
            """,
            (game_id,),
        )

        rows = cur.fetchall()

    lines = ["🏆 LEADERBOARD", ""]

    for index, row in enumerate(rows, 1):
        lines.append(
            f"{index}. {COUNTRIES[row[0]]['name']} — "
            f"{row[1]} pts | "
            f"Army {row[2]} | "
            f"Morale {row[3]}"
        )

    return "\n".join(lines)


# =========================
# RECRUIT
# =========================

def recruit_action(game_id, user_id):
    with db() as con:
        country = owned_country(con, game_id, user_id)

        if not country:
            return "Select a country first."

        with con.cursor() as cur:
            cur.execute(
                """
                SELECT money, population, army
                FROM countries
                WHERE game_id=%s
                  AND country=%s
                FOR UPDATE
                """,
                (game_id, country),
            )

            row = cur.fetchone()

            if not row:
                return "Country not found."

            if row[0] < 250 or row[1] < 1:
                return "Not enough resources."

            cur.execute(
                """
                UPDATE countries
                SET
                    money=money-250,
                    population=population-1,
                    army=army+100
                WHERE game_id=%s
                  AND country=%s
                """,
                (game_id, country),
            )

    return "👨‍✈️ Recruited +100 army for 250 money and 1 population."


# =========================
# BUILD
# =========================

def build_action(game_id, user_id, building):
    if building not in BUILDIN
