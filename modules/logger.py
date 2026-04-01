"""Логирование с colorama"""
import logging
import sys
from datetime import datetime
from colorama import init, Fore, Style

# Инициализация colorama
init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """Форматтер с цветами для разных типов логов"""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
        'SUCCESS': Fore.LIGHTGREEN_EX,
    }
    
    def format(self, record):
        # Добавляем цвет к уровню
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"
        
        # Форматируем время
        record.time = datetime.now().strftime("%H:%M:%S")
        
        return super().format(record)


class Logger:
    """Кастомный логгер для бота"""
    
    def __init__(self, name: str = "7mGacha"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Убираем дублирование обработчиков
        if not self.logger.handlers:
            # Консольный обработчик
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)
            
            # Формат: [ТИП] [ВРЕМЯ] СООБЩЕНИЕ
            formatter = ColoredFormatter(
                fmt='[%(levelname)s] [%(time)s] %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def _log(self, level: int, user_id: int | None, action: str, details: str = ""):
        """Внутренний метод для логирования"""
        user_str = f"User:{user_id}" if user_id else "System"
        message = f"{user_str} | {action}"
        if details:
            message += f" | {details}"
        
        self.logger.log(level, message)
    
    def debug(self, action: str, user_id: int = None, details: str = ""):
        self._log(logging.DEBUG, user_id, action, details)
    
    def info(self, action: str, user_id: int = None, details: str = ""):
        self._log(logging.INFO, user_id, action, details)
    
    def success(self, action: str, user_id: int = None, details: str = ""):
        """Success - использует зеленый цвет"""
        self._log(logging.INFO, user_id, f"✓ {action}", details)
    
    def warning(self, action: str, user_id: int = None, details: str = ""):
        self._log(logging.WARNING, user_id, action, details)
    
    def error(self, action: str, user_id: int = None, details: str = ""):
        self._log(logging.ERROR, user_id, action, details)
    
    def critical(self, action: str, user_id: int = None, details: str = ""):
        self._log(logging.CRITICAL, user_id, action, details)
    
    # Удобные методы для конкретных событий
    def user_joined(self, user_id: int, name: str):
        self.success("User joined", user_id, f"name={name}")
    
    def user_command(self, user_id: int, command: str):
        self.info("Command executed", user_id, f"cmd={command}")
    
    def user_action(self, user_id: int, action: str):
        self.info("User action", user_id, f"action={action}")
    
    def gacha_spin(self, user_id: int, rarity: str):
        self.info("Gacha spin", user_id, f"rarity={rarity}")
    
    def craft_card(self, user_id: int, card_name: str, is_duplicate: bool):
        if is_duplicate:
            self.success("Card crafted (duplicate)", user_id, f"card={card_name}")
        else:
            self.success("Card crafted (new)", user_id, f"card={card_name}")
    
    def admin_action(self, admin_id: int, action: str, target: str = ""):
        self.warning("Admin action", admin_id, f"action={action} target={target}")
    
    def system(self, message: str, details: str = ""):
        self.info("System", details=message if not details else f"{message} | {details}")
    
    def error_exception(self, user_id: int, error: Exception, context: str = ""):
        self.error("Exception", user_id, f"error={type(error).__name__}: {error} | context={context}")


# Глобальный экземпляр логгера
logger = Logger()
