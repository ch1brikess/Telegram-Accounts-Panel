# TG Manager Pro
![Telegram Manager](https://img.shields.io/badge/Telegram-Manager-Blue?style=for-the-badge&logo=telegram)

# Languages
1. [EN](#EN)
2. [RU](#RU)

# EN

## Overview

TG Manager Pro is a comprehensive web-based Telegram account management system. It provides a modern web interface for managing multiple Telegram accounts, sending messages, joining channels, collecting audience data, reporting users, and performing OSINT investigations. The application uses Flask for the backend and Telethon library for Telegram API interactions.

## Features

- **Multi-Account Management**: Add, authorize, and manage multiple Telegram accounts with session persistence
- **Authentication System**: Secure admin login with password hashing (SHA256) and session management
- **Message Sending**: Send messages to individual users or chat groups
- **Channel Management**: Create channels, join channels/groups, manage subscriptions
- **Audience Collection**: Extract member data from groups and channels with filtering options
- **Reporting System**: Report users or messages with customizable reasons and AI-generated report text (via Ollama)
- **OSINT Tools**: Search for accounts by username, email, phone number, or IP address
- **Account Warmup**: Automatic activity simulation to maintain account health
- **Admin Chat**: Built-in messaging system for administrators
- **Blacklist Management**: Track and manage blocked users across accounts
- **Statistics Dashboard**: View reports sent, messages sent, channels joined, and account status
- **Theme Support**: Dark and light themes with customizable admin profiles

## Installation

1. Clone or download the repository:
```bash
git clone https://github.com/your-repo/tg-manager.git
cd tg-manager
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables in `.env` file:
```bash
API_ID=your_api_id
API_HASH=your_api_hash
SECRET_KEY=your_secret_key
OLLAMA_ENABLED=false
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

4. Get your Telegram API credentials:
   - Visit https://my.telegram.org/apps
   - Create a new application
   - Copy API ID and API Hash

5. Run the application:
```bash
python app.py
```

6. Open browser and navigate to:
```bash
http://localhost:5000
```

## First Setup

### Creating Admin Account

After first run, create an admin account using the web interface or the `create_user.py` script:
```bash
python create_user.py
```

### Getting Telegram API Credentials

1. Go to https://my.telegram.org/apps
2. Login with your Telegram account
3. Click "Create new application"
4. Select appropriate platform (Telegram App)
5. Copy API ID and API Hash
6. Enter them in the web interface settings or `.env` file

## Usage

### Adding Telegram Account

1. Login to the admin panel
2. Go to Accounts section
3. Enter phone number in format: +1234567890
4. Click "Add Account"
5. Enter the verification code sent to your Telegram app
6. If 2FA is enabled, enter your password

### Sending Messages

1. Select account from dropdown
2. Enter recipient (username or phone)
3. Type message content
4. Optionally attach media
5. Click Send

### Joining Channels

1. Select account or use "Join from all accounts"
2. Enter channel/group link
3. Choose archive and mute options
4. Confirm action

### Reporting Users

1. Select account(s) for reporting
2. Enter target user ID or username
3. Select reason (spam, abuse, violence, etc.)
4. Optionally enable AI-generated report text
5. Submit report

### OSINT Search

**By Username:**
```json
POST /api/osint/username
{
  "username": "target_username",
  "verbose": true,
  "export_csv": true
}
```

**By Email:**
```json
POST /api/osint/email
{
  "email": "target@example.com",
  "timeout": 30
}
```

**By Phone:**
```json
POST /api/osint/phone
{
  "phone": "+1234567890"
}
```

### Using Ollama for Report Generation

To enable AI-generated report text:

1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull llama3.2`
3. Enable in settings: `OLLAMA_ENABLED=true`
4. Configure URL and model in settings

## Configuration

### Environment Variables (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| API_ID | Telegram API ID | - |
| API_HASH | Telegram API Hash | - |
| SECRET_KEY | Flask secret key | dev-key-change-in-prod |
| OLLAMA_ENABLED | Enable Ollama integration | false |
| OLLAMA_URL | Ollama server URL | http://localhost:11434 |
| OLLAMA_MODEL | Ollama model name | llama3.2 |
| DEFAULT_THEME | Default UI theme | dark |
| AUTO_ARCHIVE_ON_JOIN | Auto-archive joined chats | false |
| MUTE_ON_JOIN | Mute chats on join | false |

### Web Interface Settings

Access settings via web interface at `/api/settings` or through the UI:
- Telegram API credentials
- Ollama configuration
- Theme selection
- Auto-archive/mute options

## API Endpoints

### Authentication
- `POST /api/auth/login` - Admin login
- `POST /api/auth/logout` - Admin logout
- `GET /api/auth/check` - Check authentication status
- `GET /api/auth/admins` - List administrators
- `POST /api/auth/admins` - Create administrator
- `DELETE /api/auth/admins/<username>` - Delete administrator

### Accounts
- `GET /api/accounts` - List all accounts
- `POST /api/accounts/add` - Add new account
- `POST /api/accounts/<phone>/authorize` - Authorize account
- `DELETE /api/accounts/<phone>` - Remove account
- `POST /api/accounts/<phone>/refresh` - Refresh account data

### Messages
- `POST /api/messages/send` - Send message

### Channels & Groups
- `POST /api/channels/create` - Create channel
- `GET /api/channels` - Get account channels
- `GET /api/channels/groups` - Get account groups
- `POST /api/channels/join` - Join channel
- `POST /api/channels/join-all` - Join with all accounts

### Chats
- `GET /api/chats/dialogs` - Get dialogs
- `GET /api/chats/messages` - Get chat messages
- `POST /api/chats/send` - Send message to chat
- `POST /api/chats/archive` - Archive chat
- `POST /api/chats/mute` - Toggle mute
- `POST /api/chats/block` - Block user
- `POST /api/chats/delete` - Delete chat

### Reports
- `POST /api/reports/user` - Report user
- `POST /api/reports/message` - Report message
- `POST /api/reports/all-accounts` - Report from all accounts

### OSINT
- `POST /api/osint/username` - Search by username
- `POST /api/osint/email` - Search by email
- `POST /api/osint/phone` - Search by phone
- `POST /api/osint/ip` - Search by IP

### Statistics
- `GET /api/stats` - Get system statistics
- `GET /api/system/stats` - Get detailed stats

## Security Notes

- Change default `SECRET_KEY` in production
- Use strong admin passwords
- Keep API credentials secure
- Regularly backup the database
- Monitor account activity to prevent bans

## Troubleshooting

### "Session invalid" error
- Delete the session file in `sessions/` directory
- Re-authorize the account

### Rate limiting (FloodWait)
- Wait for the specified time
- Reduce request frequency
- Use account warmup to maintain activity

### Connection errors
- Check internet connection
- Verify API credentials
- Ensure Telegram is accessible

## Project Structure

```
tg_manager/
├── app.py              # Main Flask application
├── config.py           # Configuration
├── create_user.py      # Admin creation script
├── requirements.txt    # Python dependencies
├── .env               # Environment variables
├── admins.json        # Admin credentials
├── core/              # Core functionality
│   ├── telegram_client.py
│   ├── account_manager.py
│   ├── message_handler.py
│   ├── channel_manager.py
│   ├── chat_manager.py
│   ├── audience_collector.py
│   ├── report_manager.py
│   ├── osint_manager.py
│   └── warmup.py
├── database/          # Database layer
│   ├── db_manager.py
│   └── models.py
├── utils/             # Utilities
│   ├── logger.py
│   ├── validators.py
│   └── spintax.py
├── templates/         # HTML templates
├── static/           # CSS and static files
├── sessions/         # Telegram session files
└── logs/            # Application logs
```

## License

MIT License

---

# RU

## Обзор

TG Manager Pro — это комплексная веб-система управления Telegram-аккаунтами. Она предоставляет современный веб-интерфейс для управления несколькими аккаунтами Telegram, отправки сообщений, присоединения к каналам, сбора данных аудитории, создания репортов пользователей и проведения OSINT-расследований. Приложение использует Flask для бэкенда и библиотеку Telethon для взаимодействия с API Telegram.

## Возможности

- **Управление несколькими аккаунтами**: Добавление, авторизация и управление несколькими аккаунтами Telegram с сохранением сессий
- **Система аутентификации**: Безопасный вход администратора с хэшированием паролей (SHA256) и управлением сессиями
- **Отправка сообщений**: Отправка сообщений отдельным пользователям или в групповые чаты
- **Управление каналами**: Создание каналов, присоединение к каналам/группам, управление подписками
- **Сбор аудитории**: Извлечение данных участников из групп и каналов с возможностью фильтрации
- **Система репортинга**: Репорт пользователей или сообщений с настраиваемыми причинами и AI-генерируемым текстом репорта (через Ollama)
- **OSINT-инструменты**: Поиск аккаунтов по имени пользователя, email, номеру телефона или IP-адресу
- **Прогрев аккаунтов**: Автоматическая имитация активности для поддержания здоровья аккаунта
- **Чат админов**: Встроенная система обмена сообщениями между администраторами
- **Управление чёрным списком**: Отслеживание и управление заблокированными пользователями
- **Панель статистики**: Просмотр отправленных репортов, сообщений, присоединённых каналов и статуса аккаунтов
- **Поддержка тем**: Тёмная и светлая темы с настраиваемыми профилями администраторов

## Установка

1. Клонируйте или скачайте репозиторий:
```bash
git clone https://github.com/your-repo/tg-manager.git
cd tg-manager
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Настройте переменные окружения в файле `.env`:
```bash
API_ID=your_api_id
API_HASH=your_api_hash
SECRET_KEY=your_secret_key
OLLAMA_ENABLED=false
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

4. Получите учётные данные Telegram API:
   - Перейдите на https://my.telegram.org/apps
   - Создайте новое приложение
   - Скопируйте API ID и API Hash

5. Запустите приложение:
```bash
python app.py
```

6. Откройте браузер и перейдите по адресу:
```bash
http://localhost:5000
```

## Первоначальная настройка

### Создание учётной записи администратора

После первого запуска создайте учётную запись администратора через веб-интерфейс или скрипт `create_user.py`:
```bash
python create_user.py
```

### Получение учётных данных Telegram API

1. Перейдите на https://my.telegram.org/apps
2. Войдите в свой аккаунт Telegram
3. Нажмите "Create new application"
4. Выберите подходящую платформу (Telegram App)
5. Скопируйте API ID и API Hash
6. Введите их в настройках веб-интерфейса или в файле `.env`

## Использование

### Добавление аккаунта Telegram

1. Войдите в панель администратора
2. Перейдите в раздел "Accounts"
3. Введите номер телефона в формате: +1234567890
4. Нажмите "Add Account"
5. Введите код подтверждения, отправленный в ваше приложение Telegram
6. если включена 2FA, введите пароль

### Отправка сообщений

1. Выберите аккаунт из выпадающего списка
2. Введите получателя (имя пользователя или телефон)
3. Введите текст сообщения
4. При желании прикрепите медиафайл
5. Нажмите "Send"

### Присоединение к каналам

1. Выберите аккаунт или используйте "Join from all accounts"
2. Введите ссылку на канал/группу
3. Выберите параметры архивации и отключения звука
4. Подтвердите действие

### Репорт пользователей

1. Выберите аккаунт(ы) для репортинга
2. Введите ID целевого пользователя или имя пользователя
3. Выберите причину (спам, злоупотребление, насилие и т.д.)
4. При желании включите AI-генерируемый текст репорта
5. Отправьте репорт

### OSINT-поиск

**По имени пользователя:**
```json
POST /api/osint/username
{
  "username": "target_username",
  "verbose": true,
  "export_csv": true
}
```

**По email:**
```json
POST /api/osint/email
{
  "email": "target@example.com",
  "timeout": 30
}
```

**По телефону:**
```json
POST /api/osint/phone
{
  "phone": "+1234567890"
}
```

### Использование Ollama для генерации репортов

Для включения AI-генерируемого текста репорта:

1. Установите Ollama: https://ollama.ai
2. Загрузите модель: `ollama pull llama3.2`
3. Включите в настройках: `OLLAMA_ENABLED=true`
4. Настройте URL и модель в настройках

## Конфигурация

### Переменные окружения (.env)

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| API_ID | Telegram API ID | - |
| API_HASH | Telegram API Hash | - |
| SECRET_KEY | Секретный ключ Flask | dev-key-change-in-prod |
| OLLAMA_ENABLED | Включить интеграцию с Ollama | false |
| OLLAMA_URL | URL сервера Ollama | http://localhost:11434 |
| OLLAMA_MODEL | Имя модели Ollama | llama3.2 |
| DEFAULT_THEME | Тема интерфейса по умолчанию | dark |
| AUTO_ARCHIVE_ON_JOIN | Автоархивирование присоединённых чатов | false |
| MUTE_ON_JOIN | Отключение звука при присоединении | false |

### Настройки веб-интерфейса

Доступ к настройкам через веб-интерфейс по адресу `/api/settings` или через UI:
- Учётные данные Telegram API
- Конфигурация Ollama
- Выбор темы
- Параметры автоархивации/отключения звука

## API-эндпоинты

### Аутентификация
- `POST /api/auth/login` - Вход администратора
- `POST /api/auth/logout` - Выход администратора
- `GET /api/auth/check` - Проверка статуса аутентификации
- `GET /api/auth/admins` - Список администраторов
- `POST /api/auth/admins` - Создание администратора
- `DELETE /api/auth/admins/<username>` - Удаление администратора

### Аккаунты
- `GET /api/accounts` - Список всех аккаунтов
- `POST /api/accounts/add` - Добавление нового аккаунта
- `POST /api/accounts/<phone>/authorize` - Авторизация аккаунта
- `DELETE /api/accounts/<phone>` - Удаление аккаунта
- `POST /api/accounts/<phone>/refresh` - Обновление данных аккаунта

### Сообщения
- `POST /api/messages/send` - Отправка сообщения

### Каналы и группы
- `POST /api/channels/create` - Создание канала
- `GET /api/channels` - Получение каналов аккаунта
- `GET /api/channels/groups` - Получение групп аккаунта
- `POST /api/channels/join` - Присоединение к каналу
- `POST /api/channels/join-all` - Присоединение со всех аккаунтов

### Чаты
- `GET /api/chats/dialogs` - Получение диалогов
- `GET /api/chats/messages` - Получение сообщений чата
- `POST /api/chats/send` - Отправка сообщения в чат
- `POST /api/chats/archive` - Архивация чата
- `POST /api/chats/mute` - Переключение звука
- `POST /api/chats/block` - Блокировка пользователя
- `POST /api/chats/delete` - Удаление чата

### Репорты
- `POST /api/reports/user` - Репорт пользователя
- `POST /api/reports/message` - Репорт сообщения
- `POST /api/reports/all-accounts` - Репорт со всех аккаунтов

### OSINT
- `POST /api/osint/username` - Поиск по имени пользователя
- `POST /api/osint/email` - Поиск по email
- `POST /api/osint/phone` - Поиск по телефону
- `POST /api/osint/ip` - Поиск по IP

### Статистика
- `GET /api/stats` - Получение системной статистики
- `GET /api/system/stats` - Получение подробной статистики

## Заметки по безопасности

- Измените стандартный `SECRET_KEY` в production
- Используйте надёжные пароли администраторов
- Храните учётные данные API в безопасности
- Регулярно создавайте резервные копии базы данных
- Следите за активностью аккаунтов для предотвращения блокировок

## Устранение неполадок

### Ошибка "Session invalid"
- Удалите файл сессии в директории `sessions/`
- Повторно авторизуйте аккаунт

### Ограничение скорости (FloodWait)
- Подождите указанное время
- Уменьшите частоту запросов
- Используйте прогрев аккаунта для поддержания активности

### Ошибки подключения
- Проверьте подключение к интернету
- Проверьте учётные данные API
- Убедитесь, что Telegram доступен

## Структура проекта

```
tg_manager/
├── app.py              # Основное приложение Flask
├── config.py           # Конфигурация
├── create_user.py      # Скрипт создания администратора
├── requirements.txt    # Зависимости Python
├── .env               # Переменные окружения
├── admins.json        # Учётные данные администраторов
├── core/              # Основной функционал
│   ├── telegram_client.py
│   ├── account_manager.py
│   ├── message_handler.py
│   ├── channel_manager.py
│   ├── chat_manager.py
│   ├── audience_collector.py
│   ├── report_manager.py
│   ├── osint_manager.py
│   └── warmup.py
├── database/          # Уровень базы данных
│   ├── db_manager.py
│   └── models.py
├── utils/             # Утилиты
│   ├── logger.py
│   ├── validators.py
│   └── spintax.py
├── templates/         # HTML-шаблоны
├── static/           # CSS и статические файлы
├── sessions/         # Файлы сессий Telegram
└── logs/            # Логи приложения
```

## Лицензия

MIT License
