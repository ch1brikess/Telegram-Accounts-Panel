"""Утилиты и функции работы с данными"""
import json
import os
import time
import random
from datetime import datetime
from pathlib import Path
import config


# === Загрузка/сохранение данных ===

def load_cards():
    with open(config.CARDS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)['cards']


def load_users():
    if os.path.exists(config.USER_DATA_FILE):
        with open(config.USER_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_users(users):
    with open(config.USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# === Работа с пользователями ===

def get_user(users, user_id):
    user_id_str = str(user_id)
    current_month = datetime.now().strftime("%Y-%m")
    
    if user_id_str not in users:
        users[user_id_str] = {
            "name": None,
            "fragments": {"common": 0, "rare": 0, "epic": 0, "legendary": 0, "mythic": 0, "limited": 0},
            "cards": [],
            "total_gacha": 0,
            "total_crafts": 0,
            "total_points": 0,
            "duplicates_count": 0,
            "limited_fragments_this_month": 0,
            "limited_month": current_month,
            "created_at": datetime.now().isoformat(),
            "gacha_history": [],
            "accepted_rules": False
        }
    
    user = users[user_id_str]
    
    # Миграция: добавляем недостающие поля для старых пользователей
    if "fragments" not in user:
        user["fragments"] = {"common": 0, "rare": 0, "epic": 0, "legendary": 0, "mythic": 0, "limited": 0}
    if "cards" not in user:
        user["cards"] = []
    if "total_gacha" not in user:
        user["total_gacha"] = 0
    if "total_crafts" not in user:
        user["total_crafts"] = 0
    if "total_points" not in user:
        user["total_points"] = 0
    if "duplicates_count" not in user:
        user["duplicates_count"] = 0
    if "created_at" not in user:
        user["created_at"] = datetime.now().isoformat()
    if "gacha_history" not in user:
        user["gacha_history"] = []
    if "limited_fragments_this_month" not in user:
        user["limited_fragments_this_month"] = 0
    if "limited_month" not in user:
        user["limited_month"] = current_month
    if "accepted_rules" not in user:
        user["accepted_rules"] = False
    
    # Миграция: добавляем поле duplicates к каждой карте
    for card in user.get("cards", []):
        if "duplicates" not in card:
            card["duplicates"] = 0
    
    if user.get("limited_month") != current_month:
        user["limited_fragments_this_month"] = 0
        user["limited_month"] = current_month
    
    return user


def get_user_points(user):
    """Возвращает общее количество очков пользователя"""
    return user.get("total_points", 0)


def recalculate_points(user):
    """Пересчитывает очки (используется при миграции)"""
    points = 0
    for card in user.get("cards", []):
        base_points = card.get("points", config.RARITY_POINTS.get(card.get("rarity"), 0))
        duplicates = card.get("duplicates", 0)
        points += base_points * (1 + duplicates)
    user["total_points"] = points
    return points


def get_leaderboard(users):
    """Возвращает топ-10 игроков"""
    leaderboard = []
    for user_id, user in users.items():
        if not isinstance(user, dict):
            continue
        points = get_user_points(user)
        leaderboard.append({"id": user_id, "name": user.get("name") or f"User{user_id}", "points": points})
    leaderboard.sort(key=lambda x: x["points"], reverse=True)
    return leaderboard[:10]


# === Гача и карты ===

def get_random_rarity():
    """Возвращает случайную редкость на основе шансов"""
    rarities = list(config.RARITY_CHANCES.keys())
    weights = list(config.RARITY_CHANCES.values())
    return random.choices(rarities, weights=weights, k=1)[0]


def get_random_card_by_rarity(rarity, limited_only=False):
    """Возвращает случайную карту указанной редкости"""
    cards = load_cards()
    if limited_only:
        matching_cards = [c for c in cards if c['rarity'] == rarity and c.get('limited', False)]
    else:
        matching_cards = [c for c in cards if c['rarity'] == rarity and not c.get('limited', False)]
    if not matching_cards:
        return None
    return random.choice(matching_cards)


def get_random_limited_card():
    """Возвращает случайную лимитированную карту"""
    cards = load_cards()
    limited_cards = [c for c in cards if c.get('limited', False)]
    if not limited_cards:
        return None
    card = random.choice(limited_cards)
    rarity = card['rarity']
    return card, rarity


# === История ===

def add_gacha_history(user, rarity, is_limited, card_id=None):
    """Добавляет запись в историю круток"""
    history = user.get("gacha_history", [])
    
    entry = {
        "time": datetime.now().isoformat(),
        "rarity": rarity,
        "is_limited": is_limited,
        "card_id": card_id
    }
    
    history.insert(0, entry)
    user["gacha_history"] = history[:10]


def get_gacha_history_text(user):
    """Возвращает текст с историей последних 10 круток"""
    history = user.get("gacha_history", [])
    if not history:
        return "📜 История круток пуста"
    
    cards = load_cards()
    card_map = {c["id"]: c for c in cards}
    
    text = "📜 *Последние 10 круток:*\n"
    for i, entry in enumerate(history, 1):
        dt = datetime.fromisoformat(entry["time"])
        time_str = dt.strftime("%H:%M:%S")
        
        rarity = entry.get("rarity", "common")
        is_limited = entry.get("is_limited", False)
        card_id = entry.get("card_id")
        
        emoji = config.RARITY_EMOJI.get(rarity, "⚪")
        rarity_name = config.RARITY_NAMES.get(rarity, rarity)
        limited_tag = " 🎁" if is_limited else ""
        
        if card_id and card_id in card_map:
            card = card_map[card_id]
            name = f"{card['name']} {card['surname']}"
        else:
            name = rarity_name
        
        text += f"{i}. {emoji} {name}{limited_tag} — {time_str}\n"
    
    return text


# === Форматирование ===

def format_time(seconds):
    """Форматирует секунды в читаемый вид"""
    if seconds < 60:
        return f"{int(seconds)} сек"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins} мин {secs} сек"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours} ч {mins} мин {secs} сек"


def escape_md2(text):
    """Экранирует спецсимволы для MarkdownV2"""
    special_chars = '_*[]()~>#+-.!|'
    for char in special_chars:
        text = text.replace(char, '\\' + char)
    return text


# === Проверки ===

def is_banned(user_id):
    """Проверяет, забанен ли пользователь"""
    return user_id in config.BANNED_USERS


def is_admin(user_id):
    """Проверяет, является ли пользователь админом"""
    return user_id in config.ADMIN_IDS


def is_season_active():
    """Проверяет, идёт ли сейчас сезон"""
    try:
        start = datetime.strptime(config.SEASON_START, "%Y-%m-%d")
        end = datetime.strptime(config.SEASON_END, "%Y-%m-%d")
        now = datetime.now()
        return start <= now <= end
    except:
        return True


def get_season_name():
    """Возвращает название текущего сезона"""
    return config.SEASON_START.replace("-", "")[:6]


def has_accepted_rules(user):
    """Проверяет, принял ли пользователь правила"""
    return user.get("accepted_rules", False)


def set_accepted_rules(user):
    """Отмечает, что пользователь принял правила"""
    user["accepted_rules"] = True


# === Сезоны ===

def load_season_top():
    """Загружает топ сезона из файла"""
    if os.path.exists(config.SEASON_TOP_FILE):
        try:
            with open(config.SEASON_TOP_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"season": None, "top": []}


def save_season_top(leaderboard):
    """Сохраняет топ сезона в файл"""
    data = {
        "season": get_season_name(),
        "start": config.SEASON_START,
        "end": config.SEASON_END,
        "top": leaderboard[:10],
        "saved_at": datetime.now().isoformat()
    }
    with open(config.SEASON_TOP_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def is_new_season():
    """Проверяет, начался ли новый сезон"""
    users = load_users()
    last_season = users.get("_last_season", None)
    current_season = get_season_name()
    if last_season != current_season:
        users["_last_season"] = current_season
        save_users(users)
        return True
    return False


# === Файлы ===

def load_rules():
    """Загружает правила из файла"""
    try:
        with open(config.RULES_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return "Правила не найдены"


def load_info():
    """Загружает информацию о боте из файла"""
    try:
        with open(config.INFO_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return "Информация не найдена"


# === Сообщения ===

async def send_banned_message(update, context):
    """Отправить сообщение о бане"""
    if update.message:
        await update.message.reply_text(config.BANNED_MESSAGE)
    elif update.callback_query:
        await update.callback_query.answer(config.BANNED_MESSAGE, show_alert=True)


async def send_off_season_message(update, context):
    """Отправить сообщение о конце сезона"""
    if update.message:
        await update.message.reply_text(config.OFF_SEASON_MESSAGE, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.answer(config.OFF_SEASON_MESSAGE, show_alert=True)


async def safe_edit_message(query, text, parse_mode='Markdown', reply_markup=None):
    """Безопасное редактирование сообщения"""
    try:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception:
        await query.bot.send_message(
            chat_id=query.from_user.id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )