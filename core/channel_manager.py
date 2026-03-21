import asyncio
from typing import List, Dict, Optional
from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, EditPhotoRequest
from telethon.tl.functions.messages import CreateChatRequest
from telethon.tl.types import InputChatUploadedPhoto
from core.telegram_client import client_manager
from config import Config

class ChannelManager:
    """Менеджер каналов и чатов"""
    
    def __init__(self):
        self.client_manager = client_manager
    
    async def create_channel(self, phone: str, title: str, 
                            description: str = '', 
                            is_broadcast: bool = True,
                            is_megagroup: bool = False) -> dict:
        """Создать канал"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            result = await client(CreateChannelRequest(
                title=title,
                about=description,
                broadcast=is_broadcast,
                megagroup=is_megagroup
            ))
            
            return {
                'status': 'success',
                'message': 'Channel created',
                'channel_id': result.chats[0].id,
                'username': result.chats[0].username
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def create_group(self, phone: str, title: str, 
                          users: List[str] = None) -> dict:
        """Создать группу"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            # Получаем объекты пользователей
            user_entities = []
            if users:
                for user in users:
                    entity = await client.get_entity(user)
                    user_entities.append(entity)
            
            result = await client(CreateChatRequest(
                title=title,
                users=user_entities
            ))
            
            return {
                'status': 'success',
                'message': 'Group created',
                'chat_id': result.chats[0].id
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def set_channel_username(self, phone: str, channel_id: int,
                                   username: str) -> dict:
        """Установить username канала"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.set_username(channel_id, username)
            return {'status': 'success', 'message': 'Username set'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def set_channel_photo(self, phone: str, channel_id: int,
                               photo_path: str) -> dict:
        """Установить фото канала"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            photo = InputChatUploadedPhoto(file=photo_path)
            await client(EditPhotoRequest(channel=channel_id, photo=photo))
            return {'status': 'success', 'message': 'Photo set'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def get_channel_info(self, phone: str, channel_username: str) -> dict:
        """Получить информацию о канале"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            entity = await client.get_entity(channel_username)
            return {
                'status': 'success',
                'data': {
                    'id': entity.id,
                    'title': entity.title,
                    'username': entity.username,
                    'participants_count': entity.participants_count,
                    'description': entity.about,
                    'is_verified': entity.verified,
                    'is_scam': entity.scam
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def get_channel_participants(self, phone: str, channel_username: str,
                                       limit: int = 100) -> dict:
        """Получить участников канала"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            participants = []
            async for participant in client.iter_participants(channel_username, limit=limit):
                participants.append({
                    'id': participant.id,
                    'username': participant.username,
                    'first_name': participant.first_name,
                    'last_name': participant.last_name,
                    'phone': participant.phone
                })
            
            return {
                'status': 'success',
                'total': len(participants),
                'participants': participants
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def ban_user(self, phone: str, chat_id: int, 
                      user_id: int, revoke_messages: bool = False) -> dict:
        """Заблокировать пользователя в чате"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.edit_permissions(chat_id, user_id, view_messages=False)
            if revoke_messages:
                await client.delete_user_history(chat_id, user_id)
            return {'status': 'success', 'message': 'User banned'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def unban_user(self, phone: str, chat_id: int, user_id: int) -> dict:
        """Разблокировать пользователя"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.edit_permissions(chat_id, user_id, view_messages=True)
            return {'status': 'success', 'message': 'User unbanned'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def get_admins(self, phone: str, chat_id: int) -> dict:
        """Получить администраторов чата"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            admins = []
            async for admin in client.iter_admins(chat_id):
                admins.append({
                    'id': admin.id,
                    'username': admin.username,
                    'first_name': admin.first_name,
                    'is_creator': admin.creator
                })
            
            return {'status': 'success', 'admins': admins}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def leave_chat(self, phone: str, chat_id: int) -> dict:
        """Выйти из чата/канала"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.leave_entity(chat_id)
            return {'status': 'success', 'message': 'Left chat'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def delete_channel(self, phone: str, channel_id: int) -> dict:
        """Удалить канал (если вы владелец)"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.delete_dialog(channel_id)
            return {'status': 'success', 'message': 'Channel deleted'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def export_chat_invite(self, phone: str, chat_id: int) -> dict:
        """Экспортировать ссылку-приглашение"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            invite = await client.export_chat_invite(chat_id)
            return {
                'status': 'success',
                'invite_link': invite.link
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def create_invite_link(self, phone: str, chat_id: int,
                                expire_date: int = None,
                                usage_limit: int = None) -> dict:
        """Создать ссылку-приглашение с параметрами"""
        client = await self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            from telethon.tl.functions.messages import ExportChatInviteRequest
            
            result = await client(ExportChatInviteRequest(
                peer=chat_id,
                expire_date=expire_date,
                usage_limit=usage_limit
            ))
            
            return {
                'status': 'success',
                'invite_link': result.link
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def get_channels(self, phone: str) -> dict:
        """Получить список каналов аккаунта"""
        client = await self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            channels = []
            async for dialog in client.iter_dialogs():
                from telethon.tl.types import Channel
                if isinstance(dialog.entity, Channel) and getattr(dialog.entity, 'broadcast', False):
                    channels.append({
                        'id': dialog.entity.id,
                        'title': dialog.entity.title,
                        'username': getattr(dialog.entity, 'username', None),
                        'participants_count': getattr(dialog.entity, 'participants_count', 0)
                    })
            return {'status': 'success', 'channels': channels, 'total': len(channels)}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def get_groups(self, phone: str) -> dict:
        """Получить список групп аккаунта"""
        client = await self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            groups = []
            async for dialog in client.iter_dialogs():
                from telethon.tl.types import Channel, Chat
                is_group = isinstance(dialog.entity, Chat) or (
                    isinstance(dialog.entity, Channel) and 
                    getattr(dialog.entity, 'megagroup', False)
                )
                if is_group:
                    groups.append({
                        'id': dialog.entity.id,
                        'title': dialog.entity.title,
                        'username': getattr(dialog.entity, 'username', None)
                    })
            return {'status': 'success', 'groups': groups, 'total': len(groups)}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}