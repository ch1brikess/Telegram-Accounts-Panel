import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from core.telegram_client import client_manager
from config import Config

class AudienceCollector:
    """Сборщик аудитории (легальный)"""
    
    def __init__(self):
        self.client_manager = client_manager
    
    async def search_channels(self, phone: str, query: str, 
                             limit: int = 50) -> dict:
        """Поиск каналов по запросу"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            results = []
            async for result in client.iter_dialogs():
                if query.lower() in result.name.lower():
                    results.append({
                        'id': result.id,
                        'name': result.name,
                        'type': type(result.entity).__name__
                    })
                    if len(results) >= limit:
                        break
            
            return {'status': 'success', 'results': results}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def get_chat_members(self, phone: str, chat_id: str,
                              limit: int = 100,
                              filter_active: bool = True,
                              days_active: int = 30) -> dict:
        """Получить участников чата"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            members = []
            async for member in client.iter_participants(chat_id, limit=limit):
                member_data = {
                    'id': member.id,
                    'username': member.username,
                    'first_name': member.first_name,
                    'last_name': member.last_name,
                    'phone': member.phone,
                    'is_bot': member.bot
                }
                
                # Фильтр по активности (если включен)
                if filter_active and member.status:
                    from telethon.tl.types import UserStatusRecently, UserStatusLastWeek
                    if isinstance(member.status, (UserStatusRecently, UserStatusLastWeek)):
                        members.append(member_data)
                elif not filter_active:
                    members.append(member_data)
            
            return {
                'status': 'success',
                'total': len(members),
                'members': members
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def get_post_commenters(self, phone: str, channel_username: str,
                                  post_id: int, limit: int = 100) -> dict:
        """Получить комментаторов поста"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            commenters = []
            async for comment in client.iter_messages(channel_username, 
                                                     reply_to=post_id,
                                                     limit=limit):
                if comment.sender:
                    commenters.append({
                        'id': comment.sender_id,
                        'username': comment.sender.username if comment.sender else None,
                        'first_name': comment.sender.first_name if comment.sender else None,
                        'message': comment.text,
                        'date': comment.date.isoformat() if comment.date else None
                    })
            
            return {
                'status': 'success',
                'total': len(commenters),
                'commenters': commenters
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def collect_user_info(self, phone: str, username: str) -> dict:
        """Собрать информацию о пользователе"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            user = await client.get_entity(username)
            
            # Получаем фото профиля
            photo = None
            if user.photo:
                photo = await client.download_profile_photo(username)
            
            return {
                'status': 'success',
                'data': {
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'phone': user.phone,
                    'bio': user.about,
                    'is_premium': user.premium,
                    'is_bot': user.bot,
                    'photo_path': photo
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def validate_username(self, phone: str, username: str) -> dict:
        """Проверить существование username"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            entity = await client.get_entity(username)
            return {
                'status': 'success',
                'exists': True,
                'type': type(entity).__name__,
                'data': {
                    'id': entity.id,
                    'title': getattr(entity, 'title', None),
                    'username': entity.username
                }
            }
        except Exception as e:
            return {'status': 'success', 'exists': False, 'message': 'Username not found'}
    
    async def get_similar_channels(self, phone: str, channel_username: str,
                                   limit: int = 20) -> dict:
        """Найти похожие каналы (по участникам)"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            # Получаем участников исходного канала
            members = []
            async for member in client.iter_participants(channel_username, limit=100):
                if member.username:
                    members.append(member.username)
            
            # Ищем каналы, где есть эти участники
            similar = {}
            for member in members:
                try:
                    dialogs = await client.get_dialogs()
                    for dialog in dialogs:
                        if hasattr(dialog.entity, 'username') and dialog.entity.username:
                            key = dialog.entity.username
                            if key not in similar:
                                similar[key] = {
                                    'id': dialog.entity.id,
                                    'title': dialog.entity.title,
                                    'username': dialog.entity.username,
                                    'common_members': 0
                                }
                            similar[key]['common_members'] += 1
                except:
                    continue
            
            # Сортируем по количеству общих участников
            sorted_channels = sorted(similar.values(), 
                                    key=lambda x: x['common_members'], 
                                    reverse=True)[:limit]
            
            return {
                'status': 'success',
                'channels': sorted_channels
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def export_audience(self, phone: str, chat_id: str,
                             output_format: str = 'csv',
                             fields: List[str] = None) -> dict:
        """Экспортировать аудиторию в файл"""
        import csv
        import json
        
        if fields is None:
            fields = ['id', 'username', 'first_name', 'last_name', 'phone']
        
        result = await self.get_chat_members(phone, chat_id, limit=1000)
        
        if result['status'] != 'success':
            return result
        
        members = result['members']
        
        import os
        from pathlib import Path
        exports_dir = Path('exports')
        exports_dir.mkdir(exist_ok=True)
        
        filename = f"audience_{chat_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{output_format}"
        filepath = exports_dir / filename
        
        try:
            if output_format == 'csv':
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fields)
                    writer.writeheader()
                    for member in members:
                        row = {k: member.get(k, '') for k in fields}
                        writer.writerow(row)
            
            elif output_format == 'json':
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(members, f, ensure_ascii=False, indent=2)
            
            return {
                'status': 'success',
                'message': f'Exported {len(members)} members',
                'filepath': str(filepath)
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}