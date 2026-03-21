# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Получаем абсолютный путь к корню проекта
PROJECT_ROOT = Path(__file__).parent.resolve()

class Config:
    # Telegram API
    API_ID = int(os.getenv('API_ID', ''))
    API_HASH = os.getenv('API_HASH', '')
    
    # === БАЗА ДАННЫХ В КОРНЕ ПРОЕКТА ===
    DATABASE_PATH = PROJECT_ROOT / 'accounts.db'
    DATABASE_URL = f'sqlite:///{DATABASE_PATH}'
    
    # Папки
    SESSION_DIR = PROJECT_ROOT / 'sessions'
    LOG_DIR = PROJECT_ROOT / 'logs'
    
    # Настройки
    MAX_CONCURRENT_CLIENTS = 10
    REQUEST_DELAY = 1.0
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-prod')
    
    # === AUTHENTICATION ===
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    # === OLLAMA (Report text generation) ===
    OLLAMA_ENABLED = os.getenv('OLLAMA_ENABLED', 'false').lower() == 'true'
    OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2')
    
    # === THEMES ===
    THEMES = ['dark', 'light']
    DEFAULT_THEME = os.getenv('DEFAULT_THEME', 'dark')
    
    AUTO_ARCHIVE_ON_JOIN = os.getenv('AUTO_ARCHIVE_ON_JOIN', 'false').lower() == 'true'
    MUTE_ON_JOIN = os.getenv('MUTE_ON_JOIN', 'false').lower() == 'true'
    
    @classmethod
    def init_dirs(cls):
        """Создаём необходимые папки"""
        for directory in [cls.SESSION_DIR, cls.LOG_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
        cls.load_api_settings()
    
    @classmethod
    def load_api_settings(cls):
        """Загрузить настройки Telegram API из БД"""
        try:
            from database.db_manager import db_manager
            saved_api_id = db_manager.get_setting('telegram_api_id')
            saved_api_hash = db_manager.get_setting('telegram_api_hash')
            
            if saved_api_id:
                cls.API_ID = int(saved_api_id)
            if saved_api_hash:
                cls.API_HASH = saved_api_hash
                
            print(f"[CONFIG] Telegram API loaded: ID={cls.API_ID}, Hash={cls.API_HASH[:8]}...")
        except Exception as e:
            print(f"[CONFIG] Could not load API settings: {e}")

    TELETHON_RECONNECT_ATTEMPTS = 3
    TELETHON_TIMEOUT = 120
    TELETHON_FLOOD_SLEEP = 60
