# core/account_manager.py
from typing import List, Dict
from datetime import datetime
from database.db_manager import db_manager
from core.telegram_client import client_manager


class AccountManager:
    """Менеджер аккаунтов"""
    
    def __init__(self, db):
        self.db = db
        self.client_manager = client_manager
    
    def add_account(self, phone: str) -> dict:
        """Добавить аккаунт"""
        # Проверяем существование
        existing = self.db.get_account_by_phone(phone)
        if existing:
            return {'status': 'error', 'message': 'Account already exists'}
        
        # Создаём клиента Telethon (без прокси)
        try:
            self.client_manager.create_client(phone)
        except Exception as e:
            return {'status': 'error', 'message': f'Telethon error: {str(e)}'}
        
        # Сохраняем в БД
        account = self.db.create_account(phone=phone, status='pending_auth')
        if not account:
            return {'status': 'error', 'message': 'Failed to save to database'}
        
        return {'status': 'success', 'message': 'Account created'}
    
    def authorize_account(self, phone: str, code: str, password: str = None) -> dict:
        """Авторизовать аккаунт"""
        result = self.client_manager.verify_code(phone, code, password)
        
        if result['status'] == 'success':
            # Получаем данные пользователя
            user_info = self.client_manager.get_me(phone)
            if user_info:
                # Обновляем в БД
                self.db.update_account(
                    phone=phone,
                    status='active',
                    user_id=user_info['id'],
                    username=user_info['username'],
                    first_name=user_info['first_name'],
                    last_name=user_info['last_name'],
                    is_premium=user_info.get('is_premium', False),
                    last_active=datetime.now()
                )
        return result
    
    def remove_account(self, phone: str) -> dict:
        """Удалить аккаунт"""
        # Удаляем сессию Telethon
        self.client_manager.delete_session(phone)
        # Удаляем из БД
        self.db.delete_account(phone)
        return {'status': 'success', 'message': 'Account removed'}
    
    def get_all_accounts(self) -> List[dict]:
        """Получить все аккаунты как список словарей"""
        accounts = self.db.get_all_accounts()
        
        result = []
        for acc in accounts:
            result.append({
                'id': acc.id,
                'phone': acc.phone,
                'username': acc.username,
                'first_name': acc.first_name,
                'last_name': acc.last_name,
                'status': acc.status,
                'is_premium': acc.is_premium,
                'created_at': acc.created_at.isoformat() if acc.created_at else None,
                'last_active': acc.last_active.isoformat() if acc.last_active else None
            })
        
        return result
    
    def get_account_stats(self, phone: str) -> dict:
        """Статистика аккаунта"""
        account = self.db.get_account_by_phone(phone)
        if not account:
            return {'status': 'error', 'message': 'Account not found'}
        
        is_auth = self.client_manager.is_authorized(phone)
        if not is_auth:
            return {'status': 'error', 'message': 'Not authorized'}
        
        dialogs = self.client_manager.get_dialogs(phone, limit=10)
        channels = self.client_manager.get_channels(phone)
        
        return {
            'status': 'success',
            'data': {
                'phone': phone,
                'username': account.username,
                'dialogs_count': len(dialogs),
                'channels_count': len(channels),
                'is_premium': account.is_premium
            }
        }
