import json
import random
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)

import config


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
            "limited_fragments_this_month": 0,
            "limited_month": current_month,
            "created_at": datetime.now().isoformat()
        }
    
    user = users[user_id_str]
    if user.get("limited_month") != current_month:
        user["limited_fragments_this_month"] = 0
        user["limited_month"] = current_month
    
    return user


def get_user_points(user):
    points = 0
    for card in user.get("cards", []):
        points += card.get("points", config.RARITY_POINTS.get(card.get("rarity"), 0))
    return points


def get_leaderboard(users):
    leaderboard = []
    for user_id, user in users.items():
        points = get_user_points(user)
        leaderboard.append({"id": user_id, "name": user.get("name") or f"User{user_id}", "points": points})
    leaderboard.sort(key=lambda x: x["points"], reverse=True)
    return leaderboard[:10]


def get_random_rarity():
    rarities = list(config.RARITY_CHANCES.keys())
    weights = list(config.RARITY_CHANCES.values())
    return random.choices(rarities, weights=weights, k=1)[0]


def get_random_card_by_rarity(rarity, limited_only=False):
    cards = load_cards()
    if limited_only:
        matching_cards = [c for c in cards if c['rarity'] == rarity and c.get('limited', False)]
    else:
        matching_cards = [c for c in cards if c['rarity'] == rarity and not c.get('limited', False)]
    if not matching_cards:
        return None
    return random.choice(matching_cards)


def get_random_limited_card():
    cards = load_cards()
    limited_cards = [c for c in cards if c.get('limited', False)]
    if not limited_cards:
        return None
    card = random.choice(limited_cards)
    rarity = card['rarity']
    return card, rarity


def main_keyboard_reply():
    """Главное меню в виде ReplyKeyboard (кнопки внизу экрана)"""
    keyboard = [
        ["🎴 Гача", "🃏 Мои карты"],
        ["👤 Профиль", "📋 Меню"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def main_keyboard_inline(points):
    """Главное меню в виде Inline клавиатуры (для обратной совместимости)"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🎴 Получить карту ({points} pts)", callback_data="gacha")],
        [InlineKeyboardButton("📋 Меню", callback_data="menu")],
        [InlineKeyboardButton("🃏 Мои карты", callback_data="mycards_all")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")]
    ])


def get_card_detail_keyboard(card_id):
    """Кнопки для просмотра карты"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ Удалить из коллекции", callback_data=f"delete_card_{card_id}")],
        [InlineKeyboardButton("🔙 К списку карт", callback_data="mycards_all")]
    ])


def menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Таблица лидеров", callback_data="leaderboard")],
        [InlineKeyboardButton("⚒️ Крафт", callback_data="craft_menu")],
        [InlineKeyboardButton("💎 Осколки", callback_data="inventory")],
        [InlineKeyboardButton("📋 Все карты", callback_data="all_cards")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])


def craft_keyboard():
    keyboard = []
    for rarity in ['common', 'rare', 'epic', 'legendary', 'mythic']:
        emoji = config.RARITY_EMOJI[rarity]
        name = config.RARITY_NAMES[rarity]
        keyboard.append([InlineKeyboardButton(f"{emoji} {name}", callback_data=f"craft_{rarity}")])
    keyboard.append([InlineKeyboardButton("🎁 Лимитированная", callback_data="craft_limited")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu")])
    return InlineKeyboardMarkup(keyboard)


def mycards_keyboard(user, page=0, rarity_filter=None):
    cards = user.get("cards", [])
    
    if rarity_filter:
        if rarity_filter == "limited":
            cards = [c for c in cards if c.get("limited", False)]
        elif rarity_filter == "all":
            pass
        else:
            cards = [c for c in cards if c.get("rarity") == rarity_filter]
    
    cards_per_page = 5
    total_pages = max(1, (len(cards) + cards_per_page - 1) // cards_per_page)
    page = min(page, total_pages - 1)
    
    start = page * cards_per_page
    page_cards = cards[start:start + cards_per_page]
    
    keyboard = []
    
    for card in page_cards:
        emoji = config.RARITY_EMOJI.get(card.get("rarity"), "⚪")
        limited_tag = " 🎁" if card.get("limited") else ""
        # Клик на карту открывает её детальный просмотр
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {card['name']} {card['surname']}{limited_tag}",
            callback_data=f"view_card_{card['id']}"
        )])
    
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀", callback_data=f"mycards_{rarity_filter or 'all'}_{page-1}"))
    nav_row.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("▶", callback_data=f"mycards_{rarity_filter or 'all'}_{page+1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    filter_row = []
    for label, rf in [("Все", "all"), ("Лимит", "limited")]:
        if rarity_filter == rf or (rarity_filter is None and rf == "all"):
            filter_row.append(InlineKeyboardButton(f"✅ {label}", callback_data="noop"))
        else:
            filter_row.append(InlineKeyboardButton(label, callback_data=f"mycards_{rf}_0"))
    
    keyboard.append(filter_row)
    
    rarity_row = []
    for rarity in ['common', 'rare', 'epic', 'legendary', 'mythic']:
        emoji = config.RARITY_EMOJI[rarity]
        if rarity_filter == rarity:
            rarity_row.append(InlineKeyboardButton(f"✅{emoji}", callback_data="noop"))
        else:
            rarity_row.append(InlineKeyboardButton(emoji, callback_data=f"mycards_{rarity}_0"))
    
    keyboard.append(rarity_row)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
    
    return InlineKeyboardMarkup(keyboard)


def leaderboard_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="leaderboard")],
        [InlineKeyboardButton("🔙 Назад", callback_data="menu")]
    ])


async def send_main_menu(update, context, user):
    points = get_user_points(user)
    text = f"👤 {user.get('name') or update.effective_user.first_name}\n"
    text += f"💰 Очки: {points}\n\n"
    text += "Выберите действие:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=main_keyboard_reply())
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=main_keyboard_inline(points))


async def send_welcome_message(update: Update, context: CallbackContext):
    """Вступительное сообщение с объяснением бота"""
    user = update.effective_user
    
    text = f"""🎮 *Добро пожаловать в 7mGacha!*

Привет, {user.first_name}! 👋

Я — бот для сбора карт с твоими одноклассниками и не только!

🎯 *Как это работает:*

1. *Гача* — крути колесо удачи и получай осколки карт
2. Собирай *6 осколков* одной редкости → крафтишь карту
3. Строй свою коллекцию и поднимайся в *таблице лидеров*!
4. У каждой карты есть очки — чем реже карта, тем больше очков

📊 *Редкости:*
⚪ Обычная (10 pts) — 70%
🔵 Редкая (50 pts) — 20%
🟣 Эпическая (200 pts) — 8%
🟡 Легендарная (1000 pts) — 1.6%
🌈 Мифическая (5000 pts) — 0.4%

🎁 *Лимитированные карты* — особые редкие карты, доступные только в определённое время!

Нажми /start чтобы начать или выбери действие в меню ниже!"""
    
    users = load_users()
    user_data = get_user(users, update.effective_user.id)
    save_users(users)
    
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard_reply())
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard_reply())


async def send_card_detail(update: Update, context: CallbackContext, card: dict):
    """Отправить детальную информацию о карте с изображением"""
    query = update.callback_query
    
    emoji = config.RARITY_EMOJI.get(card.get("rarity"), "⚪")
    rarity_name = config.RARITY_NAMES.get(card.get("rarity"), "")
    limited_tag = " 🎁 *ЛИМИТИРОВАННАЯ*" if card.get("limited") else ""
    
    text = f"{emoji} *{card['name']} {card['surname']}*\n"
    text += f"Редкость: {rarity_name}{limited_tag}\n\n"
    text += f"_{card['description']}_\n\n"
    text += f"💰 Очки: {card.get('points', 0)}"
    
    # Проверяем наличие картинки
    image_path = card.get("image_path", "")
    has_image = image_path and os.path.exists(image_path)
    
    if has_image:
        try:
            with open(image_path, 'rb') as photo:
                if query:
                    await query.answer()
                    await context.bot.send_photo(
                        chat_id=query.from_user.id,
                        photo=photo,
                        caption=text,
                        parse_mode='Markdown',
                        reply_markup=get_card_detail_keyboard(card['id'])
                    )
                else:
                    await update.message.reply_photo(photo, caption=text, parse_mode='Markdown', reply_markup=get_card_detail_keyboard(card['id']))
            return
        except Exception as e:
            print(f"Error sending photo: {e}")
    
    # Если картинки нет — отправляем текст
    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_card_detail_keyboard(card['id']))
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_card_detail_keyboard(card['id']))


async def start_command(update: Update, context: CallbackContext):
    users = load_users()
    user = get_user(users, update.effective_user.id)
    save_users(users)
    # Показываем вступительное сообщение
    await send_welcome_message(update, context)


async def gacha_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    user = get_user(users, update.effective_user.id)
    
    if config.COOLDOWN_SECONDS > 0:
        last_gacha = user.get("last_gacha", 0)
        if time.time() - last_gacha < config.COOLDOWN_SECONDS:
            remaining = int(config.COOLDOWN_SECONDS - (time.time() - last_gacha))
            await query.answer(f"Подождите {remaining} сек!", show_alert=True)
            return
    
    rarity = get_random_rarity()
    is_limited = random.random() < 0.1
    
    if is_limited:
        current_month = datetime.now().strftime("%Y-%m")
        if user.get("limited_month") != current_month:
            user["limited_fragments_this_month"] = 0
            user["limited_month"] = current_month
        
        if user["limited_fragments_this_month"] >= config.LIMITED_FRAGMENTS_PER_MONTH:
            is_limited = False
        else:
            card_data = get_random_limited_card()
            if card_data:
                card, rarity = card_data
                user["limited_fragments_this_month"] += 1
                user["fragments"]["limited"] = user["fragments"].get("limited", 0) + 1
            else:
                is_limited = False
    
    if not is_limited:
        user["fragments"][rarity] += 1
    
    user["total_gacha"] += 1
    user["last_gacha"] = time.time()
    save_users(users)
    
    emoji = config.RARITY_EMOJI.get(rarity, "⚪")
    rarity_name = config.RARITY_NAMES.get(rarity, rarity)
    
    if is_limited:
        limited_text = " 🎁 ЛИМИТИРОВАННАЯ"
        current = user["fragments"].get("limited", 0)
    else:
        limited_text = ""
        current = user["fragments"].get(rarity, 0)
    
    text = f"✨ Вам выпал осколок!\n\n{emoji} *{rarity_name}*{limited_text}\n\nОсколков: {current}/{config.FRAGMENTS_NEEDED}"
    
    if current >= config.FRAGMENTS_NEEDED:
        text += "\n\n🎉 Достаточно для крафта!"
    
    points = get_user_points(user)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=main_keyboard_inline(points))


async def menu_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    text = "📋 *Меню*\n\nВыберите действие:"
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=menu_keyboard())


async def profile_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    user_obj = query.from_user
    created = datetime.fromisoformat(user["created_at"]).strftime("%d.%m.%Y")
    points = get_user_points(user)
    
    text = f"👤 *Профиль*\n\n"
    text += f"Никнейм: {user.get('name') or 'Не установлен'}\n"
    text += f"TG ID: `{user_obj.id}`\n"
    text += f"Круток: {user['total_gacha']}\n"
    text += f"Дата регистрации: {created}\n"
    text += f"💰 Очки: {points}"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Сменить никнейм", callback_data="setname")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)


SET_NAME = 1

async def setname_command(update: Update, context: CallbackContext):
    await update.message.reply_text("Введите новый никнейм:")
    return SET_NAME


async def setname_received(update: Update, context: CallbackContext):
    users = load_users()
    user = get_user(users, update.effective_user.id)
    user["name"] = update.message.text[:50]
    save_users(users)
    await update.message.reply_text(f"Никнейм установлен: {user['name']}")
    await send_main_menu(update, context, user)
    return ConversationHandler.END


async def inventory_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    text = "💎 *Ваши осколки:*\n\n"
    
    for rarity in ['mythic', 'legendary', 'epic', 'rare', 'common']:
        count = user["fragments"].get(rarity, 0)
        emoji = config.RARITY_EMOJI[rarity]
        name = config.RARITY_NAMES[rarity]
        text += f"{emoji} {name}: {count}/{config.FRAGMENTS_NEEDED}"
        if count >= config.FRAGMENTS_NEEDED:
            text += " ✅"
        text += "\n"
    
    limited_count = user["fragments"].get("limited", 0)
    text += f"🎁 Лимитированные: {limited_count}/{config.FRAGMENTS_NEEDED}"
    if limited_count >= config.FRAGMENTS_NEEDED:
        text += " ✅"
    
    text += f"\n\n_Лимитированных осколков за месяц: {user.get('limited_fragments_this_month', 0)}/{config.LIMITED_FRAGMENTS_PER_MONTH}_"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data="menu")]
    ])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)


async def craft_menu_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    text = "⚒️ *Крафт карты*\n\nВыберите редкость для крафта (нужно 6 осколков):"
    
    keyboard = []
    for rarity in ['common', 'rare', 'epic', 'legendary', 'mythic']:
        count = user["fragments"].get(rarity, 0)
        emoji = config.RARITY_EMOJI[rarity]
        name = config.RARITY_NAMES[rarity]
        status = "✅" if count >= config.FRAGMENTS_NEEDED else "❌"
        keyboard.append([InlineKeyboardButton(f"{emoji} {name} ({count}/6) {status}", callback_data=f"craft_{rarity}")])
    
    limited_count = user["fragments"].get("limited", 0)
    status = "✅" if limited_count >= config.FRAGMENTS_NEEDED else "❌"
    keyboard.append([InlineKeyboardButton(f"🎁 Лимитированная ({limited_count}/6) {status}", callback_data="craft_limited")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu")])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


async def craft_do_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    rarity = query.data.replace("craft_", "")
    
    if rarity == "limited":
        current = user["fragments"].get("limited", 0)
        if current < config.FRAGMENTS_NEEDED:
            await query.answer(f"Нужно {config.FRAGMENTS_NEEDED} осколков!", show_alert=True)
            return
        
        user["fragments"]["limited"] -= config.FRAGMENTS_NEEDED
        card = get_random_limited_card()
        if not card:
            await query.answer("Нет лимитированных карт!", show_alert=True)
            return
        card, _ = card
    else:
        current = user["fragments"].get(rarity, 0)
        if current < config.FRAGMENTS_NEEDED:
            await query.answer(f"Нужно {config.FRAGMENTS_NEEDED} осколков!", show_alert=True)
            return
        
        user["fragments"][rarity] -= config.FRAGMENTS_NEEDED
        card = get_random_card_by_rarity(rarity)
        if not card:
            await query.answer("Карты не найдены!", show_alert=True)
            return
    
    user["cards"].append(card)
    user["total_crafts"] += 1
    save_users(users)
    
    emoji = config.RARITY_EMOJI.get(card['rarity'], "⚪")
    rarity_name = config.RARITY_NAMES.get(card['rarity'], "")
    limited_tag = " 🎁 ЛИМИТИРОВАННАЯ" if card.get("limited") else ""
    
    text = f"🎉 *КРАФТ УСПЕШЕН!*\n\n{emoji} *{card['name']} {card['surname']}*\nРедкость: {rarity_name}{limited_tag}\n\n_{card['description']}_"
    
    points = get_user_points(user)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=main_keyboard_inline(points))


async def mycards_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    if not user.get("cards"):
        text = "У вас пока нет карт!"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_main")]])
        await query.edit_message_text(text, reply_markup=keyboard)
        return
    
    await query.edit_message_text("🃏 *Мои карты*", parse_mode='Markdown', reply_markup=mycards_keyboard(user, 0, None))


async def mycards_page_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    _, rarity_filter, page = query.data.split("_")
    page = int(page)
    if rarity_filter == "all":
        rarity_filter = None
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    await query.edit_message_text("🃏 *Мои карты*", parse_mode='Markdown', reply_markup=mycards_keyboard(user, page, rarity_filter))


async def leaderboard_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    leaderboard = get_leaderboard(users)
    
    text = "🏆 *Таблица лидеров*\n\n"
    
    for i, entry in enumerate(leaderboard, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {entry['name']}: {entry['points']} pts\n"
    
    if not leaderboard:
        text = "Пока нет данных!"
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=leaderboard_keyboard())


async def all_cards_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    cards = load_cards()
    
    text = "📋 *Все доступные карты:*\n\n"
    
    for rarity in ['mythic', 'legendary', 'epic', 'rare', 'common']:
        rarity_cards = [c for c in cards if c['rarity'] == rarity and not c.get('limited')]
        if rarity_cards:
            emoji = config.RARITY_EMOJI[rarity]
            name = config.RARITY_NAMES[rarity]
            text += f"{emoji} *{name}* ({len(rarity_cards)}):\n"
            for card in rarity_cards:
                text += f"  • {card['name']} {card['surname']} ({card['points']} pts)\n"
    
    limited_cards = [c for c in cards if c.get('limited')]
    if limited_cards:
        text += f"\n🎁 *Лимитированные:*\n"
        for card in limited_cards:
            emoji = config.RARITY_EMOJI.get(card['rarity'], "🎁")
            text += f"  {emoji} {card['name']} {card['surname']} ({card['points']} pts)\n"
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu")]])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)


async def back_main_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    await send_main_menu(update, context, user)


async def view_card_callback(update: Update, context: CallbackContext):
    """Показать детальную информацию о карте при клике"""
    query = update.callback_query
    await query.answer()
    
    card_id = int(query.data.replace("view_card_", ""))
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    # Ищем карту в коллекции пользователя
    card = None
    for c in user.get("cards", []):
        if c.get("id") == card_id:
            card = c
            break
    
    if not card:
        await query.edit_message_text("Карта не найдена в коллекции!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="mycards_all")]]))
        return
    
    await send_card_detail(update, context, card)


async def delete_card_callback(update: Update, context: CallbackContext):
    """Удалить карту из коллекции"""
    query = update.callback_query
    await query.answer()
    
    card_id = int(query.data.replace("delete_card_", ""))
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    # Удаляем карту из коллекции
    original_count = len(user.get("cards", []))
    user["cards"] = [c for c in user.get("cards", []) if c.get("id") != card_id]
    
    if len(user["cards"]) < original_count:
        save_users(users)
        await query.edit_message_text("🗑️ Карта удалена из коллекции!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К списку карт", callback_data="mycards_all")]]))
    else:
        await query.edit_message_text("Карта не найдена!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="mycards_all")]]))


async def handle_reply_buttons(update: Update, context: CallbackContext):
    """Обработка нажатий на ReplyKeyboard кнопки"""
    text = update.message.text
    
    users = load_users()
    user = get_user(users, update.effective_user.id)
    
    if text == "🎴 Гача":
        await gacha_from_reply(update, context, user, users)
    elif text == "🃏 Мои карты":
        await mycards_callback_from_reply(update, context, user)
    elif text == "👤 Профиль":
        await profile_from_reply(update, context, user)
    elif text == "📋 Меню":
        await menu_from_reply(update, context, user)


async def gacha_from_reply(update, context, user, users):
    """Выполнение гачи из ReplyKeyboard"""
    if config.COOLDOWN_SECONDS > 0:
        last_gacha = user.get("last_gacha", 0)
        if time.time() - last_gacha < config.COOLDOWN_SECONDS:
            remaining = int(config.COOLDOWN_SECONDS - (time.time() - last_gacha))
            await update.message.reply_text(f"⏳ Подождите {remaining} сек!", reply_markup=main_keyboard_reply())
            return
    
    rarity = get_random_rarity()
    is_limited = random.random() < 0.1
    
    if is_limited:
        current_month = datetime.now().strftime("%Y-%m")
        if user.get("limited_month") != current_month:
            user["limited_fragments_this_month"] = 0
            user["limited_month"] = current_month
        
        if user["limited_fragments_this_month"] >= config.LIMITED_FRAGMENTS_PER_MONTH:
            is_limited = False
        else:
            card_data = get_random_limited_card()
            if card_data:
                card, rarity = card_data
                user["limited_fragments_this_month"] += 1
                user["fragments"]["limited"] = user["fragments"].get("limited", 0) + 1
            else:
                is_limited = False
    
    if not is_limited:
        user["fragments"][rarity] += 1
    
    user["total_gacha"] += 1
    user["last_gacha"] = time.time()
    save_users(users)
    
    emoji = config.RARITY_EMOJI.get(rarity, "⚪")
    rarity_name = config.RARITY_NAMES.get(rarity, rarity)
    
    if is_limited:
        limited_text = " 🎁 ЛИМИТИРОВАННАЯ"
        current = user["fragments"].get("limited", 0)
    else:
        limited_text = ""
        current = user["fragments"].get(rarity, 0)
    
    text = f"✨ Вам выпал осколок!\n\n{emoji} *{rarity_name}*{limited_text}\n\nОсколков: {current}/{config.FRAGMENTS_NEEDED}"
    
    if current >= config.FRAGMENTS_NEEDED:
        text += "\n\n🎉 Достаточно для крафта!"
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard_reply())


async def mycards_callback_from_reply(update, context, user):
    """Показать свои карты из ReplyKeyboard"""
    if not user.get("cards"):
        await update.message.reply_text("🃏 У вас пока нет карт!\n\nНачните крутить гачу!", reply_markup=main_keyboard_reply())
        return
    
    await update.message.reply_text("🃏 *Мои карты*", parse_mode='Markdown', reply_markup=mycards_keyboard(user, 0, None))


async def profile_from_reply(update, context, user):
    """Показать профиль из ReplyKeyboard"""
    user_obj = update.effective_user
    created = datetime.fromisoformat(user["created_at"]).strftime("%d.%m.%Y")
    points = get_user_points(user)
    
    text = f"👤 *Профиль*\n\n"
    text += f"Никнейм: {user.get('name') or 'Не установлен'}\n"
    text += f"TG ID: `{user_obj.id}`\n"
    text += f"Круток: {user['total_gacha']}\n"
    text += f"Крафтов: {user['total_crafts']}\n"
    text += f"Дата регистрации: {created}\n"
    text += f"💰 Очки: {points}"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Сменить никнейм", callback_data="setname")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard)


async def menu_from_reply(update, context, user):
    """Показать меню из ReplyKeyboard"""
    text = "📋 *Меню*\n\nВыберите действие:"
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=menu_keyboard())


async def back_menu_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    text = "📋 *Меню*\n\nВыберите действие:"
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=menu_keyboard())


async def noop_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()


def main():
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Error: Set BOT_TOKEN in config.py")
        return
    
    if not os.path.exists(config.CARDS_FILE):
        print(f"Error: {config.CARDS_FILE} not found!")
        return
    
    Path(config.CARDS_DIR).mkdir(exist_ok=True)
    
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(gacha_callback, pattern="^gacha$"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(profile_callback, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(inventory_callback, pattern="^inventory$"))
    app.add_handler(CallbackQueryHandler(craft_menu_callback, pattern="^craft_menu$"))
    app.add_handler(CallbackQueryHandler(craft_do_callback, pattern="^craft_"))
    app.add_handler(CallbackQueryHandler(mycards_callback, pattern="^mycards_all$"))
    app.add_handler(CallbackQueryHandler(mycards_page_callback, pattern="^mycards_"))
    app.add_handler(CallbackQueryHandler(leaderboard_callback, pattern="^leaderboard$"))
    app.add_handler(CallbackQueryHandler(all_cards_callback, pattern="^all_cards$"))
    app.add_handler(CallbackQueryHandler(back_main_callback, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(back_menu_callback, pattern="^back_menu$"))
    app.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop$"))
    app.add_handler(CallbackQueryHandler(view_card_callback, pattern="^view_card_"))
    app.add_handler(CallbackQueryHandler(delete_card_callback, pattern="^delete_card_"))
    
    # Обработчик ReplyKeyboard кнопок
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply_buttons))
    
    # Команда /welcome для повторного показа вступительного сообщения
    app.add_handler(CommandHandler("welcome", send_welcome_message))
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(setname_command, pattern="^setname$")],
        states={SET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, setname_received)]},
        fallbacks=[],
    )
    app.add_handler(conv_handler)
    
    print("Bot started!")
    app.run_polling(allowed_updates=["message", "callback_query"], timeout=30)


if __name__ == "__main__":
    main()