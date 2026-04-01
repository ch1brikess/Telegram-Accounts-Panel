"""Клавиатуры бота"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
import config


def main_keyboard_reply():
    """Главное меню в виде ReplyKeyboard"""
    keyboard = [
        ["🎴 Гача", "🃏 Мои карты"],
        ["👤 Профиль", "📋 Меню"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def main_keyboard_inline(points):
    """Главное меню в виде Inline клавиатуры"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚒️ Заново", callback_data="gacha")],
        [InlineKeyboardButton("📋 Меню", callback_data="menu")],
        [InlineKeyboardButton("🃏 Мои карты", callback_data="mycards_all")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")]
    ])


def get_card_detail_keyboard(card_id):
    """Кнопки для просмотра карты"""
    return InlineKeyboardMarkup([
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
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
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
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])
