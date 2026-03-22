# app.py
import os
import sys
import io
import asyncio
import json
import hashlib
import secrets
from pathlib import Path
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from config import Config
from database.db_manager import db_manager
from core.telegram_client import client_manager
from core.account_manager import AccountManager
from core.message_handler import MessageHandler
from core.channel_manager import ChannelManager
from core.audience_collector import AudienceCollector
from core.warmup import AccountWarmup

from core.chat_manager import chat_manager
from core.report_manager import report_manager
from core.osint_manager import osint_manager
from utils.logger import logger
import nest_asyncio


# === ADMIN AUTH ===
ADMINS_FILE = Path(__file__).parent / 'admins.json'


def load_admins():
    """Загружает админов из файла"""
    if ADMINS_FILE.exists():
        with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_admins(admins):
    """Сохраняет админов в файл"""
    with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
        json.dump(admins, f, indent=4, ensure_ascii=False)


def hash_password(password: str, salt: str = '') -> str:
    """Хэширует пароль - простой SHA256 для совместимости"""
    combined = password + salt
    return hashlib.sha256(combined.encode()).hexdigest()


def verify_admin(username: str, password: str) -> bool:
    """Проверяет админа"""
    admins = load_admins()
    
    if username not in admins:
        return False
    
    admin = admins[username]
    stored_hash = admin.get('password_hash', '')
    salt = admin.get('salt', '')
    
    computed = hash_password(password, salt)
    return computed == stored_hash

# === FIX CONSOLE ENCODING ===
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
# ============================

Config.init_dirs()

# Используем nest_asyncio для совместимости
import nest_asyncio
nest_asyncio.apply()

# Глобальный event loop для async вызовов
_main_loop = None

def get_event_loop():
    """Получить или создать event loop"""
    global _main_loop
    try:
        _main_loop = asyncio.get_event_loop()
        if _main_loop.is_closed():
            _main_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_main_loop)
    except RuntimeError:
        _main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_main_loop)
    return _main_loop

def run_async(coro):
    """Запустить async корутину в синхронном контексте"""
    # Используем единый event loop из client_manager
    return client_manager._run(coro)

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 час

# Менеджеры
account_manager = AccountManager(db_manager)
message_handler = MessageHandler()
channel_manager = ChannelManager()
audience_collector = AudienceCollector()
warmup_manager = AccountWarmup()

# === AUTH DECORATOR ===
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated_function

# === Инициализация сессий при старте ===
def load_all_sessions():
    """Загрузить все сессии аккаунтов при старте"""
    try:
        accounts = account_manager.get_all_accounts()
        loaded = 0
        for account in accounts:
            phone = account.get('phone')
            if phone:
                try:
                    client_manager.get_client(phone)
                    loaded += 1
                    logger.info(f"[INIT] Loaded session: {phone}")
                except Exception as e:
                    logger.error(f"[INIT] Failed to load {phone}: {e}")
        
        logger.info(f"[INIT] Loaded {loaded}/{len(accounts)} sessions")
        return loaded
    except Exception as e:
        logger.error(f"[INIT] Error loading sessions: {e}")
        return 0

# Загружаем сессии при импорте
print("=" * 50)
print("[INIT] TG Manager Pro - Ready to use!")
print("[INIT] Sessions will be loaded on demand")
print("=" * 50)

# === API для загрузки сессий ===
@app.route('/api/sessions/load', methods=['POST'])
def reload_sessions():
    """Принудительная перезагрузка всех сессий"""
    loaded = load_all_sessions()
    return jsonify({'status': 'success', 'loaded': loaded, 'message': f'Загружено {loaded} сессий'})

@app.route('/api/sessions/status', methods=['GET'])
def sessions_status():
    """Статус загрузки сессий"""
    accounts = account_manager.get_all_accounts()
    loaded_count = len(client_manager.clients)
    return jsonify({
        'total': len(accounts),
        'loaded': loaded_count,
        'accounts': [a.get('phone') for a in accounts]
    })

# === NOTIFICATIONS CHECK ===
notifications_queue = []

def check_notifications():
    """Проверяет новые уведомления от всех аккаунтов"""
    global notifications_queue
    notifications = []
    
    # Копируем ключи, чтобы избежать ошибки изменения словаря во время итерации
    phones = list(client_manager.clients.keys())
    
    for phone in phones:
        try:
            client = client_manager.get_client(phone)
            if not client:
                continue
            
            # Используем единый event loop из client_manager
            async def check_client():
                if not await client.is_user_authorized():
                    return []
                
                dialogs_list = []
                async for dialog in client.iter_dialogs(limit=10):
                    dialogs_list.append(dialog)
                return dialogs_list
            
            dialogs = client_manager._run(check_client())
            
            for dialog in dialogs:
                if hasattr(dialog, 'unread_count') and dialog.unread_count > 0:
                    peer = dialog.entity
                    name = getattr(peer, 'title', None) or getattr(peer, 'first_name', '') or str(peer.id)
                    notifications.append({
                        'phone': phone,
                        'chat_name': name,
                        'unread': dialog.unread_count,
                        'last_message': str(getattr(dialog, 'last_message', '') or '')[:50]
                    })
        except Exception as e:
            logger.error(f"[NOTIFY] Error checking {phone}: {e}")
    
    notifications_queue = notifications
    return notifications

@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    """Получить уведомления"""
    notifications = check_notifications()
    return jsonify({'notifications': notifications})

# ==================== ROUTES ====================

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/')
def index():
    if not session.get('authenticated'):
        return render_template('login.html')
    return render_template('index.html')

# === AUTH ROUTES ===

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Аутентификация"""
    data = request.get_json(force=True, silent=True) or {}
    username = data.get('username', '')
    password = data.get('password', '')
    
    # Проверяем через admins.json
    admins = load_admins()
    
    if username in admins:
        admin = admins[username]
        salt = admin.get('salt', '')
        stored_hash = admin.get('password_hash', '')
        
        # Хэшируем входящий пароль
        computed = hash_password(password, salt)
        
        if computed == stored_hash:
            session['authenticated'] = True
            session['username'] = username
            session.permanent = True
            
            # Сохраняем последний использованный username
            db_manager.set_setting('last_login_username', username)
            
            return jsonify({'status': 'success', 'message': 'Logged in'})
    
    return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401


@app.route('/api/auth/last-username', methods=['GET'])
def get_last_username():
    """Получить последний использованный username для входа"""
    username = db_manager.get_setting('last_login_username')
    return jsonify({'username': username or ''})

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Выход"""
    session.clear()
    return jsonify({'status': 'success', 'message': 'Logged out'})

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    """Проверка аутентификации"""
    return jsonify({'authenticated': session.get('authenticated', False)})

# === ADMIN MANAGEMENT ===
@app.route('/api/auth/admins', methods=['GET'])
def get_admins():
    """Получить список админов"""
    if not session.get('authenticated'):
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    admins = load_admins()
    admin_profiles = db_manager.get_all_admin_profiles()
    profiles_dict = {p.username: p for p in admin_profiles}
    
    result = []
    for username in admins.keys():
        profile = profiles_dict.get(username)
        result.append({
            'username': username,
            'display_name': profile.display_name if profile else username,
            'avatar': profile.avatar if profile else None,
            'custom_id': profile.custom_id if profile else None,
            'theme': profile.theme if profile else 'dark'
        })
    
    return jsonify({'admins': result})


@app.route('/api/auth/admins', methods=['POST'])
def create_admin():
    """Создать админа"""
    if not session.get('authenticated'):
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    username = data.get('username', '')
    password = data.get('password', '')
    display_name = data.get('display_name', username)
    custom_id = data.get('custom_id', '')
    
    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Username and password required'}), 400
    
    admins = load_admins()
    
    if username in admins:
        return jsonify({'status': 'error', 'message': 'User already exists'}), 400
    
    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)
    
    admins[username] = {
        'password_hash': password_hash,
        'salt': salt
    }
    
    save_admins(admins)
    
    # Создаём профиль админа
    db_manager.create_admin_profile(username, display_name, custom_id)
    
    return jsonify({'status': 'success', 'message': f'User {username} created'})


@app.route('/api/auth/admins/<username>', methods=['DELETE'])
def delete_admin(username):
    """Удалить админа"""
    if not session.get('authenticated'):
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    admins = load_admins()
    
    if username not in admins:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    
    if len(admins) <= 1:
        return jsonify({'status': 'error', 'message': 'Cannot delete last admin'}), 400
    
    del admins[username]
    save_admins(admins)
    
    return jsonify({'status': 'success', 'message': f'User {username} deleted'})


@app.route('/api/auth/admins/profile', methods=['POST'])
def update_admin_profile():
    """Обновить профиль админа"""
    if not session.get('authenticated'):
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    username = session.get('username') or data.get('username', '')
    
    display_name = data.get('display_name')
    avatar = data.get('avatar')
    custom_id = data.get('custom_id')
    theme = data.get('theme')
    new_password = data.get('new_password')
    current_password = data.get('current_password')
    
    # Если меняется пароль - проверить текущий и обновить
    if new_password:
        if not current_password:
            return jsonify({'status': 'error', 'message': 'Current password required'}), 400
        
        # Проверяем текущий пароль через admins.json
        admins = load_admins()
        if username not in admins:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404
        
        admin_data = admins[username]
        stored_hash = admin_data.get('password_hash', '')
        stored_salt = admin_data.get('salt', '')
        
        # Проверяем текущий пароль
        if hash_password(current_password, stored_salt) != stored_hash:
            return jsonify({'status': 'error', 'message': 'Current password incorrect'}), 400
        
        # Проверяем, что новый пароль не совпадает с текущим
        if hash_password(new_password, stored_salt) == stored_hash:
            return jsonify({'status': 'error', 'message': 'New password cannot be the same as the current password'}), 400
        
        # Генерируем новый хеш и соль
        new_salt = secrets.token_hex(16)
        new_hash = hash_password(new_password, new_salt)
        
        # Обновляем в admins.json
        admins[username] = {
            'password_hash': new_hash,
            'salt': new_salt
        }
        save_admins(admins)
    
    kwargs = {}
    if display_name is not None:
        kwargs['display_name'] = display_name
    if avatar is not None:
        kwargs['avatar'] = avatar
    if custom_id is not None:
        # Если custom_id пустой - генерируем уникальный
        if not custom_id:
            custom_id = db_manager.generate_unique_admin_id()
        kwargs['custom_id'] = custom_id
    if theme is not None:
        kwargs['theme'] = theme
    
    if kwargs:
        db_manager.update_admin_profile(username, **kwargs)
    
    return jsonify({'status': 'success'})


@app.route('/api/auth/admins/profile', methods=['GET'])
def get_admin_profile():
    """Получить профиль текущего админа"""
    if not session.get('authenticated'):
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    username = session.get('username', '')
    profile = db_manager.get_admin_profile(username)
    
    if profile:
        return jsonify({
            'id': profile.id,
            'username': profile.username,
            'display_name': profile.display_name,
            'avatar': profile.avatar,
            'custom_id': profile.custom_id,
            'theme': profile.theme
        })
    
    return jsonify({
        'username': username,
        'display_name': username,
        'avatar': None,
        'custom_id': None,
        'theme': 'dark'
    })


# === ADMIN CHAT ===
@app.route('/api/admin/chat/messages', methods=['GET'])
def get_admin_chat_messages():
    """Получить сообщения чата админов"""
    if not session.get('authenticated'):
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    limit = int(request.args.get('limit', 50))
    messages = db_manager.get_admin_chat_messages(limit)
    
    return jsonify({
        'messages': [{
            'id': m.id,
            'sender': m.sender_username,
            'message': m.message,
            'created_at': m.created_at.isoformat() if m.created_at else None
        } for m in messages]
    })


@app.route('/api/admin/chat/messages', methods=['POST'])
def send_admin_chat_message():
    """Отправить сообщение в чат админов"""
    if not session.get('authenticated'):
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    message = data.get('message', '')
    sender = session.get('username', 'admin')
    
    if not message:
        return jsonify({'status': 'error', 'message': 'Message required'}), 400
    
    result = db_manager.add_admin_chat_message(sender, message)
    
    if result:
        message_id = result.id  # Get ID before detaching
        return jsonify({'status': 'success', 'id': message_id})
    
    return jsonify({'status': 'error', 'message': 'Failed to send message'}), 500


@app.route('/api/admin/chat/messages/<int:message_id>', methods=['PUT'])
def update_admin_chat_message(message_id):
    """Редактировать сообщение"""
    if not session.get('authenticated'):
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    new_message = data.get('message', '')
    
    if not new_message:
        return jsonify({'status': 'error', 'message': 'Message required'}), 400
    
    success = db_manager.update_admin_chat_message(message_id, new_message)
    
    if success:
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error', 'message': 'Failed to update message'}), 500


@app.route('/api/admin/chat/messages/<int:message_id>', methods=['DELETE'])
def delete_admin_chat_message(message_id):
    """Удалить сообщение"""
    if not session.get('authenticated'):
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    success = db_manager.delete_admin_chat_message(message_id)
    
    if success:
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error', 'message': 'Failed to delete message'}), 500


# === OLLAMA MODELS ===
@app.route('/api/ollama/models', methods=['GET'])
def get_ollama_models():
    """Получить список моделей Ollama"""
    import requests
    
    try:
        ollama_url = Config.OLLAMA_URL
        response = requests.get(f'{ollama_url}/api/tags', timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return jsonify({'models': [m.get('name', '') for m in models]})
        return jsonify({'models': [], 'error': f'Response status: {response.status_code}'})
    except Exception as e:
        logger.error(f"[OLLAMA] Error fetching models: {e}")
        return jsonify({'models': [], 'error': str(e)})


@app.route('/api/ollama/generate', methods=['POST'])
def generate_with_ollama():
    """Сгенерировать текст через Ollama"""
    import requests
    
    data = request.get_json(force=True, silent=True) or {}
    prompt = data.get('prompt', '')
    model = data.get('model', Config.OLLAMA_MODEL)
    
    if not prompt:
        return jsonify({'status': 'error', 'message': 'Prompt required'}), 400
    
    try:
        ollama_url = Config.OLLAMA_URL
        response = requests.post(
            f'{ollama_url}/api/generate',
            json={'model': model, 'prompt': prompt, 'stream': False},
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            return jsonify({'status': 'success', 'text': result.get('response', '')})
        return jsonify({'status': 'error', 'message': f'Response status: {response.status_code}'}), 400
    except Exception as e:
        logger.error(f"[OLLAMA] Error generating: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Получить все аккаунты"""
    try:
        accounts = account_manager.get_all_accounts()
        logger.info(f"[API] Returning {len(accounts)} accounts")
        return jsonify(accounts)
    except Exception as e:
        logger.error(f"[API] Error: {e}")
        return jsonify([])

@app.route('/api/accounts/add', methods=['POST'])
def add_account():
    """Добавить аккаунт"""
    data = request.json or {}
    result = account_manager.add_account(data.get('phone'))
    return jsonify(result)

@app.route('/api/accounts/<phone>/authorize', methods=['POST'])
def authorize_account(phone):
    """Авторизовать аккаунт"""
    data = request.json or {}
    result = account_manager.authorize_account(phone, data.get('code'), data.get('password'))
    return jsonify(result)

@app.route('/api/accounts/<phone>', methods=['DELETE'])
def remove_account(phone):
    """Удалить аккаунт"""
    result = account_manager.remove_account(phone)
    return jsonify(result)

@app.route('/api/accounts/<phone>/stats', methods=['GET'])
def get_account_stats(phone):
    """Статистика аккаунта"""
    result = account_manager.get_account_stats(phone)
    return jsonify(result)

# === LOGIN ROUTES ===

@app.route('/api/login/send-code', methods=['POST'])
def send_code():
    data = request.json or {}
    result = client_manager.send_code(data.get('phone'))
    return jsonify(result)

@app.route('/api/login/verify', methods=['POST'])
def verify_code():
    data = request.json or {}
    result = client_manager.verify_code(
        data.get('phone'), 
        data.get('code'), 
        data.get('password')
    )
    return jsonify(result)

@app.route('/api/accounts/<phone>/refresh', methods=['POST'])
def refresh_account(phone):
    """Обновить данные аккаунта из Telegram"""
    from utils.logger import logger
    
    try:
        logger.info(f"[REFRESH] Updating account: {phone}")
        
        # Получаем клиента - пробуем создать если не найден
        client = client_manager.get_client(phone)
        if not client:
            # Пробуем создать новый клиент
            try:
                client = client_manager.create_client(phone)
            except Exception as e:
                logger.error(f"[REFRESH] Failed to create client: {e}")
                return jsonify({'status': 'error', 'message': f'Client not found: {str(e)}'})
        
        if not client:
            return jsonify({'status': 'error', 'message': 'Client not found'})
        
        # Проверяем авторизацию (async)
        if not run_async(client.is_user_authorized()):
            return jsonify({'status': 'error', 'message': 'Not authorized'})
        
        # Получаем актуальные данные (async)
        me = run_async(client.get_me())
        
        user_data = {
            'user_id': me.id,
            'username': me.username,
            'first_name': me.first_name,
            'last_name': me.last_name,
            'is_premium': getattr(me, 'premium', False),
            'last_active': datetime.now()
        }
        
        logger.info(f"[REFRESH] Got user data: {user_data}")
        
        # Обновляем в БД
        db_manager.update_account(phone=phone, **user_data)
        
        logger.info(f"[REFRESH] Account {phone} updated successfully")
        
        return jsonify({
            'status': 'success',
            'message': 'Account refreshed',
            'data': user_data
        })
        
    except Exception as e:
        logger.error(f"[REFRESH] Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/login/qr', methods=['POST'])
def qr_login():
    data = request.json or {}
    result = client_manager.qr_login(data.get('phone'))
    return jsonify(result)

@app.route('/api/login/qr/check', methods=['POST'])
def check_qr():
    data = request.json or {}
    result = client_manager.check_qr_login(data.get('phone'))
    return jsonify(result)

# === MESSAGE ROUTES ===

@app.route('/api/messages/send', methods=['POST'])
def send_message():
    data = request.json or {}
    result = run_async(message_handler.send_message(
        data.get('phone'), data.get('recipient'), 
        data.get('message'), data.get('media')
    ))
    return jsonify(result)

# === CHANNEL ROUTES ===

@app.route('/api/channels/create', methods=['POST'])
def create_channel():
    data = request.json or {}
    result = run_async(channel_manager.create_channel(
        data.get('phone'), data.get('title'), 
        data.get('description', ''), data.get('is_broadcast', True)
    ))
    return jsonify(result)

@app.route('/api/channels/<channel>/info', methods=['GET'])
def get_channel_info(channel):
    phone = request.args.get('phone')
    result = run_async(channel_manager.get_channel_info(phone, channel))
    return jsonify(result)

@app.route('/api/channels', methods=['GET'])
def get_channels():
    """Получить каналы аккаунта"""
    phone = request.args.get('phone')
    if not phone:
        return jsonify({'status': 'error', 'message': 'Phone required'})
    
    result = run_async(channel_manager.get_channels(phone))
    return jsonify(result)

@app.route('/api/channels/groups', methods=['GET'])
def get_groups():
    """Получить группы аккаунта"""
    phone = request.args.get('phone')
    if not phone:
        return jsonify({'status': 'error', 'message': 'Phone required'})
    
    result = run_async(channel_manager.get_groups(phone))
    return jsonify(result)

# === CHAT/MESSAGE ROUTES ===

@app.route('/api/chats/dialogs', methods=['GET'])
def get_dialogs():
    """Получить диалоги аккаунта"""
    phone = request.args.get('phone')
    if not phone:
        return jsonify({'status': 'error', 'message': 'Phone required'})
    
    logger.info(f"[DIALOGS] Loading dialogs for {phone}")
    # Теперь это синхронный вызов через _safe_call
    result = chat_manager.get_dialogs(phone)
    logger.info(f"[DIALOGS] Result: {result.get('status')}, count: {result.get('total', 0)}")
    return jsonify(result)

@app.route('/api/chats/messages', methods=['GET'])
def get_chat_messages():
    """Получить сообщения из чата с группировкой по датам"""
    phone = request.args.get('phone')
    chat_id = request.args.get('chat_id')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    
    if not phone or not chat_id:
        return jsonify({'status': 'error', 'message': 'Phone and chat_id required'})
    
    # Теперь это синхронный вызов
    messages = chat_manager.get_messages(phone, int(chat_id), limit, offset)
    
    # Группировка по датам (chat_manager уже возвращает сгруппированные сообщения)
    if messages.get('status') == 'success' and 'messages' in messages:
        from datetime import datetime
        grouped = {}
        
        # messages['messages'] - это словарь {date: [messages]}
        messages_data = messages['messages']
        if isinstance(messages_data, dict):
            for date_key, msgs in messages_data.items():
                grouped_list = []
                for msg in msgs:
                    # msg может быть строкой (текст) или словарём
                    if isinstance(msg, dict):
                        grouped_list.append(msg)
                    else:
                        # Если это просто текст сообщения
                        grouped_list.append({'text': str(msg)})
                grouped[date_key] = grouped_list
        else:
            # Если это список - группируем по дате
            for msg in messages_data:
                if isinstance(msg, dict):
                    date_str = msg.get('date', '')
                    if date_str:
                        try:
                            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            date_key = dt.strftime('%d.%m.%Y')
                        except:
                            date_key = date_str[:10] if len(date_str) >= 10 else 'Unknown'
                    else:
                        date_key = 'Unknown'
                    
                    if date_key not in grouped:
                        grouped[date_key] = []
                    grouped[date_key].append(msg)
        
        messages['grouped_by_date'] = grouped
    
    return jsonify(messages)

@app.route('/api/chats/send', methods=['POST'])
def send_chat_message():
    """Отправить сообщение в чат"""
    data = request.json or {}
    phone = data.get('phone')
    chat_id = data.get('chat_id')
    message = data.get('message')
    username = data.get('username')  # Альтернатива: отправить по username
    
    if not phone or not message:
        return jsonify({'status': 'error', 'message': 'Phone and message required'})
    
    if chat_id:
        result = run_async(chat_manager.send_message_to_chat(phone, int(chat_id), message))
    elif username:
        result = run_async(chat_manager.send_message_by_username(phone, username, message))
    else:
        return jsonify({'status': 'error', 'message': 'chat_id or username required'})
    
    return jsonify(result)

@app.route('/api/chats/archive', methods=['POST'])
def archive_chat():
    """Архивировать чат"""
    data = request.json or {}
    phone = data.get('phone')
    chat_id = data.get('chat_id')
    
    if not phone or not chat_id:
        return jsonify({'status': 'error', 'message': 'Phone and chat_id required'})
    
    result = run_async(chat_manager.archive_chat(phone, int(chat_id)))
    return jsonify(result)

@app.route('/api/chats/mute', methods=['POST'])
def toggle_mute():
    """Включить/выключить уведомления"""
    data = request.json or {}
    phone = data.get('phone')
    chat_id = data.get('chat_id')
    mute = data.get('mute', True)
    
    if not phone or not chat_id:
        return jsonify({'status': 'error', 'message': 'Phone and chat_id required'})
    
    result = run_async(chat_manager.toggle_mute(phone, int(chat_id), mute))
    return jsonify(result)

@app.route('/api/chats/block', methods=['POST'])
def block_chat():
    """Заблокировать пользователя"""
    data = request.json or {}
    phone = data.get('phone')
    chat_id = data.get('chat_id')
    
    if not phone or not chat_id:
        return jsonify({'status': 'error', 'message': 'Phone and chat_id required'})
    
    result = run_async(chat_manager.block_user(phone, int(chat_id)))
    return jsonify(result)

@app.route('/api/chats/read', methods=['POST'])
def mark_as_read():
    """Отметить как прочитанное"""
    data = request.json or {}
    phone = data.get('phone')
    chat_id = data.get('chat_id')
    
    if not phone or not chat_id:
        return jsonify({'status': 'error', 'message': 'Phone and chat_id required'})
    
    result = run_async(chat_manager.mark_as_read(phone, int(chat_id)))
    return jsonify(result)

@app.route('/api/chats/delete', methods=['POST'])
def delete_chat():
    """Удалить чат (выйти из чата/канала)"""
    data = request.json or {}
    phone = data.get('phone')
    chat_id = data.get('chat_id')
    
    if not phone or not chat_id:
        return jsonify({'status': 'error', 'message': 'Phone and chat_id required'})
    
    result = run_async(chat_manager.delete_chat(phone, int(chat_id)))
    return jsonify(result)

# === CHANNEL JOIN ROUTES ===

@app.route('/api/channels/join', methods=['POST'])
def join_channel():
    """Подписаться на канал"""
    data = request.json or {}
    phone = data.get('phone')
    channel_link = data.get('channel_link')
    archive = data.get('archive', False)
    mute = data.get('mute', False)
    
    if not phone or not channel_link:
        return jsonify({'status': 'error', 'message': 'Phone and channel_link required'})
    
    result = run_async(chat_manager.join_channel(phone, channel_link, archive, mute))
    
    if result.get('status') == 'success':
        db_manager.update_stats(channels_joined=1)
    
    return jsonify(result)

@app.route('/api/channels/join-all', methods=['POST'])
def join_channel_all():
    """Подписаться на канал со всех аккаунтов"""
    data = request.json or {}
    channel_link = data.get('channel_link')
    archive = data.get('archive', False)
    mute = data.get('mute', False)
    
    if not channel_link:
        return jsonify({'status': 'error', 'message': 'channel_link required'})
    
    accounts = account_manager.get_all_accounts()
    results = []
    successful = 0
    
    for account in accounts:
        phone = account.get('phone')
        if phone:
            result = run_async(chat_manager.join_channel(phone, channel_link, archive, mute))
            results.append({'phone': phone, 'result': result})
            if result.get('status') == 'success':
                successful += 1
                db_manager.update_stats(channels_joined=1)
            asyncio.sleep(1)
    
    return jsonify({
        'status': 'completed',
        'total': len(accounts),
        'successful': successful,
        'results': results
    })

# === REACTION ROUTES ===

@app.route('/api/reactions/add', methods=['POST'])
def add_reaction():
    """Добавить реакцию на сообщение"""
    data = request.json or {}
    phone = data.get('phone')
    channel_link = data.get('channel_link')
    message_id = data.get('message_id')
    emoji = data.get('emoji', '👍')
    
    if not phone or not channel_link or not message_id:
        return jsonify({'status': 'error', 'message': 'Phone, channel_link and message_id required'})
    
    result = run_async(chat_manager.add_reaction(phone, channel_link, int(message_id), emoji))
    return jsonify(result)

@app.route('/api/reactions/add-all', methods=['POST'])
def add_reaction_all():
    """Добавить реакцию на сообщение со всех аккаунтов"""
    data = request.json or {}
    channel_link = data.get('channel_link')
    message_id = data.get('message_id')
    emoji = data.get('emoji', '👍')
    
    if not channel_link or not message_id:
        return jsonify({'status': 'error', 'message': 'channel_link and message_id required'})
    
    accounts = account_manager.get_all_accounts()
    results = []
    successful = 0
    
    for account in accounts:
        phone = account.get('phone')
        if phone:
            result = run_async(chat_manager.add_reaction(phone, channel_link, int(message_id), emoji))
            results.append({'phone': phone, 'result': result})
            if result.get('status') == 'success':
                successful += 1
            asyncio.sleep(1)
    
    return jsonify({
        'status': 'completed',
        'total': len(accounts),
        'successful': successful,
        'results': results
    })

# === REPORT ROUTES ===

@app.route('/api/reports/user', methods=['POST'])
def report_user():
    """Отправить репорт на пользователя"""
    data = request.json or {}
    phone = data.get('phone')
    user_id = data.get('user_id')
    username = data.get('username')
    reason = data.get('reason', 'spam')
    report_text = data.get('report_text', '')
    
    # Если указан промпт и включена Ollama - генерируем текст репорта
    if not report_text and data.get('generate_with_ollama') and Config.OLLAMA_ENABLED:
        try:
            import requests
            model = data.get('ollama_model', Config.OLLAMA_MODEL)
            prompt = data.get('ollama_prompt', f'Напиши краткое описание репорта для пользователя {username} по причине {reason}. Не более 50 слов.')
            response = requests.post(
                f'{Config.OLLAMA_URL}/api/generate',
                json={'model': model, 'prompt': prompt, 'stream': False},
                timeout=30
            )
            if response.status_code == 200:
                report_text = response.json().get('response', '')
        except Exception as e:
            logger.error(f"[REPORT] Ollama generation error: {e}")
    
    result = run_async(report_manager.report_user(phone, int(user_id), username, reason, report_text))
    return jsonify(result)

@app.route('/api/reports/message', methods=['POST'])
def report_message():
    """Отправить репорт на сообщение"""
    data = request.json or {}
    phone = data.get('phone')
    channel_username = data.get('channel_username')
    message_id = data.get('message_id')
    reason = data.get('reason', 'spam')
    report_text = data.get('report_text', '')
    
    # Если указан промпт и включена Ollama - генерируем текст репорта
    if not report_text and data.get('generate_with_ollama') and Config.OLLAMA_ENABLED:
        try:
            import requests
            model = data.get('ollama_model', Config.OLLAMA_MODEL)
            prompt = data.get('ollama_prompt', f'Напиши краткое описание репорта на сообщение по причине {reason}. Не более 50 слов.')
            response = requests.post(
                f'{Config.OLLAMA_URL}/api/generate',
                json={'model': model, 'prompt': prompt, 'stream': False},
                timeout=30
            )
            if response.status_code == 200:
                report_text = response.json().get('response', '')
        except Exception as e:
            logger.error(f"[REPORT] Ollama generation error: {e}")
    
    result = run_async(report_manager.report_message(phone, channel_username, int(message_id), reason, report_text))
    return jsonify(result)

@app.route('/api/reports/all-accounts', methods=['POST'])
def report_from_all():
    """Отправить репорт со всех аккаунтов"""
    data = request.json or {}
    user_id = data.get('user_id')
    username = data.get('username')
    reason = data.get('reason', 'spam')
    report_text = data.get('report_text', '')
    
    # Если указан промпт и включена Ollama - генерируем текст репорта
    if not report_text and data.get('generate_with_ollama') and Config.OLLAMA_ENABLED:
        try:
            import requests
            model = data.get('ollama_model', Config.OLLAMA_MODEL)
            prompt = data.get('ollama_prompt', f'Напиши краткое описание репорта для пользователя {username} по причине {reason}. Не более 50 слов.')
            response = requests.post(
                f'{Config.OLLAMA_URL}/api/generate',
                json={'model': model, 'prompt': prompt, 'stream': False},
                timeout=30
            )
            if response.status_code == 200:
                report_text = response.json().get('response', '')
        except Exception as e:
            logger.error(f"[REPORT] Ollama generation error: {e}")
    
    result = run_async(report_manager.report_from_all_accounts(int(user_id), username, reason, report_text))
    return jsonify(result)

# === SETTINGS ROUTES ===

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Получить настройки"""
    settings = db_manager.get_all_settings()
    # Добавляем дефолтные
    settings.setdefault('theme', Config.DEFAULT_THEME)
    settings.setdefault('auto_archive', str(Config.AUTO_ARCHIVE_ON_JOIN))
    settings.setdefault('mute_on_join', str(Config.MUTE_ON_JOIN))
    settings.setdefault('ollama_enabled', str(Config.OLLAMA_ENABLED))
    settings.setdefault('ollama_url', Config.OLLAMA_URL)
    settings.setdefault('ollama_model', Config.OLLAMA_MODEL)
    return jsonify(settings)

@app.route('/api/settings', methods=['POST'])
def save_settings():
    """Сохранить настройки"""
    data = request.json or {}
    for key, value in data.items():
        db_manager.set_setting(key, str(value))
    return jsonify({'status': 'success'})

@app.route('/api/settings/theme', methods=['POST'])
def set_theme():
    """Установить тему"""
    data = request.json or {}
    theme = data.get('theme', 'dark')
    if theme not in Config.THEMES:
        theme = 'dark'
    db_manager.set_setting('theme', theme)
    return jsonify({'status': 'success', 'theme': theme})

@app.route('/api/settings/telegram-api', methods=['GET'])
def get_telegram_api_settings():
    """Получить настройки Telegram API"""
    return jsonify({
        'api_id': Config.API_ID,
        'api_hash': Config.API_HASH
    })

@app.route('/api/test-post', methods=['POST'])
def test_post():
    """Тестовый эндпоинт"""
    data = request.get_json(force=True, silent=True) or {}
    print(f"[TEST] Received: {data}")
    return jsonify({'status': 'success', 'received': data})

@app.route('/api/settings/telegram-api', methods=['POST'])
def save_telegram_api_settings():
    """Сохранить настройки Telegram API в config.py"""
    from pathlib import Path
    from utils.logger import logger
    
    logger.info(f"[SETTINGS] Raw request.data: {request.data}")
    data = request.get_json(force=True, silent=True) or {}
    logger.info(f"[SETTINGS] Parsed JSON: {data}")
    
    api_id = data.get('api_id', '')
    api_hash = data.get('api_hash', '')
    
    if not api_id or not api_hash:
        return jsonify({'status': 'error', 'message': 'API ID and API Hash required'}), 400
    
    try:
        api_id = int(api_id)
    except ValueError:
        return jsonify({'status': 'error', 'message': 'API ID must be a number'}), 400
    
    # Обновляем Config
    Config.API_ID = api_id
    Config.API_HASH = api_hash
    
    # Сохраняем в .env файл
    env_path = Path(__file__).parent / '.env'
    
    # Читаем текущий .env
    env_lines = []
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            env_lines = f.readlines()
    
    # Обновляем или добавляем значения
    lines_to_keep = []
    api_id_found = False
    api_hash_found = False
    
    for line in env_lines:
        if line.strip().startswith('API_ID='):
            lines_to_keep.append(f'API_ID={api_id}\n')
            api_id_found = True
        elif line.strip().startswith('API_HASH='):
            lines_to_keep.append(f'API_HASH={api_hash}\n')
            api_hash_found = True
        else:
            lines_to_keep.append(line)
    
    if not api_id_found:
        lines_to_keep.append(f'API_ID={api_id}\n')
    if not api_hash_found:
        lines_to_keep.append(f'API_HASH={api_hash}\n')
    
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines_to_keep)
    
    # Также обновляем config.py для вида
    config_path = Path(__file__).parent / 'config.py'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.readlines()
        
        new_config = []
        for line in config_content:
            if "API_ID = int(os.getenv('API_ID'" in line:
                new_config.append(f"    API_ID = int(os.getenv('API_ID', '{api_id}'))\n")
            elif "API_HASH = os.getenv('API_HASH'" in line:
                new_config.append(f"    API_HASH = os.getenv('API_HASH', '{api_hash}')\n")
            else:
                new_config.append(line)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(new_config)
    
    return jsonify({'status': 'success', 'message': 'Settings saved'})

# === STATS ROUTES ===

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Получить статистику"""
    stats = db_manager.get_stats()
    accounts = account_manager.get_all_accounts()
    
    # Дополнительная статистика
    report_stats = db_manager.get_report_stats()
    banned_count = db_manager.get_banned_count()
    
    return jsonify({
        'total_accounts': len(accounts),
        'active_accounts': len([a for a in accounts if a.get('status') == 'active']),
        'banned_accounts': banned_count,
        'reports_sent': stats.get('reports_sent', 0),
        'messages_sent': stats.get('messages_sent', 0),
        'channels_joined': stats.get('channels_joined', 0),
        'report_stats': report_stats
    })

# === AUDIENCE ROUTES ===

@app.route('/api/audience/members', methods=['POST'])
def get_chat_members():
    data = request.json or {}
    result = run_async(audience_collector.get_chat_members(
        data.get('phone'), data.get('chat_id'),
        data.get('limit', 100), data.get('filter_active', True)
    ))
    return jsonify(result)

@app.route('/api/audience/export', methods=['POST'])
def export_audience():
    """Экспорт аудитории в файл"""
    data = request.json or {}
    result = run_async(audience_collector.export_audience(
        data.get('phone'), data.get('chat_id'),
        data.get('output_format', 'csv')
    ))
    return jsonify(result)

# === WARMUP ROUTES ===

@app.route('/api/warmup/start', methods=['POST'])
def start_warmup():
    data = request.json or {}
    result = run_async(warmup_manager.start_warmup(data.get('phone'), data.get('duration', 30)))
    return jsonify(result)

@app.route('/api/warmup/stop', methods=['POST'])
def stop_warmup():
    data = request.json or {}
    result = run_async(warmup_manager.stop_warmup(data.get('phone')))
    return jsonify(result)

@app.route('/api/warmup/status', methods=['GET'])
def warmup_status():
    """Получить статус прогрева"""
    phone = request.args.get('phone')
    if not phone:
        return jsonify({'status': 'error', 'message': 'Phone required'})
    result = run_async(warmup_manager.get_warmup_status(phone))
    return jsonify(result)

# === BLACKLIST ROUTES ===

@app.route('/api/blacklist/add', methods=['POST'])
def add_to_blacklist():
    data = request.json or {}
    result = db_manager.add_to_blacklist(
        data.get('phone'), data.get('username'),
        data.get('user_id'), data.get('reason')
    )
    blacklist_id = result.id if result else None
    return jsonify({'status': 'success', 'id': blacklist_id})

@app.route('/api/blacklist/check', methods=['POST'])
def check_blacklist():
    data = request.json or {}
    is_blacklisted = db_manager.is_blacklisted(
        data.get('phone'), data.get('username'), data.get('user_id')
    )
    return jsonify({'blacklisted': is_blacklisted})

@app.route('/api/blacklist/panel', methods=['GET'])
def get_panel_blacklist():
    """Получить чёрный список созданный из панели"""
    if not session.get('authenticated'):
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    entries = db_manager.get_blacklist_with_source()
    return jsonify({
        'entries': [{
            'id': e.id,
            'phone': e.phone,
            'username': e.username,
            'user_id': e.user_id,
            'reason': e.reason,
            'created_at': e.created_at.isoformat() if e.created_at else None
        } for e in entries]
    })

# === SYSTEM STATS ===

@app.route('/api/system/stats', methods=['GET'])
def get_system_stats():
    accounts = account_manager.get_all_accounts()
    stats = db_manager.get_stats()
    banned_count = db_manager.get_banned_count()
    report_stats = db_manager.get_report_stats()
    
    return jsonify({
        'total_accounts': len(accounts),
        'active_accounts': len([a for a in accounts if a.get('status') == 'active']),
        'banned_accounts': banned_count,
        'reports_sent': stats.get('reports_sent', 0),
        'messages_sent': stats.get('messages_sent', 0),
        'channels_joined': stats.get('channels_joined', 0),
        'report_stats': report_stats
    })

# === SESSION MANAGEMENT ===

@app.route('/api/sessions/delete', methods=['POST'])
def delete_session():
    """Удалить сессию аккаунта"""
    data = request.json or {}
    phone = data.get('phone')
    
    if not phone:
        return jsonify({'status': 'error', 'message': 'Phone required'})
    
    try:
        # Удаляем сессию из client_manager
        client_manager.remove_client(phone)
        
        # Удаляем файл сессии
        session_file = Config.SESSION_DIR / f"{phone}.session"
        if session_file.exists():
            session_file.unlink()
            # Удаляем journal если есть
            journal_file = Config.SESSION_DIR / f"{phone}.session-journal"
            if journal_file.exists():
                journal_file.unlink()
        
        return jsonify({'status': 'success', 'message': f'Session {phone} deleted'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# === INIT MESSAGE ===

@app.route('/api/init/status', methods=['GET'])
def get_init_status():
    """Получить статус инициализации"""
    return jsonify({
        'initialized': True,
        'message': 'Все сессии загружены'
    })

# === OSINT ROUTES ===

@app.route('/api/osint/username', methods=['POST'])
def osint_search_username():
    """Поиск аккаунтов по username"""
    data = request.json or {}
    username = data.get('username', '')
    
    if not username:
        return jsonify({'status': 'error', 'message': 'Username required'}), 400
    
    config_data = {
        'verbose': data.get('verbose', False),
        'timeout': data.get('timeout', 30),
        'proxy': data.get('proxy'),
        'filter': data.get('filter'),
        'no_nsfw': data.get('no_nsfw', False),
        'export_csv': data.get('export_csv', False)
    }
    
    result = osint_manager.search_username(username, config_data)
    return jsonify(result)

@app.route('/api/osint/email', methods=['POST'])
def osint_search_email():
    """Поиск аккаунтов по email"""
    data = request.json or {}
    email = data.get('email', '')
    
    if not email:
        return jsonify({'status': 'error', 'message': 'Email required'}), 400
    
    config_data = {
        'verbose': data.get('verbose', False),
        'timeout': data.get('timeout', 30),
        'proxy': data.get('proxy'),
        'export_csv': data.get('export_csv', False)
    }
    
    result = osint_manager.search_email(email, config_data)
    return jsonify(result)

@app.route('/api/osint/phone', methods=['POST'])
def osint_search_phone():
    """Поиск информации по номеру телефона"""
    data = request.json or {}
    phone = data.get('phone', '')
    
    if not phone:
        return jsonify({'status': 'error', 'message': 'Phone required'}), 400
    
    result = osint_manager.search_phone(phone)
    return jsonify(result)

@app.route('/api/osint/ip', methods=['POST'])
def osint_search_ip():
    """Поиск информации по IP"""
    data = request.json or {}
    ip = data.get('ip', '')
    timeout = data.get('timeout', 30)
    
    if not ip:
        return jsonify({'status': 'error', 'message': 'IP required'}), 400
    
    result = osint_manager.search_ip(ip, timeout)
    return jsonify(result)

@app.route('/api/osint/results', methods=['GET'])
def osint_get_results():
    """Получить список файлов результатов"""
    results_dir = osint_manager.get_results_dir()
    files = []
    
    if os.path.exists(results_dir):
        for f in os.listdir(results_dir):
            if f.endswith('.csv'):
                filepath = os.path.join(results_dir, f)
                files.append({
                    'name': f,
                    'path': filepath,
                    'size': os.path.getsize(filepath),
                    'created': datetime.fromtimestamp(os.path.getctime(filepath)).isoformat()
                })
    
    # Сортируем по дате (новые first)
    files.sort(key=lambda x: x['created'], reverse=True)
    
    return jsonify({
        'status': 'success',
        'results_dir': results_dir,
        'files': files
    })

# === ERROR HANDLERS ===

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    logger.info("[START] TG Manager Pro launching...")
    logger.info(f"[CONFIG] DB: {Config.DATABASE_PATH}")
    logger.info(f"[CONFIG] Sessions: {Config.SESSION_DIR}")
    
    # Получаем порт от хостинга или используем дефолтный
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)