"""Админ-обработчики"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
import os

from modules.data import (
    load_users, load_cards, get_user_points, get_leaderboard,
    is_admin, safe_edit_message
)
from modules.logger import logger
import config


async def admin_users_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Нет доступа", show_alert=True)
        return
    
    users = load_users()
    user_list = [(uid, u) for uid, u in users.items() if isinstance(u, dict)]
    text = f"👥 *Всего пользователей: {len(user_list)}*\n\n"
    
    for i, (user_id, user) in enumerate(user_list[:20]):
        name = user.get("name") or f"User{user_id}"
        cards = len(user.get("cards", []))
        points = get_user_points(user)
        text += f"{i+1}. {name}: {cards} карт, {points} pts\n"
    
    if len(user_list) > 20:
        text += f"\n... и ещё {len(user_list) - 20} пользователей"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
    logger.admin_action(query.from_user.id, "viewed_users_list")


async def admin_top_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Нет доступа", show_alert=True)
        return
    
    users = load_users()
    leaderboard = get_leaderboard(users)
    
    text = "🏆 *Топ игроков:*\n\n"
    for i, entry in enumerate(leaderboard[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {entry['name']}: {entry['points']} pts\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
    logger.admin_action(query.from_user.id, "viewed_top")


async def admin_test_card_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Нет доступа", show_alert=True)
        return
    
    cards = load_cards()
    if not cards:
        await query.answer("Нет карт для теста!", show_alert=True)
        return
    
    test_card = None
    for card in cards:
        if card.get("image_path") and os.path.exists(card.get("image_path", "")):
            test_card = card
            break
    
    if not test_card:
        test_card = cards[0]
    
    emoji = config.RARITY_EMOJI.get(test_card.get("rarity"), "⚪")
    text = f"{emoji} *Тестовая карта*\n\n_{test_card['description']}_"
    
    image_path = test_card.get("image_path", "")
    if image_path and os.path.exists(image_path):
        try:
            await context.bot.send_photo(
                chat_id=query.from_user.id,
                photo=open(image_path, 'rb'),
                caption=text,
                parse_mode='Markdown'
            )
            await query.answer("Карта отправлена!")
            logger.admin_action(query.from_user.id, "test_card_sent", f"card={test_card['name']}")
            return
        except Exception as e:
            logger.error_exception(query.from_user.id, e, "sending test card")
            print(f"Error sending test photo: {e}")
    
    await context.bot.send_message(chat_id=query.from_user.id, text=text, parse_mode='Markdown')


async def admin_ban_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await query.edit_message_text(
        "🚫 *Бани пользователя*\n\nВведите ID пользователя которого нужно забанить:",
        parse_mode='Markdown'
    )
    context.user_data["awaiting_ban_id"] = True
    logger.admin_action(query.from_user.id, "opened_ban_menu")


async def admin_unban_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await query.edit_message_text(
        "✅ *Разбан пользователя*\n\nВведите ID пользователя которого нужно разбанить:",
        parse_mode='Markdown'
    )
    context.user_data["awaiting_unban_id"] = True
    logger.admin_action(query.from_user.id, "opened_unban_menu")


async def admin_stats_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Нет доступа", show_alert=True)
        return
    
    users = load_users()
    cards = load_cards()
    
    user_list = [u for u in users.values() if isinstance(u, dict)]
    
    total_cards = sum(len(u.get("cards", [])) for u in user_list)
    total_gacha = sum(u.get("total_gacha", 0) for u in user_list)
    total_crafts = sum(u.get("total_crafts", 0) for u in user_list)
    total_points = sum(get_user_points(u) for u in user_list)
    
    text = f"""📊 *Статистика бота:*

👥 Пользователей: {len(user_list)}
🃏 Карт в игре: {len(cards)}
🎴 Всего карт у игроков: {total_cards}
🎰 Всего круток: {total_gacha}
⚒️ Всего крафтов: {total_crafts}
🎖️ Всего очков: {total_points}
🚫 Забанено: {len(config.BANNED_USERS)}"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
    ])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
    logger.admin_action(query.from_user.id, "viewed_stats")


async def admin_restart_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await query.edit_message_text("🔄 Для перезагрузки бота перезапустите процесс вручную.\n\nИспользуйте Ctrl+C и запустите бота снова.")
    logger.admin_action(query.from_user.id, "requested_restart")


async def admin_close_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.delete_message()
    logger.admin_action(query.from_user.id, "closed_admin_panel")


async def admin_back_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Нет доступа", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users")],
        [InlineKeyboardButton("🏆 Топ сезона", callback_data="admin_top")],
        [InlineKeyboardButton("📤 Тест отправки карты", callback_data="admin_test_card")],
        [InlineKeyboardButton("🔄 Перезагрузить бота", callback_data="admin_restart")],
        [InlineKeyboardButton("🚫 Забанить ID", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ Разбанить ID", callback_data="admin_unban")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Закрыть", callback_data="admin_close")]
    ])
    
    await query.edit_message_text("⚙️ *Панель администратора*", parse_mode='Markdown', reply_markup=keyboard)