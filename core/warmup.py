import asyncio
import random
from typing import List, Optional
from datetime import datetime, timedelta
from core.telegram_client import client_manager
from config import Config

class AccountWarmup:
    """Прогрев аккаунтов (имитация живой активности)"""
    
    def __init__(self):
        self.client_manager = client_manager
        self.active_warmups = {}
    
    async def start_warmup(self, phone: str, 
                          duration_minutes: int = 30,
                          actions: List[str] = None) -> dict:
        """Запустить прогрев аккаунта"""
        if actions is None:
            actions = ['read_dialogs', 'view_channels', 'random_delays']
        
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        self.active_warmups[phone] = {
            'start_time': datetime.now(),
            'duration': duration_minutes,
            'actions': actions,
            'running': True
        }
        
        asyncio.create_task(self._warmup_loop(phone))
        
        return {
            'status': 'success',
            'message': f'Warmup started for {duration_minutes} minutes'
        }
    
    async def _warmup_loop(self, phone: str):
        """Цикл прогрева"""
        config = self.active_warmups.get(phone)
        if not config:
            return
        
        client = self.client_manager.get_client(phone)
        end_time = config['start_time'] + timedelta(minutes=config['duration'])
        
        while datetime.now() < end_time and config.get('running', False):
            try:
                action = random.choice(config['actions'])
                
                if action == 'read_dialogs':
                    await self._read_dialogs(client)
                elif action == 'view_channels':
                    await self._view_channels(client)
                elif action == 'random_delays':
                    await asyncio.sleep(random.uniform(30, 120))
                
                # Задержка между действиями
                await asyncio.sleep(random.uniform(10, 60))
                
            except Exception as e:
                print(f"Warmup error for {phone}: {e}")
                await asyncio.sleep(60)
        
        if phone in self.active_warmups:
            self.active_warmups[phone]['running'] = False
    
    async def _read_dialogs(self, client):
        """Чтение диалогов"""
        try:
            async for dialog in client.iter_dialogs(limit=10):
                try:
                    async for message in client.iter_messages(dialog.id, limit=5):
                        pass
                    await asyncio.sleep(random.uniform(2, 10))
                except:
                    continue
        except Exception as e:
            print(f"Error reading dialogs: {e}")
    
    async def _view_channels(self, client):
        """Просмотр каналов"""
        try:
            async for dialog in client.iter_dialogs():
                from telethon.tl.types import Channel
                if isinstance(dialog.entity, Channel) and getattr(dialog.entity, 'broadcast', False):
                    try:
                        await client.get_messages(dialog.id, limit=1)
                        await asyncio.sleep(random.uniform(1, 5))
                    except:
                        continue
        except Exception as e:
            print(f"Error viewing channels: {e}")
    
    async def stop_warmup(self, phone: str) -> dict:
        """Остановить прогрев"""
        if phone in self.active_warmups:
            self.active_warmups[phone]['running'] = False
            del self.active_warmups[phone]
            return {'status': 'success', 'message': 'Warmup stopped'}
        return {'status': 'error', 'message': 'No active warmup'}
    
    async def get_warmup_status(self, phone: str) -> dict:
        """Получить статус прогрева"""
        if phone in self.active_warmups:
            config = self.active_warmups[phone]
            elapsed = (datetime.now() - config['start_time']).seconds // 60
            return {
                'status': 'active',
                'elapsed_minutes': elapsed,
                'remaining_minutes': max(0, config['duration'] - elapsed),
                'actions': config['actions'],
                'running': config.get('running', False)
            }
        return {'status': 'inactive'}
    
    async def schedule_warmup(self, phone: str, 
                             schedule: dict) -> dict:
        """Запланировать прогрев (заглушка)"""
        # schedule: {'time': '09:00', 'duration': 30, 'days': ['mon', 'wed', 'fri']}
        return {'status': 'error', 'message': 'Scheduled warmup not implemented'}  