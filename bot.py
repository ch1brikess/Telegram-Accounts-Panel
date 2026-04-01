"""7mGacha - Telegram бот для коллекционирования карт"""
import os
import sys
import asyncio
from pathlib import Path
from telegram import Update
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
from modules.data import (
    load_users, save_users, get_user, is_banned, is_admin, is_season_active,
    send_banned_message, send_off_season_message, get_user_points, load_cards, get_gacha_history_text
)
from modules.handlers import (
    start_command, info_command, welcome_command, admin_command,
    send_welcome_message, send_main_menu,
    accept_rules_callback, reject_rules_callback,
    gacha_callback, menu_callback, profile_callback, inventory_callback,
    craft_menu_callback, craft_do_callback,
    mycards_callback, mycards_page_callback,
    leaderboard_callback, all_cards_callback,
    back_main_callback, gacha_history_callback,
    view_card_callback, delete_card_callback,
    back_menu_callback, noop_callback,
    setname_command, setname_received, SET_NAME
)
from modules.admin_handlers import (
    admin_users_callback, admin_top_callback, admin_test_card_callback,
    admin_ban_callback, admin_unban_callback, admin_stats_callback,
    admin_restart_callback, admin_close_callback, admin_back_callback
)
from modules.keyboards import main_keyboard_reply, menu_keyboard
from cores.security import spam_protection, rate_limiter
from modules.logger import logger


# === Обработчики ReplyKeyboard ===

async def handle_reply_buttons(update: Update, context: CallbackContext):
    """Обработка нажатий на ReplyKeyboard кнопки"""
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    # Проверка для админов - ожидание ввода ID
    if is_admin(user_id):
        text = update.message.text
        
        if context.user_data.get("awaiting_ban_id"):
            context.user_data.pop("awaiting_ban_id", None)
            try:
                target_id = int(text)
                if target_id not in config.BANNED_USERS:
                    config.BANNED_USERS.append(target_id)
                    await update.message.reply_text(f"✅ Пользователь {target_id} забанен!")
                    logger.admin_action(user_id, "banned_user", str(target_id))
                else:
                    await update.message.reply_text(f"ℹ️ Пользователь {target_id} уже в бане.")
            except ValueError:
                await update.message.reply_text("❌ Неверный формат ID. Введите число.")
            return
        
        if context.user_data.get("awaiting_unban_id"):
            context.user_data.pop("awaiting_unban_id", None)
            try:
                target_id = int(text)
                if target_id in config.BANNED_USERS:
                    config.BANNED_USERS.remove(target_id)
                    await update.message.reply_text(f"✅ Пользователь {target_id} разбанен!")
                    logger.admin_action(user_id, "unbanned_user", str(target_id))
                else:
                    await update.message.reply_text(f"ℹ️ Пользователь {target_id} не в бане.")
            except ValueError:
                await update.message.reply_text("❌ Неверный формат ID. Введите число.")
            return
    
    # Проверка на спам
    if not spam_protection.check(user_id, "reply_buttons"):
        await update.message.reply_text("⏳ Слишком много запросов! Пожалуйста, подождите.")
        logger.warning("Spam detected", user_id, "reply_buttons")
        return
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await update.message.reply_text(config.OFF_SEASON_MESSAGE, parse_mode='Markdown')
        return
    
    users = load_users()
    user = get_user(users, user_id)
    
    text = update.message.text
    
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
    import random
    from datetime import datetime
    import time
    from modules.data import get_random_rarity, get_random_limited_card, add_gacha_history
    
    if config.COOLDOWN_SECONDS > 0:
        last_gacha = user.get("last_gacha", 0)
        if time.time() - last_gacha < config.COOLDOWN_SECONDS:
            remaining = int(config.COOLDOWN_SECONDS - (time.time() - last_gacha))
            from modules.data import format_time
            await update.message.reply_text(f"⏳ Подождите {format_time(remaining)}!", reply_markup=None)
            return
    
    rarity = get_random_rarity()
    is_limited = random.random() < 0.1
    card = None
    
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
    card_id = card.get("id") if card else None
    add_gacha_history(user, rarity, is_limited, card_id)
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
    
    text += "\n\n" + get_gacha_history_text(user)
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard_reply())
    logger.gacha_spin(update.effective_user.id, rarity)


async def mycards_callback_from_reply(update, context, user):
    from modules.keyboards import mycards_keyboard
    
    if not user.get("cards"):
        await update.message.reply_text("🃏 У вас пока нет карт!\n\nНачните крутить гачу!", reply_markup=main_keyboard_reply())
        return
    
    await update.message.reply_text("🃏 *Мои карты*", parse_mode='Markdown', reply_markup=mycards_keyboard(user, 0, None))


async def profile_from_reply(update, context, user):
    from datetime import datetime
    
    user_obj = update.effective_user
    user_name = user.get('name') or user_obj.first_name or "Игрок"
    created = datetime.fromisoformat(user["created_at"]).strftime("%d.%m.%Y %H:%M")
    points = get_user_points(user)
    duplicates = user.get("duplicates_count", 0)
    
    text = f"""👤 {user_name}, твой профиль.
➖➖➖➖➖➖
🪪 Твой ник: {user_name}
🆔 Твой айди: {user_obj.id}
🎖️ Всего PTS: {points}
🔄 Повторок: {duplicates}
🥡 Количество круток: {user['total_gacha']}
📆 Регистрация: {created}"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 История круток", callback_data="gacha_history")],
        [InlineKeyboardButton("✏️ Сменить никнейм", callback_data="setname")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard)


async def menu_from_reply(update, context, user):
    user_name = user.get('name') or update.effective_user.first_name or "Игрок"
    user_id = update.effective_user.id
    total_cards = len(user.get("cards", []))
    all_cards = load_cards()
    total_cards_in_game = len(all_cards)
    points = get_user_points(user)
    
    text = f"""👤 [{user_name}](tg://user?id={user_id})
🗺️ Вселенная: 7М класс
🃏 Всего карт: {total_cards} из {total_cards_in_game}
🎖️ Сезонные очки: {points} pts

📋 Выберите действие:"""
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=menu_keyboard())


# === Обработка ошибок ===

async def error_handler(update: Update, context: CallbackContext):
    """Глобальный обработчик ошибок"""
    logger.error_exception(
        update.effective_user.id if update and update.effective_user else 0,
        context.error,
        "callback_error"
    )


# === Главная функция ===

def main():
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.critical("BOT_TOKEN не настроен в config.py!")
        return
    
    if not os.path.exists(config.CARDS_FILE):
        logger.critical(f"Файл {config.CARDS_FILE} не найден!")
        return
    
    Path(config.CARDS_DIR).mkdir(exist_ok=True)
    
    logger.system("Запуск бота...")
    
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    # Регистрация обработчиков команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("welcome", welcome_command))
    app.add_handler(CommandHandler("admin", admin_command))
    
    # Обработчики правил
    app.add_handler(CallbackQueryHandler(accept_rules_callback, pattern="^accept_rules$"))
    app.add_handler(CallbackQueryHandler(reject_rules_callback, pattern="^reject_rules$"))
    
    # Админ-обработчики
    app.add_handler(CallbackQueryHandler(admin_users_callback, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_top_callback, pattern="^admin_top$"))
    app.add_handler(CallbackQueryHandler(admin_test_card_callback, pattern="^admin_test_card$"))
    app.add_handler(CallbackQueryHandler(admin_ban_callback, pattern="^admin_ban$"))
    app.add_handler(CallbackQueryHandler(admin_unban_callback, pattern="^admin_unban$"))
    app.add_handler(CallbackQueryHandler(admin_stats_callback, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_close_callback, pattern="^admin_close$"))
    app.add_handler(CallbackQueryHandler(admin_restart_callback, pattern="^admin_restart$"))
    app.add_handler(CallbackQueryHandler(admin_back_callback, pattern="^admin_back$"))
    
    # Основные callback-обработчики
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
    app.add_handler(CallbackQueryHandler(gacha_history_callback, pattern="^gacha_history$"))
    app.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop$"))
    app.add_handler(CallbackQueryHandler(view_card_callback, pattern="^view_card_"))
    app.add_handler(CallbackQueryHandler(delete_card_callback, pattern="^delete_card_"))
    
    # Обработчик ReplyKeyboard кнопок
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply_buttons))
    
    # Conversation для смены имени
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(setname_command, pattern="^setname$")],
        states={SET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, setname_received)]},
        fallbacks=[],
    )
    app.add_handler(conv_handler)
    
    # Обработка ошибок
    app.add_error_handler(error_handler)
    
    logger.success("Бот успешно запущен!")
    logger.system(f"Admin IDs: {config.ADMIN_IDS}")
    logger.system(f"Banned users: {config.BANNED_USERS}")
    
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()