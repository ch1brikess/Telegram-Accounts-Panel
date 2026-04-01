from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
import config
import json
import os
from datetime import datetime
import random
import time

from modules.data import (
    load_users, save_users, get_user, load_cards, get_user_points,
    get_leaderboard, get_random_rarity, get_random_card_by_rarity,
    get_random_limited_card, format_time, escape_md2, add_gacha_history,
    get_gacha_history_text, is_banned, is_admin, is_season_active,
    send_banned_message, send_off_season_message, safe_edit_message,
    load_rules, load_info, has_accepted_rules, set_accepted_rules,
    get_season_name, load_season_top, save_season_top, is_new_season
)
from modules.keyboards import (
    main_keyboard_reply, main_keyboard_inline, menu_keyboard,
    craft_keyboard, mycards_keyboard, leaderboard_keyboard,
    get_card_detail_keyboard
)
from modules.logger import logger


# === Команды ===

async def start_command(update: Update, context: CallbackContext):
    if not update.message:
        return
    
    user = update.effective_user
    user_id = user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        logger.warning("Banned user tried to start", user_id)
        return
    
    users = load_users()
    user_data = get_user(users, user_id)
    
    if not has_accepted_rules(user_data):
        rules_text = load_rules()
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Принять правила", callback_data="accept_rules")],
            [InlineKeyboardButton("❌ Отклонить", callback_data="reject_rules")]
        ])
        await update.message.reply_text(rules_text, parse_mode='Markdown', reply_markup=keyboard)
        save_users(users)
        logger.info("User needs to accept rules", user_id)
        return
    
    if not is_season_active():
        await update.message.reply_text(config.OFF_SEASON_MESSAGE, parse_mode='Markdown')
        logger.info("User tried to start during off-season", user_id)
        return
    
    if is_new_season():
        await update.message.reply_text(config.NEW_SEASON_MESSAGE, parse_mode='Markdown')
        leaderboard = get_leaderboard(users)
        save_season_top(leaderboard)
        logger.success("New season started, previous top saved", user_id)
    
    save_users(users)
    await send_welcome_message(update, context)
    logger.user_joined(user_id, user.first_name or "Unknown")


async def info_command(update: Update, context: CallbackContext):
    if not update.message:
        return
    
    info_text = load_info()
    await update.message.reply_text(info_text, parse_mode='Markdown')
    logger.user_command(update.effective_user.id, "info")


async def welcome_command(update: Update, context: CallbackContext):
    if not update.message:
        return
    
    if is_banned(update.effective_user.id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await update.message.reply_text(config.OFF_SEASON_MESSAGE, parse_mode='Markdown')
        return
    
    users = load_users()
    user = get_user(users, update.effective_user.id)
    
    if not has_accepted_rules(user):
        await start_command(update, context)
        return
    
    save_users(users)
    await send_welcome_message(update, context)


async def admin_command(update: Update, context: CallbackContext):
    if not update.message:
        return
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет доступа к админ-командам.")
        logger.warning("Non-admin tried to access admin panel", user_id)
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
    
    await update.message.reply_text("⚙️ *Панель администратора*", parse_mode='Markdown', reply_markup=keyboard)
    logger.admin_action(user_id, "opened_admin_panel")


# === Вспомогательные функции ===

async def send_welcome_message(update: Update, context: CallbackContext):
    """Вступительное сообщение"""
    user = update.effective_user
    
    text = f"""👋 Приветствую тебя, Игрок!

📒 Добро пожаловать в 7mGacha — увлекательную игру по коллекционированию карт одноклассников!

🎯 У нас много интересного:
➖➖➖➖➖➖
 - Крути гачу и получай осколки
 - Собирай 6 осколков → крафти карту
 - Строй свою коллекцию
 - Поднимайся в таблице лидеров
 - Лови лимитированные карты
 - Забирай очки за каждую карту

📊 Редкости:
⚡ Обычная (10 очков) — 70%
🌟 Редкая (50 очков) — 20%
🐉 Эпическая (200 очков) — 8%
🩸 Легендарная (1000 очков) — 1.6%
🎯 Мифическая (5000 очков) — 0.4%

🎁 Лимитированные карты появляются каждый месяц — не упусти шанс!"""

    users = load_users()
    user_data = get_user(users, user.id)
    save_users(users)
    
    if update.message:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard_reply())
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard_reply())


async def send_main_menu(update, context, user):
    points = get_user_points(user)
    text = f"👤 {user.get('name') or update.effective_user.first_name}\n"
    text += f"💰 Очки: {points}\n\n"
    text += "Выберите действие:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=main_keyboard_reply())
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=main_keyboard_inline(points))


# === Callback обработчики ===

async def accept_rules_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    set_accepted_rules(user)
    save_users(users)
    
    await query.edit_message_text(config.WELCOME_AFTER_RULES)
    await send_welcome_message(update, context)
    logger.success("User accepted rules", query.from_user.id)


async def reject_rules_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Вы отклонили правила. Бот не может быть использован.")
    logger.warning("User rejected rules", query.from_user.id)


async def gacha_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
    users = load_users()
    user = get_user(users, user_id)
    
    # Проверка cooldown
    if config.COOLDOWN_SECONDS > 0:
        last_gacha = user.get("last_gacha", 0)
        if time.time() - last_gacha < config.COOLDOWN_SECONDS:
            remaining = int(config.COOLDOWN_SECONDS - (time.time() - last_gacha))
            await query.answer(f"Подождите {format_time(remaining)}!", show_alert=True)
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
    
    points = get_user_points(user)
    await safe_edit_message(query, text, parse_mode='Markdown', reply_markup=main_keyboard_inline(points))
    
    logger.gacha_spin(user_id, rarity)


async def menu_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    user_name = user.get('name') or query.from_user.first_name or "Игрок"
    user_id = query.from_user.id
    total_cards = len(user.get("cards", []))
    all_cards = load_cards()
    total_cards_in_game = len(all_cards)
    points = get_user_points(user)
    
    text = f"""👤 [{user_name}](tg://user?id={user_id})
🗺️ Вселенная: 7М класс
🃏 Всего карт: {total_cards} из {total_cards_in_game}
🎖️ Сезонные очки: {points} pts

📋 Выберите действие:"""
    
    await safe_edit_message(query, text, parse_mode='Markdown', reply_markup=menu_keyboard())
    logger.user_action(user_id, "opened_menu")


async def profile_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    user_obj = query.from_user
    user_name = user.get('name') or user_obj.first_name or "Игрок"
    user_id = query.from_user.id
    created = datetime.fromisoformat(user["created_at"]).strftime("%d.%m.%Y %H:%M")
    
    points = get_user_points(user)
    duplicates = user.get("duplicates_count", 0)
    
    text = f"""👤 [{user_name}](tg://user?id={user_id}), твой профиль.
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
    
    try:
        await safe_edit_message(query, text, parse_mode='Markdown', reply_markup=keyboard)
    except Exception:
        await context.bot.send_message(chat_id=query.from_user.id, text=text, parse_mode='Markdown', reply_markup=keyboard)
    
    logger.user_action(user_id, "viewed_profile")


async def inventory_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
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
        [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
    ])
    
    await safe_edit_message(query, text, parse_mode='Markdown', reply_markup=keyboard)
    logger.user_action(user_id, "viewed_inventory")


async def craft_menu_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
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
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
    
    await safe_edit_message(query, text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    logger.user_action(user_id, "opened_craft_menu")


async def craft_do_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
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
    
    existing_card = None
    for c in user.get("cards", []):
        if c.get("id") == card["id"]:
            existing_card = c
            break
    
    is_duplicate = False
    
    if existing_card:
        is_duplicate = True
        existing_card["duplicates"] = existing_card.get("duplicates", 0) + 1
        card_points = card.get("points", 0)
        
        user["total_points"] = user.get("total_points", 0) + card_points
        user["duplicates_count"] = user.get("duplicates_count", 0) + 1
        
        total_copies = existing_card.get("duplicates", 0) + 1
        total_points_for_card = card_points * total_copies
        
        emoji = config.RARITY_EMOJI.get(card['rarity'], "⚪")
        rarity_name = config.RARITY_NAMES.get(card['rarity'], "")
        limited_tag = " 🎁 ЛИМИТИРОВАННАЯ" if card.get("limited") else ""
        
        text = f"🔄 *ПОВТОРКА!*\n\n{emoji} *{card['name']} {card['surname']}*\nРедкость: {rarity_name}{limited_tag}\n\n_{card['description']}_\n\nПовторок: {existing_card['duplicates']} (+1)\nЗачислено PTS: +{card_points}\nВсего за эту карту: {total_points_for_card} pts"
    else:
        card["duplicates"] = 0
        user["cards"].append(card)
        
        user["total_points"] = user.get("total_points", 0) + card.get("points", 0)
        
        emoji = config.RARITY_EMOJI.get(card['rarity'], "⚪")
        rarity_name = config.RARITY_NAMES.get(card['rarity'], "")
        limited_tag = " 🎁 ЛИМИТИРОВАННАЯ" if card.get("limited") else ""
        
        text = f"🎉 *КРАФТ УСПЕШЕН!*\n\n{emoji} *{card['name']} {card['surname']}*\nРедкость: {rarity_name}{limited_tag}\n\n_{card['description']}_\n\nЗачислено PTS: +{card.get('points', 0)}"
    
    user["total_crafts"] += 1
    save_users(users)
    
    image_path = card.get("image_path", "")
    has_image = image_path and os.path.exists(image_path)
    
    points = get_user_points(user)
    
    if has_image:
        try:
            await context.bot.send_photo(
                chat_id=query.from_user.id,
                photo=open(image_path, 'rb'),
                caption=text,
                parse_mode='Markdown',
                reply_markup=main_keyboard_inline(points),
                read_timeout=60,
                write_timeout=60,
                connect_timeout=30
            )
            try:
                await query.delete_message()
            except:
                pass
            logger.craft_card(user_id, f"{card['name']} {card['surname']}", is_duplicate)
            return
        except Exception as e:
            logger.error_exception(user_id, e, "sending craft photo")
            print(f"Error sending photo in craft: {e}")
    
    try:
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=main_keyboard_inline(points))
    except Exception:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=text,
            parse_mode='Markdown',
            reply_markup=main_keyboard_inline(points)
        )
    
    logger.craft_card(user_id, f"{card['name']} {card['surname']}", is_duplicate)


async def mycards_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    if not user.get("cards"):
        text = "У вас пока нет карт!"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_main")]])
        await safe_edit_message(query, text, reply_markup=keyboard)
        return
    
    all_cards = load_cards()
    rarity_counts = {}
    for r in ['common', 'rare', 'epic', 'legendary', 'mythic', 'limited']:
        total_in_game = len([c for c in all_cards if (c.get('rarity') == r) or (r == 'limited' and c.get('limited'))])
        user_count = len([c for c in user.get('cards', []) if (c.get('rarity') == r) or (r == 'limited' and c.get('limited'))])
        rarity_counts[r] = (user_count, total_in_game)
    
    rarity_text = "\n".join([
        f"{config.RARITY_EMOJI.get(r, '⚪')}: {count[0]}/{count[1]}" 
        for r, count in rarity_counts.items() if count[1] > 0
    ])
    header_text = f"🃏 *Мои карты*\n\n{rarity_text}"
    
    await safe_edit_message(query, header_text, parse_mode='Markdown', reply_markup=mycards_keyboard(user, 0, None))
    logger.user_action(user_id, "viewed_cards")


async def mycards_page_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
    _, rarity_filter, page = query.data.split("_")
    page = int(page)
    if rarity_filter == "all":
        rarity_filter = None
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    all_cards = load_cards()
    rarity_counts = {}
    for r in ['common', 'rare', 'epic', 'legendary', 'mythic', 'limited']:
        total_in_game = len([c for c in all_cards if (c.get('rarity') == r) or (r == 'limited' and c.get('limited'))])
        user_count = len([c for c in user.get('cards', []) if (c.get('rarity') == r) or (r == 'limited' and c.get('limited'))])
        rarity_counts[r] = (user_count, total_in_game)
    
    rarity_text = "\n".join([
        f"{config.RARITY_EMOJI.get(r, '⚪')}: {count[0]}/{count[1]}" 
        for r, count in rarity_counts.items() if count[1] > 0
    ])
    header_text = f"🃏 *Мои карты*\n\n{rarity_text}"
    
    await safe_edit_message(query, header_text, parse_mode='Markdown', reply_markup=mycards_keyboard(user, page, rarity_filter))


async def leaderboard_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
    users = load_users()
    leaderboard = get_leaderboard(users)
    
    if not leaderboard:
        text = "🏆 *Таблица лидеров*\n\nПока нет данных!"
        await safe_edit_message(query, text, parse_mode='Markdown', reply_markup=leaderboard_keyboard())
        return
    
    text = "🏆 *Таблица лидеров*\n\n"
    
    for i, entry in enumerate(leaderboard[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {entry['name']}: {entry['points']} pts\n"
    
    await safe_edit_message(query, text, parse_mode='Markdown', reply_markup=leaderboard_keyboard())
    logger.user_action(user_id, "viewed_leaderboard")


async def all_cards_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
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
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_main")]])
    await safe_edit_message(query, text, parse_mode='Markdown', reply_markup=keyboard)
    logger.user_action(user_id, "viewed_all_cards")


async def back_main_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    await send_main_menu(update, context, user)


async def gacha_history_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    text = get_gacha_history_text(user)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data="profile")]
    ])
    
    await safe_edit_message(query, text, parse_mode='Markdown', reply_markup=keyboard)
    logger.user_action(user_id, "viewed_gacha_history")


async def view_card_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
    card_id = int(query.data.replace("view_card_", ""))
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    card = None
    for c in user.get("cards", []):
        if c.get("id") == card_id:
            card = c
            break
    
    if not card:
        await safe_edit_message(query, "Карта не найдена в коллекции!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="mycards_all")]]))
        return
    
    duplicates = card.get("duplicates", 0)
    card_points = card.get("points", 0)
    total_points = card_points * (duplicates + 1)
    
    emoji = config.RARITY_EMOJI.get(card.get("rarity"), "⚪")
    rarity_name = config.RARITY_NAMES.get(card.get("rarity"), "")
    limited_tag = " 🎁 *ЛИМИТИРОВАННАЯ*" if card.get("limited") else ""
    
    text = f"{emoji} *{card['name']} {card['surname']}*\n"
    text += f"Редкость: {rarity_name}{limited_tag}\n\n"
    text += f"_{card['description']}_\n\n"
    text += f"💰 Всего очков: {total_points}\n"
    text += f"🔄 Повторок: {duplicates}"
    
    image_path = card.get("image_path", "")
    has_image = image_path and os.path.exists(image_path)
    
    if has_image:
        try:
            await query.answer()
            await context.bot.send_photo(
                chat_id=query.from_user.id,
                photo=open(image_path, 'rb'),
                caption=text,
                parse_mode='Markdown',
                reply_markup=get_card_detail_keyboard(card['id']),
                read_timeout=60,
                write_timeout=60,
                connect_timeout=30
            )
            logger.user_action(user_id, f"viewed_card_{card['name']}")
            return
        except Exception as e:
            logger.error_exception(user_id, e, "sending card photo")
            print(f"Error sending photo: {e}")
    
    if query:
        await query.answer()
        try:
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_card_detail_keyboard(card['id']))
        except Exception:
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=text,
                parse_mode='Markdown',
                reply_markup=get_card_detail_keyboard(card['id'])
            )


async def delete_card_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
    card_id = int(query.data.replace("delete_card_", ""))
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    original_count = len(user.get("cards", []))
    user["cards"] = [c for c in user.get("cards", []) if c.get("id") != card_id]
    
    if len(user["cards"]) < original_count:
        save_users(users)
        await safe_edit_message(query, "🗑️ Карта удалена из коллекции!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К списку карт", callback_data="mycards_all")]]))
        logger.user_action(user_id, f"deleted_card_{card_id}")
    else:
        await safe_edit_message(query, "Карта не найдена!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="mycards_all")]]))


async def back_menu_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
    users = load_users()
    user = get_user(users, query.from_user.id)
    
    user_name = user.get('name') or query.from_user.first_name or "Игрок"
    user_id = query.from_user.id
    total_cards = len(user.get("cards", []))
    all_cards = load_cards()
    total_cards_in_game = len(all_cards)
    points = get_user_points(user)
    
    text = f"""👤 [{user_name}](tg://user?id={user_id})
🗺️ Вселенная: 7М класс
🃏 Всего карт: {total_cards} из {total_cards_in_game}
🎖️ Сезонные очки: {points} pts

📋 Выберите действие:"""
    
    await safe_edit_message(query, text, parse_mode='Markdown', reply_markup=menu_keyboard())


async def noop_callback(update: Update, context: CallbackContext):
    if not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()


# === Conversation handlers ===

SET_NAME = 1

async def setname_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if is_banned(user_id):
        await send_banned_message(update, context)
        return
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return
    
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Введите новый никнейм:")
    else:
        await update.message.reply_text("Введите новый никнейм:")
    return SET_NAME


async def setname_received(update: Update, context: CallbackContext):
    if is_banned(update.effective_user.id):
        await send_banned_message(update, context)
        return ConversationHandler.END
    
    if not is_season_active():
        await send_off_season_message(update, context)
        return ConversationHandler.END
    
    users = load_users()
    user = get_user(users, update.effective_user.id)
    user["name"] = update.message.text[:50]
    save_users(users)
    
    await update.message.reply_text(f"Никнейм установлен: {user['name']}")
    await send_main_menu(update, context, user)
    
    logger.user_action(update.effective_user.id, f"changed_name_to_{user['name']}")
    return ConversationHandler.END