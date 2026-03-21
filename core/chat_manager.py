# core/chat_manager.py
import asyncio
import nest_asyncio
from typing import List, Dict, Optional
from datetime import datetime
from telethon import functions
from core.telegram_client import client_manager
from config import Config
from database.db_manager import db_manager

nest_asyncio.apply()

class ChatManager:
    """Управление чатами и сообщениями"""
    
    def __init__(self):
        self.client_manager = client_manager
    
    def get_dialogs(self, phone: str) -> dict:
        """Получить все диалоги аккаунта"""
        from utils.logger import logger
        
        logger.info(f"[CHAT] get_dialogs called for {phone}")
        
        # Сначала создаём клиент синхронно (до запуска async)
        try:
            client = client_manager.get_client(phone)
            if not client:
                # Пробуем создать
                client = client_manager.create_client(phone)
            if not client:
                return {'status': 'error', 'message': 'Client not found'}
        except Exception as e:
            logger.error(f"[CHAT] Failed to get/create client: {e}")
            return {'status': 'error', 'message': f'Client error: {str(e)}'}
        
        async def _fetch_dialogs_async():
            # Проверяем авторизацию
            if not await client.is_user_authorized():
                return {'status': 'error', 'message': 'Not authorized'}
            
            dialogs = []
            async for dialog in client.iter_dialogs(limit=200):
                entity = dialog.entity
                
                # Определяем тип чата
                chat_type = 'private'
                if hasattr(entity, 'broadcast') and entity.broadcast:
                    chat_type = 'channel'
                elif hasattr(entity, 'megagroup') and entity.megagroup:
                    chat_type = 'supergroup'
                elif hasattr(entity, 'group') and entity.group:
                    chat_type = 'group'
                
                dialogs.append({
                    'id': dialog.id,
                    'title': getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown'),
                    'username': getattr(entity, 'username', None),
                    'type': chat_type,
                    'unread_count': dialog.unread_count,
                    'date': dialog.date.isoformat() if dialog.date else None
                })
            
            return {'status': 'success', 'dialogs': dialogs, 'total': len(dialogs)}
        
        # Используем единый event loop из client_manager
        try:
            return client_manager._run(_fetch_dialogs_async())
        except Exception as e:
            logger.error(f"[CHAT] Error fetching dialogs: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def get_messages(self, phone: str, chat_id: int, 
                     limit: int = 50, offset: int = 0) -> dict:
        """Получить сообщения из чата с группировкой по датам"""
        from utils.logger import logger
        
        # Сначала создаём клиент синхронно
        try:
            client = client_manager.get_client(phone)
            if not client:
                client = client_manager.create_client(phone)
            if not client:
                return {'status': 'error', 'message': 'Client not found'}
        except Exception as e:
            logger.error(f"[CHAT] Failed to get/create client: {e}")
            return {'status': 'error', 'message': f'Client error: {str(e)}'}
        
        async def _fetch_messages_async():
            if not await client.is_user_authorized():
                return {'status': 'error', 'message': 'Not authorized'}
            
            try:
                messages_by_date = {}
                
                async for message in client.iter_messages(chat_id, limit=limit):
                    if not message.date:
                        continue
                    
                    date_key = message.date.strftime('%Y-%m-%d')
                    
                    # Получаем информацию об отправителе
                    sender_name = 'Unknown'
                    sender_id = None
                    if message.sender:
                        sender_id = message.sender_id
                        if hasattr(message.sender, 'first_name') and message.sender.first_name:
                            sender_name = message.sender.first_name
                            if hasattr(message.sender, 'last_name') and message.sender.last_name:
                                sender_name += ' ' + message.sender.last_name
                        elif hasattr(message.sender, 'username') and message.sender.username:
                            sender_name = '@' + message.sender.username
                    
                    msg_data = {
                        'id': message.id,
                        'text': message.text or message.message,
                        'date': message.date.isoformat(),
                        'time': message.date.strftime('%H:%M'),
                        'sender_id': sender_id,
                        'sender_name': sender_name,
                        'out': getattr(message, 'out', False),
                        'reply_to': message.reply_to.reply_to_msg_id if message.reply_to else None
                    }
                    
                    if date_key not in messages_by_date:
                        messages_by_date[date_key] = []
                    messages_by_date[date_key].append(msg_data)
                
                # Сортируем даты
                sorted_dates = sorted(messages_by_date.keys(), reverse=True)
                
                return {
                    'status': 'success',
                    'messages': messages_by_date,
                    'dates': sorted_dates,
                    'total': sum(len(msgs) for msgs in messages_by_date.values())
                }
            except Exception as e:
                return {'status': 'error', 'message': str(e)}
        
        # Используем единый event loop из client_manager
        try:
            return client_manager._run(_fetch_messages_async())
        except Exception as e:
            logger.error(f"[CHAT] Error fetching messages: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def send_message_to_chat(self, phone: str, chat_id: int, 
                                   message: str) -> dict:
        """Отправить сообщение в чат"""
        client = self.client_manager.get_client(phone)
        if not client or not await client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.send_message(chat_id, message)
            
            # Обновляем статистику
            db_manager.update_stats(messages_sent=1)
            
            return {'status': 'success', 'message': 'Message sent'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def send_message_by_username(self, phone: str, username: str,
                                       message: str) -> dict:
        """Отправить сообщение по username"""
        client = self.client_manager.get_client(phone)
        if not client or not await client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.send_message(username, message)
            
            db_manager.update_stats(messages_sent=1)
            
            return {'status': 'success', 'message': 'Message sent'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def join_channel(self, phone: str, channel_link: str,
                          archive: bool = None, mute: bool = None) -> dict:
        """Подписаться на канал по ссылке"""
        client = self.client_manager.get_client(phone)
        if not client or not await client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            # Извлекаем username из ссылки
            if 't.me/' in channel_link:
                channel_username = channel_link.split('t.me/')[-1].split('/')[0]
            else:
                channel_username = channel_link.strip('@')
            
            # Подписываемся
            entity = await client.get_entity(channel_username)
            await client(entity)
            
            # Архивировать если нужно
            if archive is None:
                archive = Config.AUTO_ARCHIVE_ON_JOIN
            if archive:
                try:
                    await client.archive_dialog(entity)
                except:
                    pass
            
            # Отключить звук если нужно
            if mute is None:
                mute = Config.MUTE_ON_JOIN
            if mute:
                try:
                    await client.edit_permissions(entity, notify=False)
                except:
                    pass
            
            db_manager.update_stats(channels_joined=1)
            
            return {'status': 'success', 'message': f'Joined {channel_username}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def add_reaction(self, phone: str, channel_link: str, 
                          message_id: int, emoji: str) -> dict:
        """Добавить реакцию на сообщение"""
        client = self.client_manager.get_client(phone)
        if not client or not await client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            # Извлекаем username
            if 't.me/' in channel_link:
                channel_username = channel_link.split('t.me/')[-1].split('/')[0]
            else:
                channel_username = channel_link.strip('@')
            
            # Получаем сообщение
            message = await client.get_messages(channel_username, ids=message_id)
            
            # Добавляем реакцию
            from telethon.tl.types import ReactionEmoji
            reaction = ReactionEmoji(emoticon=emoji)
            await client.react_to_message(channel_username, message_id, reaction)
            
            return {'status': 'success', 'message': 'Reaction added'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def archive_chat(self, phone: str, chat_id: int) -> dict:
        """Архивировать чат"""
        from utils.logger import logger
        
        client = self.client_manager.get_client(phone)
        if not client or not await client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            # Получаем entity по ID
            entity = await client.get_entity(chat_id)
            await client.archive_dialog(entity)
            logger.info(f"[CHAT] Archived chat {chat_id} for {phone}")
            return {'status': 'success', 'message': 'Chat archived'}
        except Exception as e:
            logger.error(f"[CHAT] Archive error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def toggle_mute(self, phone: str, chat_id: int, mute: bool = True) -> dict:
        """Включить/выключить уведомления для чата"""
        from utils.logger import logger
        
        client = self.client_manager.get_client(phone)
        if not client or not await client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            entity = await client.get_entity(chat_id)
            # Используем edit_permissions для управления уведомлениями
            await client.edit_permissions(entity, notify=not mute)
            action = 'muted' if mute else 'unmuted'
            logger.info(f"[CHAT] Chat {chat_id} {action} for {phone}")
            return {'status': 'success', 'message': f'Chat {action}'}
        except Exception as e:
            logger.error(f"[CHAT] Mute error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def block_user(self, phone: str, chat_id: int) -> dict:
        """Заблокировать пользователя/чат"""
        from utils.logger import logger
        
        client = self.client_manager.get_client(phone)
        if not client or not await client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            entity = await client.get_entity(chat_id)
            await client(functions.contacts.BlockRequest(entity))
            logger.info(f"[CHAT] Blocked chat {chat_id} for {phone}")
            return {'status': 'success', 'message': 'User blocked'}
        except Exception as e:
            logger.error(f"[CHAT] Block error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def mark_as_read(self, phone: str, chat_id: int) -> dict:
        """Отметить чат как прочитанный"""
        from utils.logger import logger
        
        client = self.client_manager.get_client(phone)
        if not client or not await client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            entity = await client.get_entity(chat_id)
            # Отмечаем как прочитанное
            await client.send_read_acknowledge(entity)
            logger.info(f"[CHAT] Marked as read: {chat_id} for {phone}")
            return {'status': 'success', 'message': 'Marked as read'}
        except Exception as e:
            logger.error(f"[CHAT] Mark as read error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def delete_chat(self, phone: str, chat_id: int) -> dict:
        """Удалить чат (выйти из чата/канала или удалить диалог)"""
        from utils.logger import logger
        
        client = self.client_manager.get_client(phone)
        if not client or not await client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            entity = await client.get_entity(chat_id)
            
            # Проверяем тип сущности и выполняем соответствующее действие
            from telethon.tl.types import Channel, Chat
            
            if isinstance(entity, Channel) and getattr(entity, 'broadcast', False):
                # Это канал - выходим из него
                await client.delete_dialog(entity)
                logger.info(f"[CHAT] Left channel {chat_id} for {phone}")
                return {'status': 'success', 'message': 'Left channel'}
            elif isinstance(entity, Channel) and getattr(entity, 'megagroup', False):
                # Это супергруппа - выходим
                await client.delete_dialog(entity)
                logger.info(f"[CHAT] Left supergroup {chat_id} for {phone}")
                return {'status': 'success', 'message': 'Left supergroup'}
            elif isinstance(entity, Chat):
                # Это обычная группа - выходим
                await client.delete_dialog(entity)
                logger.info(f"[CHAT] Left group {chat_id} for {phone}")
                return {'status': 'success', 'message': 'Left group'}
            else:
                # Личный чат - просто удаляем диалог
                await client.delete_dialog(entity)
                logger.info(f"[CHAT] Deleted dialog {chat_id} for {phone}")
                return {'status': 'success', 'message': 'Dialog deleted'}
        except Exception as e:
            logger.error(f"[CHAT] Delete error: {e}")
            return {'status': 'error', 'message': str(e)}

chat_manager = ChatManager()
