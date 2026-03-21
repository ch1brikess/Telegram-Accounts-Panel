import asyncio
import random
from typing import List, Dict, Optional
from telethon import TelegramClient
from telethon.tl.types import InputMediaUploadedPhoto, InputMediaUploadedDocument
from core.telegram_client import client_manager
from utils.spintax import process_spintax
from config import Config

class MessageHandler:
    """Обработчик сообщений"""
    
    def __init__(self):
        self.client_manager = client_manager
    
    async def send_message(self, phone: str, recipient: str, message: str, 
                          media_path: Optional[str] = None, 
                          parse_mode: str = 'html',
                          use_spintax: bool = False) -> dict:
        """Отправить сообщение"""
        # Получаем клиент через sync метод, потом используем async
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            # Обработка spintax
            if use_spintax:
                message = process_spintax(message)
            
            # Отправка
            if media_path:
                if media_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    media = InputMediaUploadedPhoto(file=media_path)
                else:
                    media = InputMediaUploadedDocument(file=media_path)
                
                await client.send_message(recipient, message, file=media, parse_mode=parse_mode)
            else:
                await client.send_message(recipient, message, parse_mode=parse_mode)
            
            # Задержка для безопасности
            await asyncio.sleep(Config.REQUEST_DELAY)
            
            return {'status': 'success', 'message': 'Message sent'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def send_messages_batch(self, phone: str, recipients: List[str], 
                                  message: str, delay_range: tuple = (1, 3),
                                  use_spintax: bool = False) -> dict:
        """Отправить сообщения пакетом"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        results = []
        successful = 0
        failed = 0
        
        for recipient in recipients:
            try:
                msg = process_spintax(message) if use_spintax else message
                await client.send_message(recipient, msg)
                successful += 1
                results.append({'recipient': recipient, 'status': 'success'})
                
                # Случайная задержка
                await asyncio.sleep(random.uniform(*delay_range))
            except Exception as e:
                failed += 1
                results.append({'recipient': recipient, 'status': 'error', 'message': str(e)})
        
        return {
            'status': 'completed',
            'total': len(recipients),
            'successful': successful,
            'failed': failed,
            'results': results
        }
    
    async def send_to_dialog(self, phone: str, dialog_id: int, message: str,
                            reply_to: Optional[int] = None) -> dict:
        """Отправить сообщение в диалог"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.send_message(dialog_id, message, reply_to=reply_to)
            return {'status': 'success', 'message': 'Message sent to dialog'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def send_to_channel(self, phone: str, channel_username: str, 
                             message: str, media_path: Optional[str] = None) -> dict:
        """Отправить сообщение в канал (если вы админ)"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            if media_path:
                await client.send_file(channel_username, media_path, caption=message)
            else:
                await client.send_message(channel_username, message)
            
            return {'status': 'success', 'message': 'Message posted to channel'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def forward_messages(self, phone: str, from_chat: str, to_chat: str,
                              message_ids: List[int]) -> dict:
        """Переслать сообщения"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.forward_messages(to_chat, message_ids, from_chat)
            return {'status': 'success', 'message': f'Forwarded {len(message_ids)} messages'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def delete_messages(self, phone: str, chat_id: str, 
                             message_ids: List[int], revoke: bool = True) -> dict:
        """Удалить сообщения"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.delete_messages(chat_id, message_ids, revoke=revoke)
            return {'status': 'success', 'message': f'Deleted {len(message_ids)} messages'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def get_messages(self, phone: str, chat_id: str, 
                          limit: int = 50, offset: int = 0) -> dict:
        """Получить сообщения из чата"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            messages = []
            async for message in client.iter_messages(chat_id, limit=limit, offset=offset):
                messages.append({
                    'id': message.id,
                    'text': message.text,
                    'date': message.date.isoformat() if message.date else None,
                    'from_id': message.sender_id,
                    'reply_to': message.reply_to.reply_to_msg_id if message.reply_to else None
                })
            
            return {'status': 'success', 'messages': messages}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def send_voice(self, phone: str, recipient: str, voice_path: str) -> dict:
        """Отправить голосовое сообщение"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.send_file(recipient, voice_path, voice_note=True)
            return {'status': 'success', 'message': 'Voice message sent'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def send_file(self, phone: str, recipient: str, file_path: str,
                       caption: str = '') -> dict:
        """Отправить файл"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.send_file(recipient, file_path, caption=caption)
            return {'status': 'success', 'message': 'File sent'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def edit_message(self, phone: str, chat_id: str, 
                          message_id: int, new_text: str) -> dict:
        """Редактировать сообщение"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.edit_message(chat_id, message_id, new_text)
            return {'status': 'success', 'message': 'Message edited'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def pin_message(self, phone: str, chat_id: str, 
                         message_id: int, notify: bool = False) -> dict:
        """Закрепить сообщение"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.pin_message(chat_id, message_id, notify=notify)
            return {'status': 'success', 'message': 'Message pinned'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def unpin_message(self, phone: str, chat_id: str) -> dict:
        """Открепить сообщение"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.unpin_message(chat_id)
            return {'status': 'success', 'message': 'Message unpinned'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}