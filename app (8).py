import html as html_lib
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

MAX_ROUNDS = 12      # each round = one turn for every player
BASE_ACTIONS = 3

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
            "🚪 /leave: خروج از بازی فعلی (سازنده بازی را لغو می‌کند).\n"
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
        "game_created": "بازی ساخته شد ✅\n\nکد بازی: \u2066<code>{code}</code>\u2069\nسازنده: {name}\n\nکد را برای بقیه بازیکن‌ها بفرست.",
        "game_already": "تو همین الان در یک بازی فعال هستی و برای همین بازی جدید ساخته نشد.\n\nکد بازی فعلی:\n\u2066<code>{code}</code>\u2069\n\nاگر می‌خواهی بازی جدید بسازی، اول /leave را بفرست.",
        "left_game": "از بازی خارج شدی ✅\n\nحالا می‌توانی بازی جدید بسازی یا با کد وارد بازی دیگری شوی.",
        "game_cancelled": "بازی لغو شد ✅\n\nحالا می‌توانی بازی جدید بسازی.",
        "cannot_leave_running": "بازی در حال اجراست و فقط سازنده می‌تواند آن را لغو کند.",
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
            "🚪 /leave: leave your current game (the owner cancels it).\n"
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
        "game_already": "You are already in an active game, so no new game was created.\n\nCurrent game code:\n<code>{code}</code>\n\nSend /leave first if you want to start a new one.",
        "left_game": "You left the game ✅\n\nYou can now create a new game or join another one with a code.",
        "game_cancelled": "Game cancelled ✅\n\nYou can now create a new game.",
        "cannot_leave_running": "The game is running and only its owner can cancel it.",
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

# v3 texts (merged into TEXTS; later keys override the old ones)
TEXTS["fa"].update({
    "help": (
        "راهنما\n\n"
        "🎮 ساخت بازی: یک لابی جدید می‌سازد.\n"
        "🔑 پیوستن به بازی: با کد ۶ حرفی وارد لابی می‌شوی.\n"
        "🌍 کشور: کشور آزاد را برای بازی انتخاب می‌کنی (هر کشور یک ویژگی ویژه دارد).\n"
        "📋 بازی من: وضعیت بازی فعلی را می‌بینی.\n"
        "📖 قوانین: توضیح کامل اقدام‌ها و امتیازدهی.\n"
        "🚪 /leave: خروج از بازی فعلی (سازنده بازی را لغو می‌کند).\n\n"
        "حداقل ۲ بازیکن برای شروع لازم است."
    ),
    "rules": (
        "قوانین نسخه فعلی\n\n"
        "• هر بازیکن یک کشور با یک ویژگی ویژه انتخاب می‌کند.\n"
        f"• بازی {MAX_ROUNDS} دوره طول می‌کشد؛ در هر دوره همه بازیکن‌ها یک نوبت دارند.\n"
        "• در هر نوبت ۳ اقدام داری (با ۲۰ علم یا بیشتر، یک اقدام اضافه می‌گیری).\n\n"
        "اقدام‌ها:\n"
        "🏭 ساخت صنعت: هزینه با رشد صنعت بیشتر می‌شود.\n"
        "🔬 تحقیق: هر ۱۰ علم یک سطح فناوری است؛ هر سطح درآمد و قدرت حمله را بیشتر می‌کند.\n"
        "💰 تجارت: درآمد به بازار (تصادفی) و پیمان‌های فعال بستگی دارد.\n"
        "🪖 جذب نیرو: برای حمله و دفاع لازم است، ولی هر واحد در پایان نوبت ۵ پول هزینه دارد.\n"
        "🏛️ اصلاحات: ثبات را بالا می‌برد.\n"
        "🤝 دیپلماسی: پیمان ۳ دوره‌ای با یک بازیکن. هر دو ثبات و پول می‌گیرند، حمله بین شما ممنوع می‌شود و درآمد تجارت بیشتر می‌شود.\n"
        "⚔️ حمله: از دوره ۲ ممکن است. برنده بخشی از پول حریف را می‌برد؛ بازنده نیرو و ثبات از دست می‌دهد.\n\n"
        "• پایان هر نوبت: درآمد پایه، هزینه ارتش و گاهی یک رویداد تصادفی.\n"
        "• ثبات بالای ۸۰ پاداش می‌دهد، زیر ۳۰ درآمد را کم می‌کند و زیر ۲۰ ناآرامی می‌آورد.\n"
        "• امتیاز = پول + صنعت + علم + ثبات + جمعیت + ارتش."
    ),
    "game_finished": "بازی تمام شد 🏁\n\n{results}",
    "recruit": "🪖 جذب نیرو",
    "welfare": "🏛️ اصلاحات",
    "attack": "⚔️ حمله",
    "military": "نظامی",
    "tier": "سطح",
    "perk": "ویژگی کشور",
    "scoreboard": "جدول امتیازها",
    "treaties": "پیمان‌های فعال",
    "until_round": "تا دوره",
    "pick_target_attack": "به چه کسی حمله می‌کنی؟",
    "pick_target_diplomacy": "با چه کسی پیمان می‌بندی؟",
    "income_line": "💵 درآمد: {income} | 🪖 هزینه ارتش: {upkeep}",
    "unrest": "🔥 ناآرامی در کشور {player}! ثبات خیلی پایین است و مقداری پول و صنعت از بین رفت.",
    "no_military": "برای حمله حداقل ۱ واحد نظامی لازم است. اول جذب نیرو کن.",
    "treaty_active": "با این بازیکن پیمان فعال داری و نمی‌توانی به او حمله کنی.",
    "treaty_exists": "با این بازیکن از قبل پیمان فعال داری.",
    "too_early": "در دوره اول حمله ممنوع است.",
    "bad_target": "هدف نامعتبر است.",
    "res_build": "🏭 صنعت {n} واحد رشد کرد (هزینه: {cost}).",
    "res_research": "🔬 تحقیق پیشرفت کرد: {n}+ علم (هزینه: {cost}).",
    "res_trade": "💰 تجارت انجام شد: {gain}+ پول (بازار: {market}، پیمان‌های فعال: {partners}).",
    "res_recruit": "🪖 {n} واحد نظامی جذب شد (هزینه: {cost}).",
    "res_welfare": "🏛️ اصلاحات انجام شد: ثبات {n}+ (هزینه: {cost}).",
    "res_diplomacy": "🤝 {attacker} و {target} پیمان صلح و تجارت بستند (تا دوره {until}). هر دو ثبات و پول گرفتند.",
    "res_attack_win": "⚔️ {attacker} به {defender} حمله کرد و پیروز شد! غنیمت: {loot} پول. (قدرت {atk} در برابر {dfn}) {defender} صنعت، جمعیت و ثبات از دست داد.",
    "res_attack_lose": "⚔️ حمله {attacker} به {defender} شکست خورد! (قدرت {atk} در برابر {dfn}) {attacker} نیرو و ثبات از دست داد.",
})

TEXTS["en"].update({
    "help": (
        "Help\n\n"
        "🎮 Create Game: create a new lobby.\n"
        "🔑 Join Game: join a lobby with a 6-character code.\n"
        "🌍 Country: choose an available country (each has a special perk).\n"
        "📋 My Game: show your current game.\n"
        "📖 Rules: full explanation of actions and scoring.\n"
        "🚪 /leave: leave your current game (the owner cancels it).\n\n"
        "At least 2 players are required to start."
    ),
    "rules": (
        "Current rules\n\n"
        "• Each player picks a country with a special perk.\n"
        f"• The game lasts {MAX_ROUNDS} rounds; every player gets one turn per round.\n"
        "• You have 3 actions per turn (20+ science gives a 4th).\n\n"
        "Actions:\n"
        "🏭 Build Industry: cost grows with your industry.\n"
        "🔬 Research: every 10 science is a tech tier; each tier boosts income and attack power.\n"
        "💰 Trade: income depends on the (random) market and your active treaties.\n"
        "🪖 Recruit: needed to attack and defend, but each unit costs 5 upkeep per turn.\n"
        "🏛️ Reform: raises stability.\n"
        "🤝 Diplomacy: a 3-round treaty with one player. Both gain stability and money, attacks between you are blocked, and trade pays more.\n"
        "⚔️ Attack: possible from round 2. The winner loots part of the rival's money; the loser loses units and stability.\n\n"
        "• End of turn: base income, army upkeep and sometimes a random event.\n"
        "• Stability above 80 gives a bonus, below 30 cuts income and below 20 causes unrest.\n"
        "• Score = money + industry + science + stability + population + army."
    ),
    "game_finished": "Game finished 🏁\n\n{results}",
    "recruit": "🪖 Recruit",
    "welfare": "🏛️ Reform",
    "attack": "⚔️ Attack",
    "military": "Military",
    "tier": "Tier",
    "perk": "Country perk",
    "scoreboard": "Scoreboard",
    "treaties": "Active treaties",
    "until_round": "until round",
    "pick_target_attack": "Who do you want to attack?",
    "pick_target_diplomacy": "Who do you want to sign a treaty with?",
    "income_line": "💵 Income: {income} | 🪖 Army upkeep: {upkeep}",
    "unrest": "🔥 Unrest in {player}'s country! Stability is very low: some money and industry were lost.",
    "no_military": "You need at least 1 military unit to attack. Recruit first.",
    "treaty_active": "You have an active treaty with this player, so you cannot attack.",
    "treaty_exists": "You already have an active treaty with this player.",
    "too_early": "Attacks are not allowed in round 1.",
    "bad_target": "Invalid target.",
    "res_build": "🏭 Industry grew by {n} (cost: {cost}).",
    "res_research": "🔬 Research advanced: +{n} science (cost: {cost}).",
    "res_trade": "💰 Trade done: +{gain} money (market {market}, active treaties: {partners}).",
    "res_recruit": "🪖 Recruited {n} military units (cost: {cost}).",
    "res_welfare": "🏛️ Reforms passed: +{n} stability (cost: {cost}).",
    "res_diplomacy": "🤝 {attacker} and {target} signed a peace & trade treaty (until round {until}). Both gained stability and money.",
    "res_attack_win": "⚔️ {attacker} attacked {defender} and won! Loot: {loot} money. (power {atk} vs {dfn}) {defender} lost industry, population and stability.",
    "res_attack_lose": "⚔️ {attacker}'s attack on {defender} failed! (power {atk} vs {dfn}) {attacker} lost units and stability.",
})

# v4 texts (merged into TEXTS; later keys override the older ones)
TEXTS["fa"].update({
    "help": (
        "راهنما\n\n"
        "🎮 ساخت بازی: یک لابی جدید می‌سازد.\n"
        "🔑 پیوستن به بازی: با کد ۶ حرفی وارد لابی می‌شوی.\n"
        "🌍 کشور: کشور آزاد را برای بازی انتخاب می‌کنی (هر کشور یک ویژگی ویژه دارد).\n"
        "📋 بازی من: وضعیت بازی فعلی را می‌بینی.\n"
        "🎯 ماموریت: هدف مخفی خودت را ببین (فقط خودت می‌بینی).\n"
        "📖 قوانین: توضیح کامل اقدام‌ها و امتیازدهی.\n"
        "🚪 /leave: خروج از بازی فعلی (سازنده بازی را لغو می‌کند).\n\n"
        "حداقل ۲ بازیکن برای شروع لازم است."
    ),
    "rules": (
        "قوانین نسخه فعلی\n\n"
        "• هر بازیکن یک کشور با ویژگی ویژه و یک ماموریت مخفی دارد (رسیدن به آن ۱۵۰۰ امتیاز پاداش می‌دهد).\n"
        f"• بازی {MAX_ROUNDS} دوره است؛ در هر دوره همه یک نوبت دارند. ابتدای هر دوره ممکن است یک رویداد جهانی همه را تحت تأثیر بگذارد.\n"
        "• هر نوبت ۳ اقدام داری (با ۲۰ علم یا بیشتر، ۴ اقدام).\n\n"
        "اقتصاد و رشد:\n"
        "🏭 ساخت صنعت (هزینه با رشد صنعت بیشتر می‌شود)\n"
        "🔬 تحقیق (هر ۱۰ علم یک سطح فناوری: درآمد و قدرت حمله بیشتر)\n"
        "💰 تجارت (بازار تصادفی، پیمان‌ها سود را بیشتر و تحریم آن را کمتر می‌کنند)\n"
        "🏛️ اصلاحات (ثبات بیشتر)\n"
        "🧪 فناوری (خرید یک‌بار مصرف: اتوماسیون، لجستیک، تسلیحات، استحکامات، پزشکی، رسانه، اطلاعات، نهادها، برنامه فضایی؛ نیاز به علم و پول)\n\n"
        "سیاست و جنگ:\n"
        "🪖 جذب نیرو (هر واحد در پایان نوبت ۵ پول هزینه دارد)\n"
        "⚔️ حمله (از دوره ۲؛ برنده بخشی از پول حریف را می‌برد)\n"
        "🤝 دیپلماسی (پیمان ۳ دوره‌ای: هر دو سود می‌برند و حمله بینتان ممنوع می‌شود)\n"
        "🚫 تحریم (۳ دوره: تجارت هدف ۳۰٪ کم می‌شود و درآمدش ۵٪ افت می‌کند؛ روی پیمان‌بند ممکن نیست)\n"
        "🕵️ جاسوسی (اگر موفق شوی علم می‌دزدی و آمار هدف را خصوصی می‌بینی؛ اگر لو بروی ثبات و پول از دست می‌دهی)\n\n"
        "• پایان هر نوبت: درآمد پایه، هزینه ارتش و گاهی یک رویداد تصادفی.\n"
        "• ثبات بالای ۸۰ پاداش می‌دهد، زیر ۳۰ درآمد را کم می‌کند و زیر ۲۰ ناآرامی می‌آورد.\n"
        "• امتیاز = پول + صنعت + علم + ثبات + جمعیت + ارتش + پاداش ماموریت و برنامه فضایی."
    ),
    "tech": "🧪 فناوری",
    "spy": "🕵️ جاسوسی",
    "sanction": "🚫 تحریم",
    "mission": "🎯 ماموریت",
    "techs_title": "فناوری‌ها",
    "sanctions": "تحریم‌های فعال",
    "pick_target_spy": "علیه چه کسی جاسوسی می‌کنی؟",
    "pick_target_sanction": "چه کسی را تحریم می‌کنی؟",
    "pick_tech": "فناوری مورد نظر را انتخاب کن:",
    "all_techs": "همه فناوری‌ها را دارید ✅",
    "mission_text": "🎯 ماموریت مخفی تو:\n{title}\nپیشرفت: {cur} / {target}\nپاداش: {bonus}+ امتیاز در پایان بازی",
    "trade_sanctioned": "(تحریم: ۳۰٪ کاهش سود)",
    "sanction_exists": "این بازیکن را از قبل تحریم کرده‌ای.",
    "tech_owned": "این فناوری را از قبل داری.",
    "tech_locked": "علم کافی برای این فناوری نداری.",
    "bad_tech": "فناوری نامعتبر است.",
    "res_spy_ok": "🕵️ جاسوسان {attacker} در {target} نفوذ کردند و {stolen} علم دزدیدند! (شانس موفقیت: {chance}٪)",
    "res_spy_fail": "🕵️ جاسوسان {attacker} در {target} لو رفتند! {attacker} ثبات و پول از دست داد. (شانس موفقیت: {chance}٪)",
    "res_sanction": "🚫 {attacker} کشور {target} را تا دوره {until} تحریم کرد.",
    "res_tech": "🧪 فناوری «{name}» به دست آمد: {desc} (هزینه: {cost}).",
})

TEXTS["en"].update({
    "help": (
        "Help\n\n"
        "🎮 Create Game: create a new lobby.\n"
        "🔑 Join Game: join a lobby with a 6-character code.\n"
        "🌍 Country: choose an available country (each has a special perk).\n"
        "📋 My Game: show your current game.\n"
        "🎯 Mission: see your secret goal (only you see it).\n"
        "📖 Rules: full explanation of actions and scoring.\n"
        "🚪 /leave: leave your current game (the owner cancels it).\n\n"
        "At least 2 players are required to start."
    ),
    "rules": (
        "Current rules\n\n"
        "• Every player has a country perk and a secret mission (reaching it gives +1500 score).\n"
        f"• The game lasts {MAX_ROUNDS} rounds; each player plays once per round. At the start of a round a world event may hit everyone.\n"
        "• 3 actions per turn (4 with 20+ science).\n\n"
        "Economy & growth:\n"
        "🏭 Build Industry (cost rises with your industry)\n"
        "🔬 Research (every 10 science = tech tier: more income and attack power)\n"
        "💰 Trade (random market; treaties raise profit, sanctions cut it)\n"
        "🏛️ Reform (more stability)\n"
        "🧪 Technology (one-time purchases: Automation, Logistics, Weapons, Fortifications, Medicine, Media, Intelligence, Institutions, Space Program; need science and money)\n\n"
        "Politics & war:\n"
        "🪖 Recruit (each unit costs 5 upkeep per turn)\n"
        "⚔️ Attack (from round 2; the winner loots part of the rival's money)\n"
        "🤝 Diplomacy (3-round treaty: both benefit and attacks between you are blocked)\n"
        "🚫 Sanction (3 rounds: target's trade profit -30% and income -5%; not allowed against treaty partners)\n"
        "🕵️ Espionage (success steals science and shows you the target's stats privately; if caught you lose stability and money)\n\n"
        "• End of turn: base income, army upkeep and sometimes a random event.\n"
        "• Stability above 80 gives a bonus, below 30 cuts income and below 20 causes unrest.\n"
        "• Score = money + industry + science + stability + population + army + mission and Space Program bonuses."
    ),
    "tech": "🧪 Technology",
    "spy": "🕵️ Espionage",
    "sanction": "🚫 Sanction",
    "mission": "🎯 Mission",
    "techs_title": "Technologies",
    "sanctions": "Active sanctions",
    "pick_target_spy": "Who do you want to spy on?",
    "pick_target_sanction": "Who do you want to sanction?",
    "pick_tech": "Choose a technology:",
    "all_techs": "You own every technology ✅",
    "mission_text": "🎯 Your secret mission:\n{title}\nProgress: {cur} / {target}\nReward: +{bonus} score at game end",
    "trade_sanctioned": "(sanctioned: -30% profit)",
    "sanction_exists": "You already sanction this player.",
    "tech_owned": "You already own this technology.",
    "tech_locked": "You don't have enough science for this technology.",
    "bad_tech": "Invalid technology.",
    "res_spy_ok": "🕵️ {attacker}'s spies infiltrated {target} and stole {stolen} science! (success chance: {chance}%)",
    "res_spy_fail": "🕵️ {attacker}'s spies were caught in {target}! {attacker} lost stability and money. (success chance: {chance}%)",
    "res_sanction": "🚫 {attacker} sanctioned {target} until round {until}.",
    "res_tech": "🧪 Technology \"{name}\" acquired: {desc} (cost: {cost}).",
})

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
    # Exclude characters that are easy to mix up at a glance (O/0, I/1),
    # so every one of the 6 characters is unambiguous when read or re-typed.
    alphabet = "".join(c for c in (string.ascii_uppercase + string.digits) if c not in "IO01")
    return "".join(secrets.choice(alphabet) for _ in range(length))


def clean_code(text: str) -> str:
    """Normalise a typed/pasted game code.

    People often copy the code together with the trailing '.' or with invisible
    bidi marks (Persian text), which made a valid code look invalid.
    """
    junk = "\u2066\u2067\u2068\u2069\u200e\u200f\u200c\u200d\u202a\u202b\u202c\u202d\u202e"
    return "".join(
        c for c in text
        if c not in junk and not c.isspace() and c not in ".,:;-_()[]"
    ).upper()


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
            add_column_if_missing(cur, "players", "military", "INTEGER NOT NULL DEFAULT 0")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS treaties (
                    id SERIAL PRIMARY KEY,
                    game_id INTEGER NOT NULL,
                    player_a INTEGER NOT NULL,
                    player_b INTEGER NOT NULL,
                    expires_round INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_treaties_game ON treaties(game_id)")
            add_column_if_missing(cur, "treaties", "kind", "TEXT NOT NULL DEFAULT 'treaty'")
            add_column_if_missing(cur, "players", "techs", "TEXT NOT NULL DEFAULT ''")
            add_column_if_missing(cur, "players", "objective", "TEXT")
            add_column_if_missing(cur, "players", "battles_won", "INTEGER NOT NULL DEFAULT 0")
            add_column_if_missing(cur, "players", "treaties_signed", "INTEGER NOT NULL DEFAULT 0")

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

            # Legacy databases may have games.code as VARCHAR(5): CREATE TABLE IF NOT EXISTS
            # never changes it, so inserting a 6-character code fails. Widen it.
            cur.execute(
                """
                SELECT character_maximum_length AS n
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'games' AND column_name = 'code'
                """
            )
            row = cur.fetchone()
            if row and row["n"] is not None and row["n"] < 6:
                cur.execute("ALTER TABLE games ALTER COLUMN code TYPE VARCHAR(6)")
                logger.warning("Widened games.code from VARCHAR(%s) to VARCHAR(6)", row["n"])

            # Legacy columns we no longer use must not be NOT NULL without a default,
            # otherwise every INSERT fails.
            known = {
                "games": {"id", "code", "owner_id", "status", "total_turn", "current_player_id", "created_at", "updated_at"},
                "players": {"id", "game_id", "user_id", "username", "first_name", "chat_id", "country", "money",
                            "industry", "science", "stability", "population", "actions_left", "score", "joined_at", "military",
                            "techs", "objective", "battles_won", "treaties_signed"},
            }
            for table, cols in known.items():
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                      AND is_nullable = 'NO' AND column_default IS NULL
                    """,
                    (table,),
                )
                for r in cur.fetchall():
                    if r["column_name"] not in cols:
                        cur.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{r["column_name"]}" DROP NOT NULL')
                        logger.warning("Dropped NOT NULL on legacy column %s.%s", table, r["column_name"])

            # Old lobbies whose code is not exactly 6 characters can never be joined
            # and would block their owner from creating a new game. Cancel them.
            cur.execute(
                """
                UPDATE games
                SET status = 'cancelled', updated_at = NOW()
                WHERE status = 'waiting' AND LENGTH(code) <> 6
                """
            )
            if cur.rowcount:
                logger.warning("Cancelled %s legacy lobby(ies) with a malformed code", cur.rowcount)

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
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games WHERE code = %s", (code.upper(),))
            return cur.fetchone()


def get_user_game(user_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT g.*
                FROM games g
                JOIN players p ON p.game_id = g.id
                WHERE p.user_id = %s
                  AND g.status IN ('waiting', 'running')
                ORDER BY g.id DESC
                LIMIT 1
                """,
                (user_id,),
            )
            return cur.fetchone()


def get_players(game_id: int) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM players WHERE game_id = %s ORDER BY id",
                (game_id,),
            )
            return list(cur.fetchall())


def get_player(game_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM players WHERE game_id = %s AND user_id = %s",
                (game_id, user_id),
            )
            return cur.fetchone()


def create_game(user: Dict[str, Any], chat_id: int) -> Dict[str, Any]:
    existing = get_user_game(int(user["id"]))
    if existing:
        raise ValueError("already_in_game")

    with get_conn() as conn:
        with conn.cursor() as cur:
            for _ in range(20):
                code = generate_code()
                try:
                    cur.execute(
                        """
                        INSERT INTO games (code, owner_id, status, total_turn)
                        VALUES (%s, %s, 'waiting', 0)
                        RETURNING *
                        """,
                        (code, int(user["id"])),
                    )
                    game = cur.fetchone()
                    break
                except psycopg.errors.UniqueViolation:
                    conn.rollback()
                    continue
            else:
                raise RuntimeError("Could not generate a unique game code")

            cur.execute(
                """
                INSERT INTO players (
                    game_id, user_id, username, first_name, chat_id,
                    money, industry, science, stability, population,
                    actions_left, score
                )
                VALUES (%s, %s, %s, %s, %s, 1000, 10, 0, 70, 50, 3, 0)
                """,
                (
                    game["id"],
                    int(user["id"]),
                    user.get("username"),
                    user.get("first_name"),
                    chat_id,
                ),
            )
            return game


def join_game(game_id: int, user: Dict[str, Any], chat_id: int):
    existing = get_user_game(int(user["id"]))
    if existing:
        if existing["id"] == game_id:
            raise ValueError("already_in_game")
        raise ValueError("already_in_game")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games WHERE id = %s FOR UPDATE", (game_id,))
            game = cur.fetchone()
            if not game or game["status"] != "waiting":
                raise ValueError("game_not_found")

            cur.execute(
                "SELECT 1 FROM players WHERE game_id = %s AND user_id = %s",
                (game_id, int(user["id"])),
            )
            if cur.fetchone():
                raise ValueError("already_in_game")

            cur.execute("SELECT COUNT(*) AS n FROM players WHERE game_id = %s", (game_id,))
            count = cur.fetchone()["n"]
            if count >= 12:
                raise ValueError("game_full")

            cur.execute(
                """
                INSERT INTO players (
                    game_id, user_id, username, first_name, chat_id,
                    money, industry, science, stability, population,
                    actions_left, score
                )
                VALUES (%s, %s, %s, %s, %s, 1000, 10, 0, 70, 50, 3, 0)
                """,
                (
                    game_id,
                    int(user["id"]),
                    user.get("username"),
                    user.get("first_name"),
                    chat_id,
                ),
            )


def leave_game(user_id: int) -> str:
    """Leave (or, for the owner, cancel) the user's current game.

    Returns one of: 'no_game', 'left', 'cancelled', 'running_not_owner'.
    """
    game = get_user_game(user_id)
    if not game:
        return "no_game"

    is_owner = game.get("owner_id") in (None, user_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            if game["status"] == "waiting":
                if is_owner:
                    cur.execute("DELETE FROM players WHERE game_id = %s", (game["id"],))
                    cur.execute("DELETE FROM games WHERE id = %s", (game["id"],))
                    return "cancelled"
                cur.execute(
                    "DELETE FROM players WHERE game_id = %s AND user_id = %s",
                    (game["id"], user_id),
                )
                return "left"

            # running game: only the owner may stop it, otherwise turn order would break
            if not is_owner:
                return "running_not_owner"
            cur.execute(
                "UPDATE games SET status = 'cancelled', updated_at = NOW() WHERE id = %s",
                (game["id"],),
            )
            return "cancelled"


def choose_country(game_id: int, user_id: int, code: str) -> bool:
    code = code.upper()
    if code not in COUNTRIES:
        return False

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM games WHERE id = %s", (game_id,))
            game = cur.fetchone()
            if not game or game["status"] != "waiting":
                return False

            cur.execute(
                "SELECT 1 FROM players WHERE game_id = %s AND country = %s AND user_id <> %s",
                (game_id, code, user_id),
            )
            if cur.fetchone():
                raise ValueError("country_taken")

            stats = COUNTRIES[code]
            cur.execute(
                """
                UPDATE players
                SET country = %s,
                    industry = %s,
                    science = %s,
                    stability = %s,
                    population = %s,
                    military = %s
                WHERE game_id = %s AND user_id = %s
                """,
                (
                    code,
                    stats["industry"],
                    stats["science"],
                    stats["stability"],
                    stats["population"],
                    COUNTRY_MILITARY.get(code, 5),
                    game_id,
                    user_id,
                ),
            )
            return cur.rowcount > 0


def start_game(game_id: int, user_id: int) -> Dict[str, Any]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games WHERE id = %s FOR UPDATE", (game_id,))
            game = cur.fetchone()
            if not game:
                raise ValueError("game_not_found")
            if game["owner_id"] != user_id:
                raise ValueError("not_owner")
            if game["status"] != "waiting":
                raise ValueError("not_running")

            cur.execute("SELECT * FROM players WHERE game_id = %s ORDER BY id", (game_id,))
            players = list(cur.fetchall())
            if len(players) < 2:
                raise ValueError("need_players")
            if any(not p.get("country") for p in players):
                raise ValueError("need_country")

            first_player = players[0]
            cur.execute(
                """
                UPDATE games
                SET status = 'running',
                    total_turn = 1,
                    current_player_id = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (first_player["id"], game_id),
            )
            cur.execute(
                "UPDATE players SET actions_left = 3 WHERE game_id = %s",
                (game_id,),
            )
            mission_keys = list(OBJECTIVES.keys())
            random.shuffle(mission_keys)
            for i, pl in enumerate(players):
                cur.execute(
                    "UPDATE players SET objective = %s WHERE id = %s",
                    (mission_keys[i % len(mission_keys)], pl["id"]),
                )
            return first_player


# ============================================================
# GAME ENGINE (v4: techs, espionage, sanctions, secret missions, world events)
# ============================================================

COUNTRY_MILITARY = {
    "IR": 8, "US": 16, "CN": 15, "DE": 9, "FR": 10, "TR": 10,
    "JP": 7, "IN": 12, "BR": 6, "CA": 6, "EG": 7, "KR": 10,
}

COUNTRY_PERKS = {
    "IR": {"mods": {"defense_pct": 15}, "fa": "دفاع مقاوم: +۱۵٪ قدرت دفاعی", "en": "Resilient defense: +15% defense strength"},
    "US": {"mods": {"trade_pct": 20}, "fa": "اقتصاد بازار: +۲۰٪ درآمد تجارت", "en": "Market economy: +20% trade income"},
    "CN": {"mods": {"build_bonus": 1}, "fa": "کارخانه جهان: هر ساخت صنعت ۱ واحد اضافه می‌دهد", "en": "World factory: +1 extra industry per build"},
    "DE": {"mods": {"research_discount_pct": 20}, "fa": "مهندسی دقیق: ۲۰٪ تخفیف هزینه تحقیق", "en": "Precision engineering: 20% cheaper research"},
    "FR": {"mods": {"diplo_stab": 3}, "fa": "دیپلماسی قوی: ۳ ثبات اضافه از هر پیمان", "en": "Strong diplomacy: +3 extra stability from treaties"},
    "TR": {"mods": {"recruit_bonus": 1}, "fa": "نیروی کارآمد: هر جذب نیرو ۱ واحد اضافه می‌دهد", "en": "Efficient army: +1 extra unit per recruit"},
    "JP": {"mods": {"research_bonus": 1}, "fa": "نوآوری: هر تحقیق ۱ علم اضافه می‌دهد", "en": "Innovation: +1 extra science per research"},
    "IN": {"mods": {"pop_turn": 2}, "fa": "رشد جمعیت: ۲ جمعیت اضافه در پایان هر نوبت", "en": "Population boom: +2 population each turn end"},
    "BR": {"mods": {"income_pct": 8}, "fa": "منابع طبیعی: ۸٪ درآمد بیشتر در پایان نوبت", "en": "Natural resources: +8% end-of-turn income"},
    "CA": {"mods": {"stab_turn": 1}, "fa": "جامعه باثبات: ۱ ثبات اضافه در پایان هر نوبت", "en": "Stable society: +1 stability each turn end"},
    "EG": {"mods": {"trade_pct": 15}, "fa": "موقعیت تجاری: +۱۵٪ درآمد تجارت", "en": "Trade crossroads: +15% trade income"},
    "KR": {"mods": {"income_pct": 6}, "fa": "صادرات فناوری: ۶٪ درآمد بیشتر در پایان نوبت", "en": "Tech exports: +6% end-of-turn income"},
}

# One-time technologies. Bought with an action; need enough science AND money.
TECHS = {
    "automation": {"cost": 450, "science": 8, "mods": {"income_pct": 10},
                   "fa": "اتوماسیون", "en": "Automation",
                   "desc_fa": "+۱۰٪ درآمد پایان نوبت", "desc_en": "+10% end-of-turn income"},
    "logistics": {"cost": 350, "science": 6, "mods": {"trade_pct": 15},
                  "fa": "لجستیک", "en": "Logistics",
                  "desc_fa": "+۱۵٪ درآمد تجارت", "desc_en": "+15% trade income"},
    "weapons": {"cost": 500, "science": 10, "mods": {"attack_pct": 15},
                "fa": "تسلیحات پیشرفته", "en": "Advanced Weapons",
                "desc_fa": "+۱۵٪ قدرت حمله", "desc_en": "+15% attack power"},
    "fortify": {"cost": 500, "science": 10, "mods": {"defense_pct": 15},
                "fa": "استحکامات", "en": "Fortifications",
                "desc_fa": "+۱۵٪ قدرت دفاع", "desc_en": "+15% defense power"},
    "medicine": {"cost": 400, "science": 8, "mods": {"pop_turn": 1},
                 "fa": "پزشکی مدرن", "en": "Modern Medicine",
                 "desc_fa": "۱ جمعیت اضافه در پایان هر نوبت", "desc_en": "+1 population each turn end"},
    "media": {"cost": 400, "science": 8, "mods": {"stab_turn": 1},
              "fa": "رسانه ملی", "en": "State Media",
              "desc_fa": "۱ ثبات اضافه در پایان هر نوبت", "desc_en": "+1 stability each turn end"},
    "intel": {"cost": 450, "science": 12, "mods": {"spy_pct": 20},
              "fa": "سازمان اطلاعات", "en": "Intelligence Agency",
              "desc_fa": "+۲۰٪ شانس موفقیت جاسوسی", "desc_en": "+20% espionage success"},
    "institutions": {"cost": 350, "science": 6, "mods": {"diplo_stab": 3, "treaty_extra": 1},
                     "fa": "نهادهای بین‌المللی", "en": "Institutions",
                     "desc_fa": "پیمان‌ها ۱ دوره بیشتر دوام دارند و ۳ ثبات اضافه می‌دهند",
                     "desc_en": "Treaties last 1 round longer and give +3 stability"},
    "space": {"cost": 1000, "science": 30, "mods": {"score_bonus": 500},
              "fa": "برنامه فضایی", "en": "Space Program",
              "desc_fa": "+۵۰۰ امتیاز در پایان بازی", "desc_en": "+500 score at game end"},
}

# Secret missions: hidden goal, +OBJECTIVE_BONUS score if reached by the end.
OBJECTIVE_BONUS = 1500
OBJECTIVES = {
    "industrialist": {"stat": lambda p: p["industry"], "target": 40,
                      "fa": "صنعتگر: به صنعت ۴۰ برس", "en": "Industrialist: reach 40 industry"},
    "warlord": {"stat": lambda p: p.get("battles_won") or 0, "target": 3,
                "fa": "فاتح: ۳ نبرد را ببر", "en": "Warlord: win 3 battles"},
    "scientist": {"stat": lambda p: p["science"], "target": 40,
                  "fa": "دانشمند: به علم ۴۰ برس", "en": "Scientist: reach 40 science"},
    "diplomat": {"stat": lambda p: p.get("treaties_signed") or 0, "target": 3,
                 "fa": "دیپلمات: ۳ پیمان امضا کن", "en": "Diplomat: sign 3 treaties"},
    "tycoon": {"stat": lambda p: p["money"], "target": 8000,
               "fa": "سرمایه‌دار: ۸۰۰۰ پول جمع کن", "en": "Tycoon: hold 8000 money"},
    "stable": {"stat": lambda p: p["stability"], "target": 90,
               "fa": "آرامش: ثبات ۹۰ یا بیشتر", "en": "Harmony: stability of 90+"},
    "superpower": {"stat": lambda p: p.get("military") or 0, "target": 30,
                   "fa": "ابرقدرت: ارتش ۳۰ واحدی بساز", "en": "Superpower: build a 30-unit army"},
    "populous": {"stat": lambda p: p["population"], "target": 150,
                 "fa": "پرجمعیت: جمعیت ۱۵۰ یا بیشتر", "en": "Populous: reach 150 population"},
}

# Global events that can hit every player when a new round begins.
WORLD_EVENTS = [
    {"key": "recession", "w": 2, "money_pct": -8,
     "fa": "📉 رکود جهانی! همه ۸٪ از پولشان را از دست دادند.", "en": "📉 Global recession! Everyone lost 8% of their money."},
    {"key": "boom", "w": 2, "money_pct": 8,
     "fa": "📈 رونق جهانی! همه ۸٪ پول اضافه گرفتند.", "en": "📈 Global boom! Everyone gained 8% money."},
    {"key": "pandemic", "w": 1, "population_pct": -6, "stability": -2,
     "fa": "🦠 همه‌گیری جهانی! جمعیت و ثبات همه کم شد.", "en": "🦠 Global pandemic! Everyone lost population and stability."},
    {"key": "tech_boom", "w": 2, "science": 1,
     "fa": "🔭 جهش فناوری! همه ۱ علم گرفتند.", "en": "🔭 Tech boom! Everyone gained 1 science."},
    {"key": "arms_race", "w": 1, "military": 1, "stability": -1,
     "fa": "🚀 مسابقه تسلیحاتی! همه ۱ واحد نظامی گرفتند ولی ثبات کمی افت کرد.", "en": "🚀 Arms race! Everyone gained 1 military unit but lost a bit of stability."},
    {"key": "summit", "w": 1, "stability": 3,
     "fa": "🕊️ اجلاس صلح! ثبات همه بالا رفت.", "en": "🕊️ Peace summit! Everyone's stability rose."},
]
WORLD_EVENT_BY_KEY = {e["key"]: e for e in WORLD_EVENTS}
WORLD_EVENT_CHANCE = 0.5

# Random events that can hit a player at the end of their turn.
EVENTS = [
    {"key": "harvest", "w": 3, "population": 2, "stability": 2,
     "fa": "🌾 برداشت پربار! جمعیت و ثبات بالا رفت.", "en": "🌾 Bumper harvest! Population and stability rose."},
    {"key": "strike", "w": 2, "money": -120, "stability": -3,
     "fa": "🛠️ اعتصاب کارگری! مقداری پول و ثبات از دست رفت.", "en": "🛠️ Workers' strike! Some money and stability were lost."},
    {"key": "breakthrough", "w": 2, "science": 2,
     "fa": "💡 پیشرفت علمی! ۲ علم اضافه شد.", "en": "💡 Scientific breakthrough! +2 science."},
    {"key": "crisis", "w": 2, "money_pct": -12, "stability": -4,
     "fa": "📉 بحران اقتصادی! ۱۲٪ پول از دست رفت.", "en": "📉 Economic crisis! 12% of the treasury was lost."},
    {"key": "oil", "w": 2, "money": 250,
     "fa": "🛢️ کشف منبع جدید! ۲۵۰ پول به خزانه اضافه شد.", "en": "🛢️ New resource discovered! +250 money."},
    {"key": "protests", "w": 2, "stability": -7,
     "fa": "✊ اعتراضات عمومی! ثبات کاهش یافت.", "en": "✊ Mass protests! Stability dropped."},
    {"key": "disaster", "w": 1, "population": -3, "industry": -1,
     "fa": "🌪️ بلای طبیعی! جمعیت و صنعت آسیب دید.", "en": "🌪️ Natural disaster! Population and industry suffered."},
    {"key": "investment", "w": 2, "money": 150, "industry": 1,
     "fa": "🏦 سرمایه‌گذاری خارجی! پول و صنعت افزایش یافت.", "en": "🏦 Foreign investment! Money and industry rose."},
    {"key": "arms_deal", "w": 1, "military": 2, "money": -100,
     "fa": "🪖 قرارداد تسلیحاتی! ۲ واحد نظامی با ۱۰۰ پول خریداری شد.", "en": "🪖 Arms deal! +2 military for 100 money."},
]
EVENT_BY_KEY = {e["key"]: e for e in EVENTS}
EVENT_CHANCE = 0.45

TARGET_ACTIONS = ("attack", "diplomacy", "spy", "sanction")
SIMPLE_ACTIONS = ("build", "research", "trade", "recruit", "welfare")


def esc(value: Any) -> str:
    return html_lib.escape(str(value))


def pname(p: Dict[str, Any]) -> str:
    return esc(p.get("first_name") or p.get("username") or "Player")


def perk_value(country: Optional[str], key: str) -> int:
    return COUNTRY_PERKS.get(country or "", {}).get("mods", {}).get(key, 0)


def perk_text(country: Optional[str], language: str) -> str:
    perk = COUNTRY_PERKS.get(country or "")
    return perk[language] if perk else "-"


def owned_techs(p: Dict[str, Any]) -> List[str]:
    return [k for k in (p.get("techs") or "").split(",") if k in TECHS]


def mod_value(p: Dict[str, Any], key: str) -> int:
    """Country perk + owned technologies for one modifier."""
    total = perk_value(p.get("country"), key)
    for k in owned_techs(p):
        total += TECHS[k]["mods"].get(key, 0)
    return total


def objective_progress(p: Dict[str, Any]):
    obj = OBJECTIVES.get(p.get("objective") or "")
    if not obj:
        return None
    return int(obj["stat"](p)), obj["target"]


def tech_tier(science: int) -> int:
    """Every 10 science = one tech tier (max 5)."""
    return min(5, max(0, int(science)) // 10)


def max_actions(science: int) -> int:
    return BASE_ACTIONS + (1 if science >= 20 else 0)


def current_round(total_turn: int, player_count: int) -> int:
    return (max(int(total_turn), 1) - 1) // max(int(player_count), 1) + 1


def calculate_score_values(money: int, industry: int, science: int, stability: int, population: int, military: int = 0) -> int:
    return (
        max(0, money) + industry * 50 + science * 100
        + stability * 10 + population * 5 + military * 40
    )


def action_cost(action: str, p: Dict[str, Any]) -> int:
    if action == "build":
        return 150 + 10 * p["industry"]
    if action == "research":
        base = 100 + 8 * p["science"]
        return int(base * (100 - mod_value(p, "research_discount_pct")) / 100)
    costs = {"recruit": 250, "welfare": 150, "diplomacy": 100, "attack": 150,
             "spy": 120, "sanction": 80, "trade": 0}
    if action in costs:
        return costs[action]
    raise ValueError("unknown_action")


def _norm(p: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Fill defaults for rows created before newer columns existed."""
    if p is None:
        return None
    for key in ("military", "battles_won", "treaties_signed"):
        if p.get(key) is None:
            p[key] = 0
    if p.get("techs") is None:
        p["techs"] = ""
    return p


def _save_player(cur, p: Dict[str, Any]):
    """Clamp stats, recompute score and persist a player row."""
    _norm(p)
    p["money"] = max(0, int(p["money"]))
    p["industry"] = max(1, int(p["industry"]))
    p["science"] = max(0, int(p["science"]))
    p["stability"] = max(0, min(100, int(p["stability"])))
    p["population"] = max(1, int(p["population"]))
    p["military"] = max(0, int(p["military"]))
    p["actions_left"] = max(0, int(p["actions_left"]))
    p["score"] = calculate_score_values(
        p["money"], p["industry"], p["science"], p["stability"], p["population"], p["military"]
    )
    cur.execute(
        """
        UPDATE players
        SET money = %s, industry = %s, science = %s, stability = %s,
            population = %s, military = %s, actions_left = %s, score = %s,
            techs = %s, battles_won = %s, treaties_signed = %s
        WHERE id = %s
        """,
        (
            p["money"], p["industry"], p["science"], p["stability"],
            p["population"], p["military"], p["actions_left"], p["score"],
            p["techs"], p["battles_won"], p["treaties_signed"], p["id"],
        ),
    )


def _lock_turn(cur, game_id: int, user_id: int):
    cur.execute("SELECT * FROM games WHERE id = %s FOR UPDATE", (game_id,))
    game = cur.fetchone()
    if not game or game["status"] != "running":
        raise ValueError("not_running")

    cur.execute(
        "SELECT * FROM players WHERE id = %s AND game_id = %s FOR UPDATE",
        (game["current_player_id"], game_id),
    )
    current = cur.fetchone()
    if not current or current["user_id"] != user_id:
        name = "Player"
        if current:
            name = current.get("first_name") or current.get("username") or "Player"
        raise ValueError(f"not_your_turn:{name}")
    return game, _norm(current)


def _get_target(cur, game_id: int, player_id: int, target_id: int) -> Dict[str, Any]:
    cur.execute(
        "SELECT * FROM players WHERE id = %s AND game_id = %s FOR UPDATE",
        (target_id, game_id),
    )
    d = cur.fetchone()
    if not d or d["id"] == player_id:
        raise ValueError("bad_target")
    return _norm(d)


def _pay(p: Dict[str, Any], cost: int):
    if p["actions_left"] <= 0:
        raise ValueError("not_enough_actions")
    if p["money"] < cost:
        raise ValueError(f"not_enough_money:{p['money']}")


def _round_of(cur, game: Dict[str, Any]) -> int:
    cur.execute("SELECT COUNT(*) AS n FROM players WHERE game_id = %s", (game["id"],))
    n = cur.fetchone()["n"]
    return current_round(game["total_turn"], n)


def _treaty_between(cur, game_id: int, a: int, b: int, rnd: int) -> bool:
    lo, hi = min(a, b), max(a, b)
    cur.execute(
        """
        SELECT 1 FROM treaties
        WHERE game_id = %s AND kind = 'treaty' AND player_a = %s AND player_b = %s AND expires_round >= %s
        """,
        (game_id, lo, hi, rnd),
    )
    return cur.fetchone() is not None


def _treaty_count(cur, game_id: int, player_id: int, rnd: int) -> int:
    cur.execute(
        """
        SELECT COUNT(*) AS n FROM treaties
        WHERE game_id = %s AND kind = 'treaty' AND expires_round >= %s AND (player_a = %s OR player_b = %s)
        """,
        (game_id, rnd, player_id, player_id),
    )
    return int(cur.fetchone()["n"])


def _sanction_count_on(cur, game_id: int, player_id: int, rnd: int) -> int:
    cur.execute(
        """
        SELECT COUNT(*) AS n FROM treaties
        WHERE game_id = %s AND kind = 'sanction' AND expires_round >= %s AND player_b = %s
        """,
        (game_id, rnd, player_id),
    )
    return int(cur.fetchone()["n"])


def _sanction_exists(cur, game_id: int, imposer: int, target: int, rnd: int) -> bool:
    cur.execute(
        """
        SELECT 1 FROM treaties
        WHERE game_id = %s AND kind = 'sanction' AND player_a = %s AND player_b = %s AND expires_round >= %s
        """,
        (game_id, imposer, target, rnd),
    )
    return cur.fetchone() is not None


def resolve_battle(attacker: Dict[str, Any], defender: Dict[str, Any], rng=random) -> Dict[str, Any]:
    """Pure combat resolution. Mutates the two player dicts (not the money cost)."""
    tier = tech_tier(attacker["science"])
    atk = (
        attacker["military"]
        * (1 + 0.08 * tier + mod_value(attacker, "attack_pct") / 100)
        * rng.uniform(0.85, 1.15)
    )
    dfn = (
        (defender["military"] * 1.15 + defender["industry"] * 0.2)
        * (1 + mod_value(defender, "defense_pct") / 100)
        * rng.uniform(0.85, 1.15)
    )
    win = atk > dfn
    loot = 0
    if win:
        loot = min(400, int(defender["money"] * 0.15))
        attacker["money"] += loot
        attacker["military"] -= 1
        attacker["stability"] -= 2
        attacker["battles_won"] = (attacker.get("battles_won") or 0) + 1
        defender["money"] -= loot
        defender["industry"] -= 1
        defender["population"] -= 2
        defender["stability"] -= 6
        defender["military"] -= 1
    else:
        attacker["military"] -= 2
        attacker["stability"] -= 4
        defender["stability"] += 2
    return {"win": win, "loot": loot, "atk": int(round(atk * 10)), "dfn": int(round(dfn * 10))}


def resolve_spy(attacker: Dict[str, Any], defender: Dict[str, Any], rng=random) -> Dict[str, Any]:
    """Pure espionage resolution. Mutates the two player dicts (not the money cost)."""
    chance = 0.5 + 0.06 * (tech_tier(attacker["science"]) - tech_tier(defender["science"]))
    chance += mod_value(attacker, "spy_pct") / 100
    chance = max(0.15, min(0.9, chance))
    success = rng.random() < chance
    stolen = 0
    if success:
        stolen = min(3, defender["science"])
        attacker["science"] += stolen
        defender["science"] -= stolen
        defender["stability"] -= 2
    else:
        attacker["stability"] -= 5
        attacker["money"] -= 50
        defender["stability"] += 1
    return {"success": success, "stolen": stolen, "chance": int(round(chance * 100))}


def settle_turn_end(current: Dict[str, Any], rng=random, sanctions: int = 0) -> Dict[str, Any]:
    """Pure end-of-turn economy. Mutates `current` and returns a report."""
    tier = tech_tier(current["science"])

    gross = 100 + current["industry"] * 10 + current["population"] * 2
    mult = 1 + 0.05 * tier + mod_value(current, "income_pct") / 100
    if current["stability"] >= 80:
        mult += 0.10
    elif current["stability"] < 30:
        mult -= 0.30
    mult -= 0.05 * min(3, sanctions)
    income = int(gross * max(0.3, mult))
    upkeep = current["military"] * 5
    current["money"] += income - upkeep

    food_effect = max(-3, min(3, (current["industry"] // 5) - 2))
    growth = 1 + food_effect + mod_value(current, "pop_turn")
    if current["stability"] < 30:
        growth = min(growth, 0)
    current["population"] = max(1, current["population"] + growth)
    current["stability"] += (1 if current["money"] >= 1000 else -1) + mod_value(current, "stab_turn")

    event_key = None
    if rng.random() < EVENT_CHANCE:
        event = rng.choices(EVENTS, weights=[e["w"] for e in EVENTS], k=1)[0]
        event_key = event["key"]
        current["money"] += event.get("money", 0)
        current["money"] += int(current["money"] * event.get("money_pct", 0) / 100)
        for stat in ("industry", "science", "stability", "population", "military"):
            current[stat] += event.get(stat, 0)

    unrest = current["stability"] < 20
    if unrest:
        current["money"] -= int(current["money"] * 0.10)
        current["industry"] -= 1

    current["actions_left"] = max_actions(current["science"])
    return {"income": income, "upkeep": upkeep, "event": event_key, "unrest": unrest}


def apply_world_event(players: List[Dict[str, Any]], rng=random) -> Optional[str]:
    """Pick a world event and apply it to every player dict in place."""
    event = rng.choices(WORLD_EVENTS, weights=[e["w"] for e in WORLD_EVENTS], k=1)[0]
    for p in players:
        p["money"] += int(p["money"] * event.get("money_pct", 0) / 100)
        p["population"] += int(p["population"] * event.get("population_pct", 0) / 100)
        for stat in ("science", "stability", "military"):
            p[stat] += event.get(stat, 0)
    return event["key"]


def final_score(p: Dict[str, Any]) -> Dict[str, Any]:
    """Final score including secret mission and tech bonuses."""
    base = calculate_score_values(
        p["money"], p["industry"], p["science"], p["stability"], p["population"], p.get("military") or 0
    )
    done = False
    obj = OBJECTIVES.get(p.get("objective") or "")
    if obj and obj["stat"](p) >= obj["target"]:
        done = True
        base += OBJECTIVE_BONUS
    base += mod_value(p, "score_bonus")
    return {"score": base, "objective_done": done}


def action_for_player(game_id: int, user_id: int, action: str):
    """Non-targeted actions. Returns (updated_player, info)."""
    if action not in SIMPLE_ACTIONS:
        raise ValueError("unknown_action")

    with get_conn() as conn:
        with conn.cursor() as cur:
            game, p = _lock_turn(cur, game_id, user_id)
            cost = action_cost(action, p)
            _pay(p, cost)

            info: Dict[str, Any] = {"action": action, "cost": cost}
            p["money"] -= cost

            if action == "build":
                gain = 2 + mod_value(p, "build_bonus")
                p["industry"] += gain
                p["population"] += 1
                info["n"] = gain
            elif action == "research":
                gain = 3 + mod_value(p, "research_bonus")
                p["science"] += gain
                info["n"] = gain
            elif action == "trade":
                rnd = _round_of(cur, game)
                partners = _treaty_count(cur, game_id, p["id"], rnd)
                sanctions = _sanction_count_on(cur, game_id, p["id"], rnd)
                market = random.uniform(0.8, 1.25)
                base = 150 + p["industry"] * 6 + 40 * partners
                gain = base * market * (1 + mod_value(p, "trade_pct") / 100)
                if sanctions:
                    gain *= 0.7
                gain = int(gain)
                p["money"] += gain
                p["stability"] -= 1
                info["gain"] = gain
                info["market"] = f"{int(round((market - 1) * 100)):+d}%"
                info["partners"] = partners
                info["sanctions"] = sanctions
            elif action == "recruit":
                gain = 3 + mod_value(p, "recruit_bonus")
                p["military"] += gain
                info["n"] = gain
            elif action == "welfare":
                p["stability"] += 8
                p["population"] += 1
                info["n"] = 8

            p["actions_left"] -= 1
            _save_player(cur, p)
            return p, info


def buy_tech(game_id: int, user_id: int, key: str):
    if key not in TECHS:
        raise ValueError("bad_tech")
    tech = TECHS[key]
    with get_conn() as conn:
        with conn.cursor() as cur:
            game, p = _lock_turn(cur, game_id, user_id)
            owned = owned_techs(p)
            if key in owned:
                raise ValueError("tech_owned")
            if p["science"] < tech["science"]:
                raise ValueError("tech_locked")
            _pay(p, tech["cost"])

            p["money"] -= tech["cost"]
            p["techs"] = ",".join(owned + [key])
            p["actions_left"] -= 1
            _save_player(cur, p)
            return p, {"action": "tech", "cost": tech["cost"], "key": key}


def get_turn_player(game_id: int, user_id: int) -> Dict[str, Any]:
    """The caller's player row (also validates that it is the caller's turn)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            _, p = _lock_turn(cur, game_id, user_id)
            return p


def get_targets(game_id: int, user_id: int) -> List[Dict[str, Any]]:
    """Other players in the game (also validates that it is the caller's turn)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            _, p = _lock_turn(cur, game_id, user_id)
            cur.execute(
                "SELECT * FROM players WHERE game_id = %s AND id <> %s ORDER BY id",
                (game_id, p["id"]),
            )
            return list(cur.fetchall())


def attack_player(game_id: int, user_id: int, target_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            game, p = _lock_turn(cur, game_id, user_id)
            cost = action_cost("attack", p)
            _pay(p, cost)
            d = _get_target(cur, game_id, p["id"], target_id)

            rnd = _round_of(cur, game)
            if rnd < 2:
                raise ValueError("too_early")
            if p["military"] < 1:
                raise ValueError("no_military")
            if _treaty_between(cur, game_id, p["id"], d["id"], rnd):
                raise ValueError("treaty_active")

            p["money"] -= cost
            p["actions_left"] -= 1
            result = resolve_battle(p, d)
            _save_player(cur, p)
            _save_player(cur, d)

            info = {"action": "attack", "cost": cost, "attacker": pname(p), "defender": pname(d), **result}
            return p, d, info


def sign_treaty(game_id: int, user_id: int, target_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            game, p = _lock_turn(cur, game_id, user_id)
            cost = action_cost("diplomacy", p)
            _pay(p, cost)
            d = _get_target(cur, game_id, p["id"], target_id)

            rnd = _round_of(cur, game)
            if _treaty_between(cur, game_id, p["id"], d["id"], rnd):
                raise ValueError("treaty_exists")

            until = rnd + 2 + mod_value(p, "treaty_extra")
            cur.execute(
                "INSERT INTO treaties (game_id, player_a, player_b, expires_round, kind) VALUES (%s, %s, %s, %s, 'treaty')",
                (game_id, min(p["id"], d["id"]), max(p["id"], d["id"]), until),
            )

            p["money"] += 60 - cost
            p["stability"] += 3 + mod_value(p, "diplo_stab")
            p["actions_left"] -= 1
            p["treaties_signed"] += 1
            d["money"] += 60
            d["stability"] += 3
            d["treaties_signed"] += 1
            _save_player(cur, p)
            _save_player(cur, d)

            info = {"action": "diplomacy", "cost": cost, "attacker": pname(p), "target": pname(d), "until": until}
            return p, d, info


def spy_on(game_id: int, user_id: int, target_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            game, p = _lock_turn(cur, game_id, user_id)
            cost = action_cost("spy", p)
            _pay(p, cost)
            d = _get_target(cur, game_id, p["id"], target_id)

            p["money"] -= cost
            p["actions_left"] -= 1
            result = resolve_spy(p, d)
            _save_player(cur, p)
            _save_player(cur, d)

            info = {"action": "spy", "cost": cost, "attacker": pname(p), "target": pname(d), **result}
            return p, d, info


def impose_sanction(game_id: int, user_id: int, target_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            game, p = _lock_turn(cur, game_id, user_id)
            cost = action_cost("sanction", p)
            _pay(p, cost)
            d = _get_target(cur, game_id, p["id"], target_id)

            rnd = _round_of(cur, game)
            if _treaty_between(cur, game_id, p["id"], d["id"], rnd):
                raise ValueError("treaty_active")
            if _sanction_exists(cur, game_id, p["id"], d["id"], rnd):
                raise ValueError("sanction_exists")

            until = rnd + 2
            cur.execute(
                "INSERT INTO treaties (game_id, player_a, player_b, expires_round, kind) VALUES (%s, %s, %s, %s, 'sanction')",
                (game_id, p["id"], d["id"], until),
            )

            p["money"] -= cost
            p["stability"] -= 1
            p["actions_left"] -= 1
            d["stability"] -= 2
            _save_player(cur, p)
            _save_player(cur, d)

            info = {"action": "sanction", "cost": cost, "attacker": pname(p), "target": pname(d), "until": until}
            return p, d, info


def get_or_assign_objective(game_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """The caller's player row; assigns a secret mission if the game predates them."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM players WHERE game_id = %s AND user_id = %s", (game_id, user_id))
            p = cur.fetchone()
            if not p:
                return None
            _norm(p)
            if not p.get("objective") or p["objective"] not in OBJECTIVES:
                p["objective"] = random.choice(list(OBJECTIVES.keys()))
                cur.execute("UPDATE players SET objective = %s WHERE id = %s", (p["objective"], p["id"]))
            return p


def end_turn(game_id: int, user_id: int) -> Dict[str, Any]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            game, current = _lock_turn(cur, game_id, user_id)

            rnd_before = _round_of(cur, game)
            sanctions = _sanction_count_on(cur, game_id, current["id"], rnd_before)
            report = settle_turn_end(current, sanctions=sanctions)
            _save_player(cur, current)

            cur.execute("SELECT * FROM players WHERE game_id = %s ORDER BY id", (game_id,))
            players = [_norm(x) for x in cur.fetchall()]
            n = len(players)

            total_turn = game["total_turn"] + 1
            if total_turn > MAX_ROUNDS * n:
                for x in players:
                    fin = final_score(x)
                    x["score"] = fin["score"]
                    x["objective_done"] = fin["objective_done"]
                    cur.execute("UPDATE players SET score = %s WHERE id = %s", (x["score"], x["id"]))
                cur.execute(
                    "UPDATE games SET status = 'finished', total_turn = %s, current_player_id = NULL, updated_at = NOW() WHERE id = %s",
                    (total_turn, game_id),
                )
                results = sorted(players, key=lambda x: (-x["score"], x["id"]))
                return {"finished": True, "turn": total_turn, "results": results, **report}

            new_round = current_round(total_turn, n)
            world_event = None
            if new_round > rnd_before and random.random() < WORLD_EVENT_CHANCE:
                world_event = apply_world_event(players)
                for x in players:
                    _save_player(cur, x)

            current_index = next(i for i, x in enumerate(players) if x["id"] == current["id"])
            next_player = players[(current_index + 1) % n]

            cur.execute(
                """
                UPDATE games
                SET total_turn = %s, current_player_id = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (total_turn, next_player["id"], game_id),
            )
            return {
                "finished": False,
                "turn": total_turn,
                "round": new_round,
                "next_player": next_player,
                "ended_player": current,
                "world_event": world_event,
                **report,
            }


# ============================================================
# FORMAT GAME
# ============================================================


def format_players(players: List[Dict[str, Any]], language: str) -> str:
    lines = []
    for i, p in enumerate(players, start=1):
        name = esc(p.get("first_name") or (f"@{p['username']}" if p.get("username") else f"Player {i}"))
        country = country_name(p.get("country"), language)
        lines.append(f"{i}. {name} — {country}")
    return "\n".join(lines) if lines else "-"


def format_game(game_id: int, language: str) -> str:
    T = TEXTS[language]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games WHERE id = %s", (game_id,))
            game = cur.fetchone()
            if not game:
                return "Game not found."

            cur.execute("SELECT * FROM players WHERE game_id = %s ORDER BY id", (game_id,))
            players = list(cur.fetchall())

            pacts = []
            if game["status"] == "running":
                rnd = current_round(game["total_turn"], len(players))
                cur.execute(
                    "SELECT * FROM treaties WHERE game_id = %s AND expires_round >= %s ORDER BY id",
                    (game_id, rnd),
                )
                pacts = list(cur.fetchall())

    text = []
    status_key = game["status"]
    status_label = T.get(status_key, status_key)
    text.append(f"🎮 <b>{T['lobby'] if status_key == 'waiting' else T['running']}</b>")
    text.append(f"<b>Code:</b> \u2066<code>{game['code']}</code>\u2069")
    text.append(f"<b>Status:</b> {status_label}")
    text.append(f"<b>{T['players_title']}:</b> {len(players)} / 12")

    if status_key == "running":
        rnd = current_round(game["total_turn"], len(players))
        text.append(f"<b>{T['round']}:</b> {rnd} / {MAX_ROUNDS}  ({T['turn']} {game['total_turn']})")
        if game.get("current_player_id"):
            current = next((p for p in players if p["id"] == game["current_player_id"]), None)
            if current:
                text.append(f"<b>Current:</b> {pname(current)}")

    text.append("")
    if status_key == "running":
        def live_score(p):
            return calculate_score_values(
                p["money"], p["industry"], p["science"], p["stability"], p["population"], p.get("military") or 0
            )

        text.append(f"🏆 <b>{T['scoreboard']}</b>")
        ranked = sorted(players, key=lambda p: (-live_score(p), p["id"]))
        for i, p in enumerate(ranked, start=1):
            text.append(
                f"{i}. {pname(p)} — {country_name(p.get('country'), language)}"
                f" | 🏆 {live_score(p)} | 🪖 {p.get('military') or 0} | 🔬 T{tech_tier(p['science'])}"
                f" | 🧪 {len(owned_techs(p))}"
            )

        by_id = {p["id"]: p for p in players}
        treaty_lines, sanction_lines = [], []
        for pact in pacts:
            a, b = by_id.get(pact["player_a"]), by_id.get(pact["player_b"])
            if not (a and b):
                continue
            if (pact.get("kind") or "treaty") == "sanction":
                sanction_lines.append(f"{pname(a)} → {pname(b)} ({T['until_round']} {pact['expires_round']})")
            else:
                treaty_lines.append(f"{pname(a)} ↔ {pname(b)} ({T['until_round']} {pact['expires_round']})")
        if treaty_lines:
            text.append("")
            text.append(f"🤝 <b>{T['treaties']}</b>")
            text.extend(treaty_lines)
        if sanction_lines:
            text.append("")
            text.append(f"🚫 <b>{T['sanctions']}</b>")
            text.extend(sanction_lines)
    else:
        text.append(format_players(players, language))
    return "\n".join(text)


def format_player_stats(player: Dict[str, Any], language: str) -> str:
    T = TEXTS[language]
    country = player.get("country")
    tier = tech_tier(player["science"])
    techs = ", ".join(TECHS[k][language] for k in owned_techs(player)) or "-"
    return (
        f"🌍 <b>{country_name(country, language)}</b>\n"
        f"✨ {T['perk']}: {perk_text(country, language)}\n"
        f"💰 {T['money']}: <b>{player['money']}</b>\n"
        f"🏭 {T['industry']}: <b>{player['industry']}</b>\n"
        f"🔬 {T['science']}: <b>{player['science']}</b> ({T['tier']} {tier})\n"
        f"🛡️ {T['stability']}: <b>{player['stability']}</b>\n"
        f"👥 {T['population']}: <b>{player['population']}</b>\n"
        f"🪖 {T['military']}: <b>{player.get('military') or 0}</b>\n"
        f"🧪 {T['techs_title']}: {techs}\n"
        f"🎯 {T['actions']}: <b>{player['actions_left']}</b>\n"
        f"🏆 Score: <b>{player['score']}</b>"
    )


def compact_stats(p: Dict[str, Any]) -> str:
    """Short, language-neutral summary that fits Telegram's 200-char toast limit."""
    return (
        f"💰{p['money']} 🏭{p['industry']} 🔬{p['science']} 🛡️{p['stability']} "
        f"👥{p['population']} 🪖{p.get('military') or 0} 🎯{p['actions_left']}"
    )


def format_action_result(info: Dict[str, Any], language: str) -> str:
    action = info["action"]
    data = dict(info)
    if action == "attack":
        key = "res_attack_win" if info.get("win") else "res_attack_lose"
    elif action == "spy":
        key = "res_spy_ok" if info.get("success") else "res_spy_fail"
    elif action == "tech":
        key = "res_tech"
        tech = TECHS[info["key"]]
        data["name"] = tech[language]
        data["desc"] = tech["desc_" + language]
    else:
        key = f"res_{action}"
    text = TEXTS[language][key].format(**data)
    if action == "trade" and info.get("sanctions"):
        text += " " + TEXTS[language]["trade_sanctioned"]
    return text


def country_prompt(language: str) -> str:
    lines = [TEXTS[language]["country_open"], ""]
    for code, data in COUNTRIES.items():
        lines.append(f"• {data[language]} — {perk_text(code, language)}")
    return "\n".join(lines)


def tech_menu(p: Dict[str, Any], language: str, game_id: int):
    T = TEXTS[language]
    owned = set(owned_techs(p))
    lines = [T["pick_tech"], ""]
    rows = []
    for key, tech in TECHS.items():
        if key in owned:
            continue
        lock = "" if p["science"] >= tech["science"] else f" 🔒 {T['science']} {tech['science']}"
        lines.append(f"• <b>{tech[language]}</b> — {tech['desc_' + language]} ({tech['cost']} 💰){lock}")
        rows.append([{"text": f"{tech[language]} — {tech['cost']}", "callback_data": f"buytech:{game_id}:{key}"}])
    if not rows:
        lines.append(T["all_techs"])
    rows.append([{"text": T["back"], "callback_data": f"refresh:{game_id}"}])
    return "\n".join(lines), {"inline_keyboard": rows}


def format_results(results: List[Dict[str, Any]], language: str) -> str:
    lines = []
    for i, p in enumerate(results, start=1):
        name = esc(p.get("first_name") or p.get("username") or f"Player {i}")
        cname = country_name(p.get("country"), language)
        line = f"{i}. {name} — {cname} — {p['score']}"
        obj = OBJECTIVES.get(p.get("objective") or "")
        if obj:
            line += f"\n    🎯 {obj[language]} {'✅' if p.get('objective_done') else '❌'}"
        lines.append(line)
    return "\n".join(lines)


# ============================================================
# TELEGRAM API
# ============================================================


def telegram_call(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not TELEGRAM_API:
        raise RuntimeError("BOT_TOKEN is missing")

    data = urllib.parse.urlencode({
        k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
        for k, v in payload.items()
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{TELEGRAM_API}/{method}",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error("Telegram HTTP %s: %s", e.code, body)
        raise

    if not result.get("ok"):
        logger.error("Telegram API error on %s: %s", method, result)
    return result


def send_message(chat_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None, parse_mode: str = "HTML"):
    payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return telegram_call("sendMessage", payload)


def edit_message(chat_id: int, message_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None):
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return telegram_call("editMessageText", payload)


def answer_callback(callback_id: str, text: Optional[str] = None, show_alert: bool = False):
    payload: Dict[str, Any] = {"callback_query_id": callback_id, "show_alert": str(show_alert).lower()}
    if text:
        payload["text"] = text
    return telegram_call("answerCallbackQuery", payload)


def set_webhook():
    if not WEBHOOK_URL:
        raise RuntimeError("WEBHOOK_URL is missing")
    endpoint = f"{WEBHOOK_URL}/telegram"
    payload = {"url": endpoint}
    if WEBHOOK_SECRET:
        payload["secret_token"] = WEBHOOK_SECRET
    return telegram_call("setWebhook", payload)


# ============================================================
# KEYBOARDS
# ============================================================


def main_keyboard(language: str):
    if language == "fa":
        return {
            "keyboard": [
                [{"text": TEXTS[language]["create_button"]}, {"text": TEXTS[language]["join_button"]}],
                [{"text": TEXTS[language]["my_game"]}, {"text": TEXTS[language]["game_menu"]}],
                [{"text": TEXTS[language]["rules_button"]}, {"text": TEXTS[language]["help_button"]}],
                [{"text": TEXTS[language]["language_button"]}],
            ],
            "resize_keyboard": True,
        }
    return {
        "keyboard": [
            [{"text": TEXTS[language]["create_button"]}, {"text": TEXTS[language]["join_button"]}],
            [{"text": TEXTS[language]["my_game"]}, {"text": TEXTS[language]["game_menu"]}],
            [{"text": TEXTS[language]["rules_button"]}, {"text": TEXTS[language]["help_button"]}],
            [{"text": TEXTS[language]["language_button"]}],
        ],
        "resize_keyboard": True,
    }


def language_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🇮🇷 فارسی", "callback_data": "lang:fa"}, {"text": "🇬🇧 English", "callback_data": "lang:en"}]
        ]
    }


def lobby_keyboard(game: Dict[str, Any], user_id: int, language: str):
    buttons = [
        [{"text": TEXTS[language]["choose_country"], "callback_data": f"country:{game['id']}"}],
        [{"text": TEXTS[language]["my_game"], "callback_data": f"refresh:{game['id']}"}],
    ]
    if game.get("owner_id") == user_id:
        buttons.insert(0, [{"text": f"🚀 {TEXTS[language]['start_game']}", "callback_data": f"start:{game['id']}"}])
    return {"inline_keyboard": buttons}


def country_keyboard(game_id: int, language: str):
    rows = []
    items = list(COUNTRIES.items())
    for i in range(0, len(items), 2):
        row = []
        for code, data in items[i : i + 2]:
            row.append({"text": data[language], "callback_data": f"pickcountry:{game_id}:{code}"})
        rows.append(row)
    rows.append([{"text": TEXTS[language]["back"], "callback_data": f"refresh:{game_id}"}])
    return {"inline_keyboard": rows}


def running_keyboard(game_id: int, language: str):
    T = TEXTS[language]
    return {
        "inline_keyboard": [
            [
                {"text": T["build"], "callback_data": f"action:{game_id}:build"},
                {"text": T["research"], "callback_data": f"action:{game_id}:research"},
            ],
            [
                {"text": T["trade"], "callback_data": f"action:{game_id}:trade"},
                {"text": T["recruit"], "callback_data": f"action:{game_id}:recruit"},
            ],
            [
                {"text": T["welfare"], "callback_data": f"action:{game_id}:welfare"},
                {"text": T["tech"], "callback_data": f"action:{game_id}:tech"},
            ],
            [
                {"text": T["diplomacy"], "callback_data": f"action:{game_id}:diplomacy"},
                {"text": T["sanction"], "callback_data": f"action:{game_id}:sanction"},
            ],
            [
                {"text": T["attack"], "callback_data": f"action:{game_id}:attack"},
                {"text": T["spy"], "callback_data": f"action:{game_id}:spy"},
            ],
            [
                {"text": T["mission"], "callback_data": f"mission:{game_id}"},
                {"text": T["my_game"], "callback_data": f"refresh:{game_id}"},
            ],
            [{"text": T["end_turn"], "callback_data": f"endturn:{game_id}"}],
        ]
    }


def target_keyboard(game_id: int, action: str, language: str, targets: List[Dict[str, Any]]):
    rows = []
    for p in targets:
        label = f"{p.get('first_name') or p.get('username') or 'Player'} — {country_name(p.get('country'), language)}"
        rows.append([{"text": label, "callback_data": f"dotarget:{game_id}:{action}:{p['id']}"}])
    rows.append([{"text": TEXTS[language]["back"], "callback_data": f"refresh:{game_id}"}])
    return {"inline_keyboard": rows}


# ============================================================
# GAME MESSAGE RENDERING
# ============================================================


def send_game_status(chat_id: int, game_id: int, user_id: int):
    language = get_language(user_id)
    game_text = format_game(game_id, language)
    game = get_game_by_id(game_id)
    if not game:
        send_message(chat_id, t(user_id, "game_not_found"), main_keyboard(language))
        return

    player = get_player(game_id, user_id)
    if game["status"] == "waiting":
        markup = lobby_keyboard(game, user_id, language)
    elif game["status"] == "running":
        markup = running_keyboard(game_id, language)
    else:
        markup = main_keyboard(language)

    if player and game["status"] == "running":
        game_text += "\n\n" + format_player_stats(player, language)
    send_message(chat_id, game_text, markup)


def get_game_by_id(game_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games WHERE id = %s", (game_id,))
            return cur.fetchone()


# ============================================================
# HANDLERS
# ============================================================


def handle_start(message: Dict[str, Any]):
    user = message["from"]
    user_id = int(user["id"])
    chat_id = int(message["chat"]["id"])
    language = get_language(user_id)

    set_pending_action(user_id, None)
    text = t(user_id, "welcome", name=display_name(user))
    if message["chat"].get("type") == "private":
        text += "\n\n" + t(user_id, "private_tip")
    send_message(chat_id, text, main_keyboard(language))


def handle_text(message: Dict[str, Any]):
    user = message["from"]
    user_id = int(user["id"])
    chat = message["chat"]
    chat_id = int(chat["id"])
    text = (message.get("text") or "").strip()
    language = get_language(user_id)

    if text.startswith("/start"):
        handle_start(message)
        return

    if text.startswith("/help"):
        send_message(chat_id, t(user_id, "help"), main_keyboard(language))
        return

    if text.startswith("/rules"):
        send_message(chat_id, t(user_id, "rules"), main_keyboard(language))
        return

    if text.startswith("/leave") or text.startswith("/cancelgame"):
        set_pending_action(user_id, None)
        result = leave_game(user_id)
        key = {
            "no_game": "no_game",
            "left": "left_game",
            "cancelled": "game_cancelled",
            "running_not_owner": "cannot_leave_running",
        }[result]
        send_message(chat_id, t(user_id, key), main_keyboard(language))
        return

    if text.startswith("/game") or text == TEXTS[language]["my_game"]:
        game = get_user_game(user_id)
        if not game:
            send_message(chat_id, t(user_id, "no_game"), main_keyboard(language))
        else:
            send_game_status(chat_id, game["id"], user_id)
        return

    if text == TEXTS[language]["language_button"] or text == "/language":
        send_message(chat_id, t(user_id, "choose_language"), language_keyboard())
        return

    if text == TEXTS[language]["rules_button"]:
        send_message(chat_id, t(user_id, "rules"), main_keyboard(language))
        return

    if text == TEXTS[language]["help_button"]:
        send_message(chat_id, t(user_id, "help"), main_keyboard(language))
        return

    if text == TEXTS[language]["create_button"] or text == "/newgame":
        if chat.get("type") == "private":
            send_message(chat_id, t(user_id, "need_group"), main_keyboard(language))
            return
        set_pending_action(user_id, None)
        try:
            game = create_game(user, chat_id)
            send_message(
                chat_id,
                t(user_id, "game_created", code=game["code"], name=display_name(user)),
                lobby_keyboard(game, user_id, language),
            )
        except ValueError as exc:
            if str(exc) == "already_in_game":
                game = get_user_game(user_id)
                send_message(chat_id, t(user_id, "game_already", code=game["code"]), main_keyboard(language))
            else:
                logger.exception("Could not create game")
                send_message(chat_id, "Database/game error. Please try again.", main_keyboard(language))
        except Exception:
            logger.exception("Could not create game (unexpected error)")
            send_message(chat_id, "Database/game error. Please try again.", main_keyboard(language))
        return

    if text == TEXTS[language]["join_button"] or text == "/join":
        set_pending_action(user_id, "join_game")
        send_message(chat_id, t(user_id, "join_enter_code"), main_keyboard(language))
        return

    pending = get_pending_action(user_id)
    if pending == "join_game":
        code = clean_code(text)
        if len(code) != 6 or not all(c in string.ascii_uppercase + string.digits for c in code):
            send_message(chat_id, t(user_id, "invalid_code"), main_keyboard(language))
            return

        game = get_game_by_code(code)
        if not game or game["status"] != "waiting":
            set_pending_action(user_id, None)
            send_message(chat_id, t(user_id, "game_not_found"), main_keyboard(language))
            return

        try:
            join_game(game["id"], user, chat_id)
            set_pending_action(user_id, None)
            refreshed = get_game_by_id(game["id"])
            send_message(
                chat_id,
                t(user_id, "joined", game=format_game(game["id"], language)),
                lobby_keyboard(refreshed, user_id, language),
            )
        except ValueError as exc:
            err = str(exc)
            set_pending_action(user_id, None)
            if err == "already_in_game":
                send_message(chat_id, t(user_id, "already_in_game"), main_keyboard(language))
            elif err == "game_full":
                send_message(chat_id, "Game is full.", main_keyboard(language))
            else:
                send_message(chat_id, t(user_id, "game_not_found"), main_keyboard(language))
        return

    if text == TEXTS[language]["game_menu"]:
        game = get_user_game(user_id)
        if not game:
            send_message(chat_id, t(user_id, "no_game"), main_keyboard(language))
        else:
            send_game_status(chat_id, game["id"], user_id)
        return

    # Command shortcuts.
    if text.startswith("/status"):
        game = get_user_game(user_id)
        if game:
            send_game_status(chat_id, game["id"], user_id)
        else:
            send_message(chat_id, t(user_id, "no_game"), main_keyboard(language))
        return

    send_message(chat_id, t(user_id, "unknown"), main_keyboard(language))


def esc_name(user: Dict[str, Any]) -> str:
    return esc(display_name(user))


def handle_game_error(callback_id: str, user_id: int, err: str) -> bool:
    """Show a friendly alert for expected game errors. Returns True if handled."""
    if err.startswith("not_your_turn:"):
        answer_callback(callback_id, t(user_id, "not_your_turn", player=err.split(":", 1)[1]), True)
        return True
    if err.startswith("not_enough_money:"):
        answer_callback(callback_id, t(user_id, "not_enough_money", money=err.split(":", 1)[1]), True)
        return True
    if err in (
        "not_enough_actions", "not_running", "no_military",
        "treaty_active", "treaty_exists", "too_early", "bad_target",
        "sanction_exists", "tech_owned", "tech_locked", "bad_tech",
    ):
        answer_callback(callback_id, t(user_id, err), True)
        return True
    return False


def handle_callback(callback: Dict[str, Any]):
    callback_id = callback["id"]
    user = callback["from"]
    user_id = int(user["id"])
    data = callback.get("data", "")
    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = int(chat.get("id", user_id))
    message_id = int(message.get("message_id", 0)) if message.get("message_id") else None
    language = get_language(user_id)

    try:
        if data.startswith("lang:"):
            selected = data.split(":", 1)[1]
            set_language(user_id, selected)
            language = selected
            answer_callback(callback_id, t(user_id, "language_saved"))
            send_message(chat_id, t(user_id, "welcome", name=display_name(user)), main_keyboard(language))
            return

        if data.startswith("country:"):
            game_id = int(data.split(":")[1])
            answer_callback(callback_id)
            game = get_game_by_id(game_id)
            if not game:
                send_message(chat_id, t(user_id, "game_not_found"), main_keyboard(language))
                return
            if game["status"] != "waiting":
                send_message(chat_id, t(user_id, "not_running"), main_keyboard(language))
                return
            send_message(chat_id, country_prompt(language), country_keyboard(game_id, language))
            return

        if data.startswith("pickcountry:"):
            _, game_id_str, code = data.split(":", 2)
            game_id = int(game_id_str)
            try:
                ok = choose_country(game_id, user_id, code)
            except ValueError as exc:
                if str(exc) == "country_taken":
                    answer_callback(callback_id, t(user_id, "country_taken"), True)
                    return
                raise
            if not ok:
                answer_callback(callback_id, t(user_id, "game_not_found"), True)
                return
            answer_callback(callback_id, t(user_id, "country_saved", country=country_name(code, language)))
            if message_id:
                edit_message(chat_id, message_id, country_prompt(language), country_keyboard(game_id, language))
            send_game_status(chat_id, game_id, user_id)
            return

        if data.startswith("start:"):
            game_id = int(data.split(":")[1])
            try:
                first_player = start_game(game_id, user_id)
            except ValueError as exc:
                key = str(exc)
                if key == "not_owner":
                    answer_callback(callback_id, t(user_id, "not_owner"), True)
                    return
                if key == "need_players":
                    answer_callback(callback_id, t(user_id, "need_players"), True)
                    return
                if key == "need_country":
                    answer_callback(callback_id, t(user_id, "need_country"), True)
                    return
                if key == "not_running":
                    answer_callback(callback_id, t(user_id, "not_running"), True)
                    return
                raise
            answer_callback(callback_id, t(user_id, "game_started", player=first_player.get("first_name") or first_player.get("username") or "Player"))
            refreshed = get_game_by_id(game_id)
            public_text = t(user_id, "game_started", player=pname(first_player))
            public_text += "\n\n" + format_game(game_id, language)
            send_message(chat_id, public_text, running_keyboard(game_id, language))
            return

        if data.startswith("action:"):
            _, game_id_str, action = data.split(":", 2)
            game_id = int(game_id_str)
            try:
                if action in TARGET_ACTIONS:
                    targets = get_targets(game_id, user_id)
                    answer_callback(callback_id)
                    send_message(
                        chat_id,
                        t(user_id, f"pick_target_{action}"),
                        target_keyboard(game_id, action, language, targets),
                    )
                    return
                if action == "tech":
                    me = get_turn_player(game_id, user_id)
                    answer_callback(callback_id)
                    menu_text, menu_markup = tech_menu(me, language, game_id)
                    send_message(chat_id, menu_text, menu_markup)
                    return
                player, info = action_for_player(game_id, user_id, action)
            except ValueError as exc:
                if handle_game_error(callback_id, user_id, str(exc)):
                    return
                raise

            answer_callback(callback_id, compact_stats(player))
            public_text = f"{esc_name(user)}: {format_action_result(info, language)}"
            public_text += "\n\n" + format_game(game_id, language)
            send_message(chat_id, public_text, running_keyboard(game_id, language))
            return

        if data.startswith("buytech:"):
            _, game_id_str, tech_key = data.split(":", 2)
            game_id = int(game_id_str)
            try:
                player, info = buy_tech(game_id, user_id, tech_key)
            except ValueError as exc:
                if handle_game_error(callback_id, user_id, str(exc)):
                    return
                raise

            answer_callback(callback_id, compact_stats(player))
            public_text = f"{esc_name(user)}: {format_action_result(info, language)}"
            public_text += "\n\n" + format_game(game_id, language)
            send_message(chat_id, public_text, running_keyboard(game_id, language))
            return

        if data.startswith("dotarget:"):
            _, game_id_str, action, target_str = data.split(":", 3)
            game_id = int(game_id_str)
            handlers = {
                "attack": attack_player,
                "diplomacy": sign_treaty,
                "spy": spy_on,
                "sanction": impose_sanction,
            }
            if action not in handlers:
                answer_callback(callback_id)
                return
            try:
                player, defender, info = handlers[action](game_id, user_id, int(target_str))
            except ValueError as exc:
                if handle_game_error(callback_id, user_id, str(exc)):
                    return
                raise

            # A successful spy gets the target's numbers privately; everyone else sees their own.
            if action == "spy" and info.get("success"):
                answer_callback(callback_id, "🕵️ " + compact_stats(defender))
            else:
                answer_callback(callback_id, compact_stats(player))
            public_text = format_action_result(info, language)
            public_text += "\n\n" + format_game(game_id, language)
            send_message(chat_id, public_text, running_keyboard(game_id, language))
            return

        if data.startswith("mission:"):
            game_id = int(data.split(":")[1])
            me = get_or_assign_objective(game_id, user_id)
            if not me:
                answer_callback(callback_id, t(user_id, "no_game"), True)
                return
            obj = OBJECTIVES[me["objective"]]
            current_value, target = objective_progress(me)
            answer_callback(
                callback_id,
                t(user_id, "mission_text", title=obj[language], cur=current_value, target=target, bonus=OBJECTIVE_BONUS),
                True,
            )
            return

        if data.startswith("endturn:"):
            game_id = int(data.split(":")[1])
            try:
                result = end_turn(game_id, user_id)
            except ValueError as exc:
                if handle_game_error(callback_id, user_id, str(exc)):
                    return
                raise

            if result["finished"]:
                answer_callback(callback_id)
                players = get_players(game_id)
                sent_chats = set()
                for p in players:
                    target_chat = p["chat_id"] or chat_id
                    if target_chat in sent_chats:
                        continue
                    sent_chats.add(target_chat)
                    lang = get_language(p["user_id"])
                    text = t(p["user_id"], "game_finished", results=format_results(result["results"], lang))
                    send_message(target_chat, text, main_keyboard(lang))
                return

            answer_callback(callback_id)
            ended = result["ended_player"]
            public_text = t(user_id, "turn_ended", turn=result["turn"], player=pname(result["next_player"]))
            public_text += "\n" + t(user_id, "income_line", income=result["income"], upkeep=result["upkeep"])
            if result.get("event"):
                public_text += f"\n📰 {pname(ended)}: {EVENT_BY_KEY[result['event']][language]}"
            if result.get("unrest"):
                public_text += "\n" + t(user_id, "unrest", player=pname(ended))
            if result.get("world_event"):
                public_text += f"\n🌍 {WORLD_EVENT_BY_KEY[result['world_event']][language]}"
            public_text += "\n\n" + format_game(game_id, language)
            send_message(chat_id, public_text, running_keyboard(game_id, language))
            return

        if data.startswith("refresh:"):
            game_id = int(data.split(":")[1])
            answer_callback(callback_id)
            send_game_status(chat_id, game_id, user_id)
            return

        answer_callback(callback_id)
    except Exception:
        logger.exception("Callback handler failed")
        try:
            answer_callback(callback_id, "Something went wrong.", True)
        except Exception:
            pass


# ============================================================
# FLASK ROUTES
# ============================================================


@app.get("/")
def home():
    return jsonify({
        "ok": True,
        "service": "strategy-game",
        "message": "Bot is running",
    })


@app.get("/health")
def health():
    db_ok = False
    error = None
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                db_ok = bool(cur.fetchone()["ok"] == 1)
    except Exception as exc:
        error = str(exc)

    payload = {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "bot_token_configured": bool(BOT_TOKEN),
        "webhook_url_configured": bool(WEBHOOK_URL),
    }
    if error:
        payload["database_error"] = error
    return jsonify(payload), (200 if db_ok else 503)


@app.route("/set-webhook", methods=["GET", "POST"])
def webhook_setup():
    if ADMIN_KEY:
        supplied = request.headers.get("X-Admin-Key", "")
        if supplied != ADMIN_KEY:
            return jsonify({"ok": False, "error": "Forbidden"}), 403

    try:
        result = set_webhook()
        return jsonify(result)
    except Exception as exc:
        logger.exception("Webhook setup failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/telegram")
def telegram_webhook():
    if WEBHOOK_SECRET:
        incoming_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if incoming_secret != WEBHOOK_SECRET:
            return jsonify({"ok": False, "error": "Unauthorized"}), 403

    update = request.get_json(silent=True) or {}

    try:
        if update.get("callback_query"):
            handle_callback(update["callback_query"])
        elif update.get("message"):
            handle_text(update["message"])
        elif update.get("edited_message"):
            handle_text(update["edited_message"])
    except Exception:
        logger.exception("Update handling failed")

    return jsonify({"ok": True})


# ============================================================
# STARTUP
# ============================================================


def startup():
    if not DATABASE_URL:
        logger.error("DATABASE_URL is missing")
    else:
        try:
            init_db()
        except Exception:
            logger.exception("Database initialization failed")

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing")
    else:
        logger.info("Telegram bot token is configured")


startup()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
