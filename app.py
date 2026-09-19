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
    logger.warning("BOT_TOKEN is not set. Telegram calls will fail until it is configured.")
if not DATABASE_URL:
    logger.warning("DATABASE_URL is not set. Database calls will fail until it is configured.")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Game data: countries, buildings, research
# ---------------------------------------------------------------------------

COUNTRIES = {
    "IR": {"name": "Iran", "flag": "🇮🇷", "money": 1000, "food": 500, "steel": 300, "oil": 800, "population": 1000, "army": 200},
    "TR": {"name": "Turkey", "flag": "🇹🇷", "money": 1200, "food": 600, "steel": 350, "oil": 200, "population": 1100, "army": 220},
    "RU": {"name": "Russia", "flag": "🇷🇺", "money": 1500, "food": 700, "steel": 600, "oil": 1500, "population": 2000, "army": 500},
    "CN": {"name": "China", "flag": "🇨🇳", "money": 2000, "food": 1000, "steel": 800, "oil": 400, "population": 3000, "army": 600},
    "IN": {"name": "India", "flag": "🇮🇳", "money": 1300, "food": 900, "steel": 400, "oil": 150, "population": 2500, "army": 400},
    "DE": {"name": "Germany", "flag": "🇩🇪", "money": 1800, "food": 500, "steel": 700, "oil": 100, "population": 900, "army": 300},
    "FR": {"name": "France", "flag": "🇫🇷", "money": 1600, "food": 550, "steel": 500, "oil": 120, "population": 800, "army": 280},
    "GB": {"name": "United Kingdom", "flag": "🇬🇧", "money": 1700, "food": 450, "steel": 450, "oil": 150, "population": 750, "army": 260},
    "JP": {"name": "Japan", "flag": "🇯🇵", "money": 1900, "food": 400, "steel": 650, "oil": 50, "population": 1300, "army": 320},
    "US": {"name": "United States", "flag": "🇺🇸", "money": 2500, "food": 1200, "steel": 900, "oil": 700, "population": 3500, "army": 700},
    "BR": {"name": "Brazil", "flag": "🇧🇷", "money": 1100, "food": 800, "steel": 300, "oil": 300, "population": 2200, "army": 250},
    "EG": {"name": "Egypt", "flag": "🇪🇬", "money": 900, "food": 400, "steel": 200, "oil": 150, "population": 1100, "army": 230},
}

BUILDINGS = {
    "factory": {"label": "Factory", "cost": {"money": 300, "steel": 100}, "desc": "+50 steel/turn per level"},
    "farm": {"label": "Farm", "cost": {"money": 200, "steel": 50}, "desc": "+80 food/turn per level"},
    "refinery": {"label": "Oil Refinery", "cost": {"money": 350, "steel": 150}, "desc": "+60 oil/turn per level"},
    "research_center": {"label": "Research Center", "cost": {"money": 400, "steel": 100}, "desc": "+10 research points/turn per level"},
    "fortification": {"label": "Fortification", "cost": {"money": 250, "steel": 200}, "desc": "+5% defense per level"},
}

RESEARCH_FIELDS = {
    "economy": {"label": "Economy", "base_cost": 300, "desc": "+10% money production per level"},
    "industry": {"label": "Industry", "base_cost": 300, "desc": "+10% steel production per level"},
    "military": {"label": "Military", "base_cost": 350, "desc": "+10% attack strength per level"},
    "logistics": {"label": "Logistics", "base_cost": 250, "desc": "-10% army upkeep per level"},
}

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_conn():
    """Open a fresh database connection. Caller is responsible for closing it."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=False)


def init_db():
    """Create all required tables if they do not already exist."""
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
                        game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
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
                        game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
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
                        game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
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
                        game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
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
            conn.commit()
        logger.info("Database tables verified/created successfully.")
    except Exception:
        logger.exception("Failed to initialize database tables.")


def generate_game_code(length=5):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------

def tg_call(method, payload=None):
    if not BOT_TOKEN:
        logger.error("Cannot call Telegram method %s: BOT_TOKEN not configured.", method)
        return None
    try:
        resp = requests.post(TELEGRAM_API_BASE + method, json=payload or {}, timeout=10)
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Telegram API returned non-ok for %s: %s", method, data.get("description"))
        return data
    except Exception:
        logger.exception("Telegram API call failed for method %s", method)
        return None


def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return tg_call("sendMessage", payload)


def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    result = tg_call("editMessageText", payload)
    if result is None or not result.get("ok"):
        # Fall back to sending a fresh message if editing failed (e.g. message too old)
        send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
    return result


def answer_callback(callback_query_id, text=None, show_alert=False):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    payload["show_alert"] = show_alert
    return tg_call("answerCallbackQuery", payload)


def set_webhook():
    if not WEBHOOK_URL:
        return {"ok": False, "description": "WEBHOOK_URL not configured"}
    url = WEBHOOK_URL.rstrip("/") + "/telegram"
    payload = {"url": url}
    if WEBHOOK_SECRET:
        payload["secret_token"] = WEBHOOK_SECRET
    return tg_call("setWebhook", payload)


# ---------------------------------------------------------------------------
# Keyboard builders
# ---------------------------------------------------------------------------

def kb(rows):
    return {"inline_keyboard": rows}


def build_country_keyboard(taken_codes):
    rows = []
    row = []
    for code, info in COUNTRIES.items():
        if code in taken_codes:
            continue
        row.append({"text": f"{info['flag']} {info['name']}", "callback_data": f"cty:{code}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return kb(rows)


def build_main_menu():
    rows = [
        [{"text": "📊 Country Status", "callback_data": "menu:status"}, {"text": "🌍 World Status", "callback_data": "menu:world"}],
        [{"text": "🏗️ Buildings", "callback_data": "menu:build"}, {"text": "🔬 Research", "callback_data": "menu:research"}],
        [{"text": "⚔️ Ground Operations", "callback_data": "menu:ground"}, {"text": "🚀 Abstract Strike", "callback_data": "menu:strike"}],
        [{"text": "🏆 Leaderboard", "callback_data": "menu:leader"}, {"text": "✅ End Turn", "callback_data": "menu:endturn"}],
    ]
    return kb(rows)


def build_back_button():
    return kb([[{"text": "⬅️ Back to Menu", "callback_data": "menu:back"}]])


def build_buildings_keyboard():
    rows = []
    for key, info in BUILDINGS.items():
        cost_str = ", ".join(f"{k}:{v}" for k, v in info["cost"].items())
        rows.append([{"text": f"{info['label']} ({cost_str})", "callback_data": f"bld:{key}"}])
    rows.append([{"text": "⬅️ Back to Menu", "callback_data": "menu:back"}])
    return kb(rows)


def build_research_keyboard():
    rows = []
    for key, info in RESEARCH_FIELDS.items():
        rows.append([{"text": f"{info['label']}", "callback_data": f"res:{key}"}])
    rows.append([{"text": "⬅️ Back to Menu", "callback_data": "menu:back"}])
    return kb(rows)


def build_target_keyboard(game_id, exclude_country, prefix, cur):
    cur.execute(
        "SELECT country FROM countries WHERE game_id = %s AND country != %s AND owner_id IS NOT NULL ORDER BY country",
        (game_id, exclude_country),
    )
    rows = []
    row = []
    for r in cur.fetchall():
        code = r["country"]
        info = COUNTRIES.get(code, {"name": code, "flag": ""})
        row.append({"text": f"{info['flag']} {info['name']}", "callback_data": f"{prefix}:{code}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "⬅️ Back to Menu", "callback_data": "menu:back"}])
    return kb(rows)


# ---------------------------------------------------------------------------
# Game data helpers
# ---------------------------------------------------------------------------

def get_active_game(cur, chat_id):
    cur.execute(
        "SELECT * FROM games WHERE chat_id = %s AND status != 'finished' ORDER BY id DESC LIMIT 1",
        (chat_id,),
    )
    return cur.fetchone()


def get_player(cur, game_id, user_id):
    cur.execute(
        "SELECT * FROM players WHERE game_id = %s AND user_id = %s",
        (game_id, user_id),
    )
    return cur.fetchone()


def get_country_row(cur, game_id, country_code):
    cur.execute(
        "SELECT * FROM countries WHERE game_id = %s AND country = %s",
        (game_id, country_code),
    )
    return cur.fetchone()


def get_player_country(cur, game_id, user_id):
    player = get_player(cur, game_id, user_id)
    if not player or not player["country"]:
        return None, None
    country = get_country_row(cur, game_id, player["country"])
    return player, country


def format_money(n):
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_start(message):
    chat_id = message["chat"]["id"]
    text = (
        "🌍 <b>Geopolitical Strategy</b>\n\n"
        "Welcome, leader. Build your nation, research technology, and compete "
        "for global dominance in this turn-based strategy game.\n\n"
        "Use /help to see available commands, or /newgame to start a new game "
        "in this chat."
    )
    send_message(chat_id, text)


def cmd_help(message):
    chat_id = message["chat"]["id"]
    text = (
        "<b>Available Commands</b>\n\n"
        "/newgame - Create a new game in this chat\n"
        "/join - Join the active game\n"
        "/startgame - (Host only) Begin country selection\n"
        "/menu - Open the main game menu\n"
        "/status - View your country status\n"
        "/world - View world status\n"
        "/leaderboard - View the leaderboard\n"
        "/attack - Launch a ground operation\n"
        "/missile - Launch an abstract strike\n"
        "/turn - View turn/ready status\n"
        "/help - Show this message"
    )
    send_message(chat_id, text)


def cmd_newgame(message):
    chat_id = message["chat"]["id"]
    user = message["from"]
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                existing = get_active_game(cur, chat_id)
                if existing and existing["status"] in ("waiting", "selecting", "active"):
                    send_message(chat_id, f"A game is already in progress here (code: <b>{existing['code']}</b>). Use /join to join it.")
                    return
                code = generate_game_code()
                cur.execute(
                    "INSERT INTO games (chat_id, code, host_id, turn, status) VALUES (%s, %s, %s, 1, 'waiting') RETURNING id",
                    (chat_id, code, user["id"]),
                )
                game_row = cur.fetchone()
                game_id = game_row["id"]
                cur.execute(
                    "INSERT INTO players (game_id, user_id, username, ready, score) VALUES (%s, %s, %s, FALSE, 0)",
                    (game_id, user["id"], user.get("username") or user.get("first_name", "Player")),
                )
            conn.commit()
        send_message(
            chat_id,
            f"🎮 New game created! Code: <b>{code}</b>\n\n"
            f"Other players should use /join to enter. When ready, the host can use /startgame.",
        )
    except Exception:
        logger.exception("Error in /newgame")
        send_message(chat_id, "⚠️ Something went wrong creating the game. Please try again.")


def cmd_join(message):
    chat_id = message["chat"]["id"]
    user = message["from"]
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                game = get_active_game(cur, chat_id)
                if not game:
                    send_message(chat_id, "No active game in this chat. Use /newgame to create one.")
                    return
                if game["status"] != "waiting":
                    send_message(chat_id, "This game has already started, you can no longer join.")
                    return
                existing_player = get_player(cur, game["id"], user["id"])
                if existing_player:
                    send_message(chat_id, "You have already joined this game.")
                    return
                cur.execute(
                    "INSERT INTO players (game_id, user_id, username, ready, score) VALUES (%s, %s, %s, FALSE, 0)",
                    (game["id"], user["id"], user.get("username") or user.get("first_name", "Player")),
                )
            conn.commit()
        send_message(chat_id, f"✅ {user.get('first_name', 'Player')} joined the game!")
    except Exception:
        logger.exception("Error in /join")
        send_message(chat_id, "⚠️ Something went wrong joining the game.")


def cmd_startgame(message):
    chat_id = message["chat"]["id"]
    user = message["from"]
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                game = get_active_game(cur, chat_id)
                if not game:
                    send_message(chat_id, "No active game in this chat. Use /newgame to create one.")
                    return
                if game["host_id"] != user["id"]:
                    send_message(chat_id, "Only the host can start the game.")
                    return
                if game["status"] != "waiting":
                    send_message(chat_id, "The game has already started.")
                    return
                cur.execute("UPDATE games SET status = 'selecting' WHERE id = %s", (game["id"],))
            conn.commit()
        send_message(chat_id, "🗺️ Country selection has begun! Each player, tap a country below to claim it.")
        send_message(chat_id, "Choose your country:", reply_markup=build_country_keyboard(set()))
    except Exception:
        logger.exception("Error in /startgame")
    # ---------------------------------------------------------------------------
# Message / callback routing
# ---------------------------------------------------------------------------

def handle_message(message):
    text = (message.get("text") or "").strip()

    if text.startswith("/start"):
        cmd_start(message)

    elif text.startswith("/help"):
        cmd_help(message)

    elif text.startswith("/newgame"):
        cmd_newgame(message)

    elif text.startswith("/join"):
        cmd_join(message)

    elif text.startswith("/startgame"):
        cmd_startgame(message)

    else:
        send_message(
            message["chat"]["id"],
            "دستور شناخته نشد. برای دیدن دستورات /help را بزن."
        )


def handle_callback(callback_query):
    callback_id = callback_query["id"]
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    user = callback_query.get("from") or {}
    data = callback_query.get("data", "")

    answer_callback(callback_id)

    if not chat_id:
        return

    if data == "menu:back":
        send_message(
            chat_id,
            "🎮 <b>Game Menu</b>",
            reply_markup=build_main_menu()
        )
        return

    if data.startswith("cty:"):
        country_code = data.split(":", 1)[1]

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    game = get_active_game(cur, chat_id)

                    if not game:
                        send_message(chat_id, "بازی فعالی وجود ندارد.")
                        return

                    player = get_player(cur, game["id"], user["id"])

                    if not player:
                        send_message(chat_id, "ابتدا باید با /join وارد بازی شوید.")
                        return

                    if player["country"]:
                        send_message(chat_id, "شما قبلاً یک کشور انتخاب کرده‌اید.")
                        return

                    country = get_country_row(cur, game["id"], country_code)

                    if not country:
                        send_message(chat_id, "این کشور وجود ندارد.")
                        return

                    if country["owner_id"] is not None:
                        send_message(chat_id, "این کشور قبلاً انتخاب شده است.")
                        return

                    base = COUNTRIES[country_code]

                    cur.execute(
                        """
                        UPDATE countries
                        SET owner_id=%s,
                            money=%s,
                            food=%s,
                            steel=%s,
                            oil=%s,
                            population=%s,
                            army=%s
                        WHERE game_id=%s AND country=%s
                        """,
                        (
                            user["id"],
                            base["money"],
                            base["food"],
                            base["steel"],
                            base["oil"],
                            base["population"],
                            base["army"],
                            game["id"],
                            country_code,
                        ),
                    )

                    cur.execute(
                        """
                        UPDATE players
                        SET country=%s, ready=TRUE
                        WHERE game_id=%s AND user_id=%s
                        """,
                        (country_code, game["id"], user["id"]),
                    )

                    cur.execute(
                        """
                        SELECT COUNT(*) AS total,
                               COUNT(*) FILTER (WHERE country IS NOT NULL) AS selected
                        FROM players
                        WHERE game_id=%s
                        """,
                        (game["id"],),
                    )

                    counts = cur.fetchone()

                    if counts["total"] > 0 and counts["selected"] == counts["total"]:
                        cur.execute(
                            "UPDATE games SET status='active' WHERE id=%s",
                            (game["id"],),
                        )

                conn.commit()

            info = COUNTRIES[country_code]

            send_message(
                chat_id,
                f"✅ شما <b>{info['flag']} {info['name']}</b> را انتخاب کردید!"
            )

        except Exception:
            logger.exception("Country selection error")
            send_message(
                chat_id,
                "⚠️ هنگام انتخاب کشور خطایی رخ داد."
            )

        return

    send_message(
        chat_id,
        "این گزینه هنوز در نسخه فعلی فعال نشده است."
    )


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return "Strategy Game Bot is running."


@app.get("/health")
def health():
    return jsonify({
        "status": "ok"
    })


@app.get("/set-webhook")
def webhook():
    result = set_webhook()
    return jsonify(result)


@app.post("/telegram")
def telegram():
    if WEBHOOK_SECRET:
        secret = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token"
        )

        if secret != WEBHOOK_SECRET:
            return jsonify({
                "ok": False,
                "error": "invalid secret"
            }), 403

    update = request.get_json(silent=True) or {}

    try:
        if "message" in update:
            handle_message(update["message"])

        elif "callback_query" in update:
            handle_callback(update["callback_query"])

    except Exception:
        logger.exception("UPDATE ERROR")

    return jsonify({
        "ok": True
    })


# ---------------------------------------------------------------------------
# Database initialization
# ---------------------------------------------------------------------------

init_db()


# ---------------------------------------------------------------------------
# Local development
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
