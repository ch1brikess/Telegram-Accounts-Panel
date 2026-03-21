# core/telegram_client.py
import os
import asyncio
import time
import nest_asyncio
from typing import Optional, Dict, List
from telethon import TelegramClient, events
from telethon.errors import (
    SessionPasswordNeededError, 
    PhoneCodeInvalidError,
    FloodWaitError,
    AuthKeyUnregisteredError,
    UserDeactivatedError,
    PhoneNumberInvalidError,
    PhoneNumberBannedError
)

from config import Config
from datetime import datetime

# Применяем nest_asyncio для поддержки вложенных event loops
nest_asyncio.apply()

class TelegramClientManager:
    """Менеджер клиентов Telegram с защитой от ошибок соединения"""
    
    def __init__(self):
        self.clients: Dict[str, TelegramClient] = {}
        self.client_states: Dict[str, dict] = {}
        # Единый event loop для всех клиентов
        self._main_loop = None
        
    def _get_loop(self):
        """Получить или создать главный event loop"""
        if self._main_loop is None or self._main_loop.is_closed():
            self._main_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._main_loop)
        return self._main_loop
        
    def _run(self, coro):
        """Запуск async кода в едином event loop"""
        loop = self._get_loop()
        return loop.run_until_complete(coro)
    
    def _safe_call(self, phone: str, async_func, *args, **kwargs):
        """Безопасный вызов async функции с проверкой клиента"""
        # Пробуем получить существующий клиент или создать новый
        client = self.clients.get(phone)
        
        if not client:
            # Пробуем создать новый клиент
            try:
                client = self.create_client(phone)
            except Exception as e:
                return {'status': 'error', 'message': f'Failed to create client: {str(e)}'}
        
        # Проверяем что клиент подключён (async)
        try:
            if not self._run(client.is_connected()):
                try:
                    self._run(client.connect())
                except Exception as e:
                    return {'status': 'error', 'message': f'Connection failed: {str(e)}'}
        except Exception as e:
            # Если ошибка при проверке - пробуем подключить
            try:
                self._run(client.connect())
            except Exception as conn_e:
                return {'status': 'error', 'message': f'Connection failed: {str(conn_e)}'}
        
        try:
            return self._run(async_func(client, *args, **kwargs))
        except (AuthKeyUnregisteredError, UserDeactivatedError) as e:
            # Сессия недействительна — удаляем клиента
            self._cleanup_client(phone)
            return {'status': 'error', 'message': 'Session invalid, please re-login'}
        except FloodWaitError as e:
            return {'status': 'error', 'message': f'Rate limited, wait {e.seconds}s'}
        except Exception as e:
            # Логируем но не крашим приложение
            print(f"[Telethon] Error for {phone}: {type(e).__name__}: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _cleanup_client(self, phone: str):
        """Безопасная очистка клиента"""
        client = self.clients.get(phone)
        if client:
            try:
                if self._run(client.is_connected()):
                    self._run(client.disconnect())
            except Exception:
                pass  # Игнорируем ошибки при очистке
            finally:
                if phone in self.clients:
                    del self.clients[phone]
                if phone in self.client_states:
                    del self.client_states[phone]
    
    def create_client(self, phone: str) -> TelegramClient:
        """Создать или получить клиента"""
        # Если уже есть — возвращаем
        if phone in self.clients:
            client = self.clients[phone]
            try:
                if self._run(client.is_connected()):
                    return client
            except:
                pass
            # Пытаемся переподключить
            try:
                self._run(client.connect())
                return client
            except Exception:
                self._cleanup_client(phone)
        
        # Создаём новый (без прокси)
        session_path = os.path.join(Config.SESSION_DIR, f"{phone}")
        
        client = TelegramClient(
            session_path,
            Config.API_ID,
            Config.API_HASH,
            auto_reconnect=False,  # Отключаем авто-реконнект, управляем вручную
            flood_sleep_threshold=60
        )
        
        try:
            self._run(client.connect())
            self.clients[phone] = client
            self.client_states[phone] = {
                'created': time.time(),
                'last_used': time.time(),
                'authorized': False
            }
            return client
        except Exception as e:
            self._cleanup_client(phone)
            raise RuntimeError(f'Failed to create client: {e}')
    
    def get_client(self, phone: str) -> Optional[TelegramClient]:
        """Получить клиента с проверкой"""
        client = self.clients.get(phone)
        if client:
            try:
                if self._run(client.is_connected()):
                    self.client_states[phone]['last_used'] = time.time()
                    return client
            except:
                pass
            # Пытаемся переподключить
            try:
                self._run(client.connect())
                self.client_states[phone]['last_used'] = time.time()
                return client
            except Exception:
                self._cleanup_client(phone)
        return None
    
    def is_authorized(self, phone: str) -> bool:
        """Проверить авторизацию"""
        client = self.get_client(phone)
        if not client:
            return False
        try:
            return client.is_user_authorized()
        except Exception:
            return False
    
    def send_code(self, phone: str) -> dict:
        """Отправить код подтверждения"""
        try:
            client = self.create_client(phone)
            
            async def _send_code(c):
                await c.send_code_request(phone)
                return {'status': 'success', 'message': 'Code sent'}
            
            return self._safe_call(phone, _send_code)
        except Exception as e:
            self._cleanup_client(phone)
            return {'status': 'error', 'message': f'Failed to send code: {str(e)}'}
    
    def verify_code(self, phone: str, code: str, password: Optional[str] = None) -> dict:
        """Подтвердить код + сохранить в БД при успехе"""
        from utils.logger import logger
        from database.db_manager import db_manager  # ← Импорт внутри метода
        
        client = self.get_client(phone)
        if not client:
            return {'status': 'error', 'message': 'Client not found'}
        
        logger.info(f"[AUTH] Verifying {phone}, password: {password is not None}")
        
        try:
            if password:
                # 2FA вход
                async def _verify_2fa():
                    await client.sign_in(password=password)
                    return {'status': 'success', 'message': 'Authorized with 2FA'}
                result = self._run(_verify_2fa())
            else:
                # Вход по коду
                async def _verify_code():
                    await client.sign_in(phone=phone, code=code)
                    return {'status': 'success', 'message': 'Authorized'}
                result = self._run(_verify_code())
            
            # ✅ УСПЕХ — сохраняем в БД!
            if result['status'] == 'success':
                logger.info(f"[AUTH] Success for {phone}, saving to DB...")
                
                # Получаем данные пользователя
                try:
                    me = client.get_me()
                    user_data = {
                        'user_id': me.id,
                        'username': me.username,
                        'first_name': me.first_name,
                        'last_name': me.last_name,
                        'is_premium': getattr(me, 'premium', False)
                    }
                    logger.info(f"[AUTH] User data: {user_data}")
                except Exception as e:
                    logger.warning(f"[AUTH] Could not get user info: {e}")
                    user_data = {}
                
                # Сохраняем или обновляем в БД
                try:
                    # Пробуем создать новый аккаунт
                    account = db_manager.create_account(
                        phone=phone,
                        status='active',
                        last_active=datetime.now(),
                        **user_data
                    )
                    if account:
                        logger.info(f"[DB] Saved new account: {phone}")
                    else:
                        # Если уже существует — обновляем
                        db_manager.update_account(
                            phone=phone,
                            status='active',
                            last_active=datetime.now(),
                            **user_data
                        )
                        logger.info(f"[DB] Updated existing account: {phone}")
                except Exception as e:
                    logger.error(f"[DB] Save error: {e}")
                
                # Обновляем состояние
                if phone in self.client_states:
                    self.client_states[phone]['authorized'] = True
                    
            return result
            
        except SessionPasswordNeededError:
            return {'status': '2fa_required', 'message': 'Two-step verification enabled. Password required.'}
        except PhoneCodeInvalidError:
            return {'status': 'error', 'message': 'Invalid code from SMS'}
        except FloodWaitError as e:
            return {'status': 'error', 'message': f'Too many attempts. Wait {e.seconds} seconds'}
        except Exception as e:
            logger.error(f"[AUTH] Error: {type(e).__name__}: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def get_me(self, phone: str) -> Optional[dict]:
        """Получить информацию о пользователе"""
        def _get_me(c):
            me = c.get_me()
            return {
                'id': me.id,
                'phone': me.phone,
                'username': me.username,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'is_premium': getattr(me, 'premium', False)
            }
        
        result = self._safe_call(phone, _get_me)
        return result if result['status'] == 'success' else None
    
    def disconnect_client(self, phone: str) -> bool:
        """Отключить клиента"""
        if phone in self.clients:
            self._cleanup_client(phone)
            return True
        return False
    
    def delete_session(self, phone: str) -> bool:
        """Удалить сессию"""
        # Отключаем клиента
        self.disconnect_client(phone)
        
        # Удаляем файлы сессии
        session_file = os.path.join(Config.SESSION_DIR, f"{phone}.session")
        session_meta = os.path.join(Config.SESSION_DIR, f"{phone}.session-journal")
        
        deleted = False
        for path in [session_file, session_meta]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    deleted = True
                except Exception:
                    pass
        
        return deleted
    
    def get_all_sessions(self) -> List[str]:
        """Получить все сессии"""
        sessions = []
        if os.path.exists(Config.SESSION_DIR):
            for file in os.listdir(Config.SESSION_DIR):
                if file.endswith('.session') and not file.endswith('.session-journal'):
                    sessions.append(file.replace('.session', ''))
        return sessions
    
    def get_dialogs(self, phone: str, limit: int = 100) -> List[dict]:
        """Получить диалоги"""
        def _get_dialogs(c):
            dialogs = []
            for dialog in c.iter_dialogs(limit=limit):
                dialogs.append({
                    'id': dialog.id,
                    'name': dialog.name,
                    'type': type(dialog.entity).__name__,
                    'unread_count': dialog.unread_count
                })
            return dialogs
        
        result = self._safe_call(phone, _get_dialogs)
        return result.get('result', []) if result['status'] == 'success' else []
    
    def get_channels(self, phone: str) -> List[dict]:
        """Получить каналы (sync wrapper)"""
        def _get_channels(c):
            channels = []
            for dialog in c.iter_dialogs():
                from telethon.tl.types import Channel
                if isinstance(dialog.entity, Channel) and getattr(dialog.entity, 'broadcast', False):
                    channels.append({
                        'id': dialog.entity.id,
                        'title': dialog.entity.title,
                        'username': getattr(dialog.entity, 'username', None),
                        'participants_count': getattr(dialog.entity, 'participants_count', 0)
                    })
            return channels
        
        result = self._safe_call(phone, _get_channels)
        if result and result.get('status') == 'success':
            return result.get('result', [])
        return []
    
    def get_groups(self, phone: str) -> List[dict]:
        """Получить группы (sync wrapper)"""
        def _get_groups(c):
            groups = []
            for dialog in c.iter_dialogs():
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
            return groups
        
        result = self._safe_call(phone, _get_groups)
        if result and result.get('status') == 'success':
            return result.get('result', [])
        return []
    
    def get_contacts(self, phone: str) -> List[dict]:
        """Получить контакты"""
        def _get_contacts(c):
            contacts = []
            result = c.get_contacts()
            for contact in result:
                contacts.append({
                    'id': contact.id,
                    'phone': contact.phone,
                    'username': contact.username,
                    'first_name': contact.first_name
                })
            return contacts
        
        result = self._safe_call(phone, _get_contacts)
        return result.get('result', []) if result['status'] == 'success' else []
    
    def qr_login(self, phone: str) -> dict:
        """Вход через QR (упрощённый)"""
        try:
            client = self.create_client(phone)
            
            async def _qr(c):
                qr_login = await c.qr_login()
                return {
                    'status': 'success',
                    'url': qr_login.url,
                    'timeout': getattr(qr_login, 'timeout', 300)
                }
            
            return self._run(_qr(client))
        except Exception as e:
            self._cleanup_client(phone)
            return {'status': 'error', 'message': str(e)}
    
    def check_qr_login(self, phone: str) -> dict:
        """Проверить статус QR (заглушка)"""
        # Для полноценной реализации нужно хранить qr_login объект
        return {'status': 'waiting', 'message': 'Scanning...'}
    
    def cleanup_inactive(self, timeout_seconds: int = 300):
        """Очистить неактивные клиенты"""
        now = time.time()
        to_remove = []
        
        for phone, state in self.client_states.items():
            if now - state['last_used'] > timeout_seconds:
                to_remove.append(phone)
        
        for phone in to_remove:
            print(f"[Telethon] Cleaning up inactive client: {phone}")
            self._cleanup_client(phone)

    # === ASYNC METHODS FOR FLASK ===

    async def get_client_async(self, phone: str):
        """Получить клиента (async версия)"""
        client = self.get_client(phone)
        return client

    async def send_message_async(self, phone: str, recipient: str, message: str):
        """Отправить сообщение (async)"""
        client = await self.get_client_async(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            await client.send_message(recipient, message)
            return {'status': 'success', 'message': 'Message sent'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def get_channels_async(self, phone: str):
        """Получить каналы (async)"""
        client = await self.get_client_async(phone)
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
            return {'status': 'success', 'channels': channels}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def get_groups_async(self, phone: str):
        """Получить группы (async)"""
        client = await self.get_client_async(phone)
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
            return {'status': 'success', 'groups': groups}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

# Global instance
client_manager = TelegramClientManager()