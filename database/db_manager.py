# database/db_manager.py
import os
from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool
from config import Config

Base = declarative_base()

class Account(Base):
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    status = Column(String(20), default='pending_auth')  # pending_auth, active, banned, inactive
    is_premium = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Blacklist(Base):
    __tablename__ = 'blacklist'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(20), nullable=True)
    username = Column(String(100), nullable=True)
    user_id = Column(Integer, nullable=True)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class AppSettings(Base):
    """Настройки приложения"""
    __tablename__ = 'app_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class ReportLog(Base):
    """Логи репортов"""
    __tablename__ = 'report_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(20), nullable=False)
    target_type = Column(String(20), nullable=False)  # 'user' or 'message'
    target_id = Column(Integer, nullable=True)
    target_username = Column(String(100), nullable=True)
    reason = Column(String(50), nullable=True)
    report_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class Stats(Base):
    """Статистика"""
    __tablename__ = 'stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    accounts_banned = Column(Integer, default=0)
    reports_sent = Column(Integer, default=0)
    messages_sent = Column(Integer, default=0)
    channels_joined = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class AdminProfile(Base):
    """Профиль администратора"""
    __tablename__ = 'admin_profiles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=True)
    avatar = Column(String(255), nullable=True)  # URL or base64
    custom_id = Column(String(20), unique=True, nullable=True)  # Кастомный ID
    theme = Column(String(20), default='dark')
    created_at = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class AdminChatMessage(Base):
    """Сообщения чата между админами"""
    __tablename__ = 'admin_chat_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_username = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

class DatabaseManager:
    """Простой и надёжный менеджер БД"""
    
    def __init__(self):
        # Путь к БД в корне проекта
        self.db_path = str(Config.DATABASE_PATH)
        
        # Создаём engine с настройками для потокобезопасности и избежания блокировки
        self.engine = create_engine(
            f'sqlite:///{self.db_path}',
            connect_args={
                'check_same_thread': False,
                'timeout': 30,  # Таймаут ожидания разблокировки
                'isolation_level': 'DEFERRED'
            },
            poolclass=StaticPool,
            echo=False
        )
        
        # Создаём таблицы
        Base.metadata.create_all(self.engine)
        
        # scoped_session для потокобезопасности
        self.session_factory = scoped_session(sessionmaker(bind=self.engine))
        
        # Миграция: добавляем колонку custom_id если не существует
        self._migrate_add_custom_id()
        
        print(f"[DB] Database initialized: {self.db_path}")
    
    def get_session(self):
        """Получить новую сессию"""
        return self.session_factory()
    
    def _commit_and_close(self, session, success=True):
        """Безопасное завершение сессии"""
        try:
            if success:
                session.commit()
            else:
                session.rollback()
        except Exception as e:
            session.rollback()
            print(f"[DB] Commit error: {e}")
        finally:
            session.close()
    
    def _migrate_add_custom_id(self):
        """Миграция: добавить колонку custom_id если не существует"""
        try:
            from sqlalchemy import text
            session = self.get_session()
            # Проверяем существует ли колонка
            result = session.execute(text("PRAGMA table_info(admin_profiles)"))
            columns = [row[1] for row in result]
            if 'custom_id' not in columns:
                session.execute(text("ALTER TABLE admin_profiles ADD COLUMN custom_id VARCHAR(20)"))
                session.commit()
                print("[DB] Migration: added custom_id column")
            session.close()
        except Exception as e:
            print(f"[DB] Migration error: {e}")
    
    # === ACCOUNT METHODS ===
    
    def create_account(self, phone: str, **kwargs) -> Optional[Account]:
        """Создать аккаунт"""
        session = self.get_session()
        try:
            # Проверяем существование
            existing = session.query(Account).filter(Account.phone == phone).first()
            if existing:
                print(f"[DB] Account {phone} already exists")
                return existing
            
            account = Account(phone=phone, **kwargs)
            session.add(account)
            self._commit_and_close(session)
            print(f"[DB] Created account: {phone}")
            return account
        except Exception as e:
            self._commit_and_close(session, success=False)
            print(f"[DB] Create error: {e}")
            return None
    
    def get_account_by_phone(self, phone: str) -> Optional[Account]:
        """Получить аккаунт по номеру"""
        session = self.get_session()
        try:
            return session.query(Account).filter(Account.phone == phone).first()
        finally:
            session.close()
    
    def get_all_accounts(self) -> List[Account]:
        """Получить ВСЕ аккаунты"""
        session = self.get_session()
        try:
            accounts = session.query(Account).all()
            print(f"[DB] Retrieved {len(accounts)} accounts")
            return accounts
        finally:
            session.close()
    
    def update_account(self, phone: str, **kwargs) -> bool:
        """Обновить аккаунт"""
        session = self.get_session()
        try:
            account = session.query(Account).filter(Account.phone == phone).first()
            if not account:
                return False
            
            for key, value in kwargs.items():
                if hasattr(account, key):
                    setattr(account, key, value)
            
            account.last_active = datetime.now()
            self._commit_and_close(session)
            print(f"[DB] Updated account: {phone}")
            return True
        except Exception as e:
            self._commit_and_close(session, success=False)
            print(f"[DB] Update error: {e}")
            return False
    
    def delete_account(self, phone: str) -> bool:
        """Удалить аккаунт"""
        session = self.get_session()
        try:
            account = session.query(Account).filter(Account.phone == phone).first()
            if account:
                session.delete(account)
                self._commit_and_close(session)
                print(f"[DB] Deleted account: {phone}")
                return True
            return False
        except Exception as e:
            self._commit_and_close(session, success=False)
            print(f"[DB] Delete error: {e}")
            return False
    
    def get_inactive_accounts(self, days: int = 7) -> List[Account]:
        """Получить неактивные аккаунты"""
        session = self.get_session()
        try:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=days)
            return session.query(Account).filter(Account.last_active < cutoff).all()
        finally:
            session.close()
    
    # === BLACKLIST METHODS ===
    
    def add_to_blacklist(self, phone: str = None, username: str = None, 
                        user_id: int = None, reason: str = None) -> Optional[Blacklist]:
        """Добавить в чёрный список"""
        session = self.get_session()
        try:
            entry = Blacklist(phone=phone, username=username, user_id=user_id, reason=reason)
            session.add(entry)
            self._commit_and_close(session)
            return entry
        except Exception as e:
            self._commit_and_close(session, success=False)
            return None
    
    def is_blacklisted(self, phone: str = None, username: str = None, 
                      user_id: int = None) -> bool:
        """Проверить чёрный список"""
        session = self.get_session()
        try:
            query = session.query(Blacklist)
            if phone:
                query = query.filter(Blacklist.phone == phone)
            if username:
                query = query.filter(Blacklist.username == username)
            if user_id:
                query = query.filter(Blacklist.user_id == user_id)
            return query.first() is not None
        finally:
            session.close()
    
    # === SETTINGS METHODS ===
    
    def get_setting(self, key: str) -> Optional[str]:
        """Получить настройку"""
        session = self.get_session()
        try:
            setting = session.query(AppSettings).filter(AppSettings.key == key).first()
            return setting.value if setting else None
        finally:
            session.close()
    
    def set_setting(self, key: str, value: str) -> bool:
        """Установить настройку"""
        session = self.get_session()
        try:
            setting = session.query(AppSettings).filter(AppSettings.key == key).first()
            if setting:
                setting.value = value
            else:
                setting = AppSettings(key=key, value=value)
                session.add(setting)
            self._commit_and_close(session)
            return True
        except Exception as e:
            self._commit_and_close(session, success=False)
            return False
    
    def get_all_settings(self) -> dict:
        """Получить все настройки"""
        session = self.get_session()
        try:
            settings = session.query(AppSettings).all()
            return {s.key: s.value for s in settings}
        finally:
            session.close()
    
    def get_banned_count(self) -> int:
        """Получить количество забаненных аккаунтов"""
        session = self.get_session()
        try:
            return session.query(Account).filter(Account.status == 'banned').count()
        finally:
            session.close()
    
    # === REPORT LOG METHODS ===
    
    def add_report_log(self, phone: str, target_type: str, target_id: int = None,
                       target_username: str = None, reason: str = None, 
                       report_text: str = None) -> Optional[ReportLog]:
        """Добавить лог репорта"""
        session = self.get_session()
        try:
            log = ReportLog(
                phone=phone,
                target_type=target_type,
                target_id=target_id,
                target_username=target_username,
                reason=reason,
                report_text=report_text
            )
            session.add(log)
            self._commit_and_close(session)
            return log
        except Exception as e:
            self._commit_and_close(session, success=False)
            return None
    
    def get_report_stats(self) -> dict:
        """Получить статистику репортов"""
        session = self.get_session()
        try:
            total_reports = session.query(ReportLog).count()
            by_phone = session.query(ReportLog.phone, 
                func.count(ReportLog.id)).group_by(ReportLog.phone).all()
            return {
                'total': total_reports,
                'by_phone': {p: c for p, c in by_phone}
            }
        finally:
            session.close()
    
    # === STATS METHODS ===
    
    def get_stats(self) -> dict:
        """Получить статистику системы"""
        session = self.get_session()
        try:
            stats = session.query(Stats).first()
            if not stats:
                stats = Stats()
                session.add(stats)
                self._commit_and_close(session)
            
            return {
                'accounts_banned': stats.accounts_banned,
                'reports_sent': stats.reports_sent,
                'messages_sent': stats.messages_sent,
                'channels_joined': stats.channels_joined
            }
        finally:
            session.close()
    
    def update_stats(self, **kwargs) -> bool:
        """Обновить статистику"""
        session = self.get_session()
        try:
            stats = session.query(Stats).first()
            if not stats:
                stats = Stats()
                session.add(stats)
            
            for key, value in kwargs.items():
                if hasattr(stats, key):
                    current = getattr(stats, key, 0) or 0
                    setattr(stats, key, current + value)
            
            self._commit_and_close(session)
            return True
        except Exception as e:
            self._commit_and_close(session, success=False)
            return False
    
    # === ADMIN PROFILE METHODS ===
    
    def create_admin_profile(self, username: str, display_name: str = None, custom_id: str = None) -> Optional[AdminProfile]:
        """Создать профиль админа"""
        session = self.get_session()
        try:
            profile = AdminProfile(username=username, display_name=display_name or username, custom_id=custom_id)
            session.add(profile)
            self._commit_and_close(session)
            return profile
        except Exception as e:
            self._commit_and_close(session, success=False)
            return None
    
    def get_admin_profile(self, username: str) -> Optional[AdminProfile]:
        """Получить профиль админа"""
        session = self.get_session()
        try:
            return session.query(AdminProfile).filter(AdminProfile.username == username).first()
        finally:
            session.close()
    
    def update_admin_profile(self, username: str, **kwargs) -> bool:
        """Обновить профиль админа"""
        session = self.get_session()
        try:
            profile = session.query(AdminProfile).filter(AdminProfile.username == username).first()
            if not profile:
                profile = AdminProfile(username=username)
                session.add(profile)
            
            for key, value in kwargs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            
            self._commit_and_close(session)
            return True
        except Exception as e:
            self._commit_and_close(session, success=False)
            return False
    
    def get_all_admin_profiles(self) -> List[AdminProfile]:
        """Получить все профили админов"""
        session = self.get_session()
        try:
            return session.query(AdminProfile).all()
        finally:
            session.close()
    
    def generate_unique_admin_id(self) -> str:
        """Сгенерировать уникальный ID администратора"""
        import random
        import string
        session = self.get_session()
        try:
            # Получаем все существующие ID
            existing_ids = set(p.custom_id for p in session.query(AdminProfile.custom_id).all() if p.custom_id)
            
            while True:
                # Генерируем ID формата XXXX
                new_id = ''.join(random.choices(string.digits, k=4))
                if new_id not in existing_ids:
                    return new_id
        finally:
            session.close()
    
    # === ADMIN CHAT METHODS ===
    
    def add_admin_chat_message(self, sender_username: str, message: str) -> Optional[AdminChatMessage]:
        """Добавить сообщение в чат админов"""
        session = self.get_session()
        try:
            msg = AdminChatMessage(sender_username=sender_username, message=message)
            session.add(msg)
            self._commit_and_close(session)
            return msg
        except Exception as e:
            self._commit_and_close(session, success=False)
            return None
    
    def get_admin_chat_messages(self, limit: int = 50) -> List[AdminChatMessage]:
        """Получить сообщения чата админов"""
        session = self.get_session()
        try:
            return session.query(AdminChatMessage).order_by(
                AdminChatMessage.created_at.desc()
            ).limit(limit).all()
        finally:
            session.close()
    
    def update_admin_chat_message(self, message_id: int, new_message: str) -> bool:
        """Обновить сообщение чата"""
        session = self.get_session()
        try:
            msg = session.query(AdminChatMessage).filter(AdminChatMessage.id == message_id).first()
            if msg:
                msg.message = new_message
                self._commit_and_close(session)
                return True
            return False
        except Exception as e:
            self._commit_and_close(session, success=False)
            return False
    
    def delete_admin_chat_message(self, message_id: int) -> bool:
        """Удалить сообщение чата"""
        session = self.get_session()
        try:
            msg = session.query(AdminChatMessage).filter(AdminChatMessage.id == message_id).first()
            if msg:
                session.delete(msg)
                self._commit_and_close(session)
                return True
            return False
        except Exception as e:
            self._commit_and_close(session, success=False)
            return False
    
    def get_blacklist_with_source(self) -> List[Blacklist]:
        """Получить чёрный список с информацией об источнике (только из панели)"""
        session = self.get_session()
        try:
            return session.query(Blacklist).filter(
                Blacklist.phone.isnot(None)
            ).order_by(Blacklist.created_at.desc()).all()
        finally:
            session.close()

# Global instance
db_manager = DatabaseManager()