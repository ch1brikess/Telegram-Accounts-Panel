"""Защита от спама и злоупотреблений"""
import time
from typing import Dict
from dataclasses import dataclass, field
from modules.logger import logger


@dataclass
class UserAction:
    """Действие пользователя"""
    action_type: str
    timestamp: float
    count: int = 1


class SpamProtection:
    """Защита от спама"""
    
    def __init__(self, window: int = 10, max_actions: int = 5):
        self.window = window  # окно в секундах
        self.max_actions = max_actions  # максимум действий
        self._actions: Dict[int, Dict[str, UserAction]] = {}  # user_id -> {action_type -> UserAction}
    
    def check(self, user_id: int, action_type: str = "general") -> bool:
        """Проверяет, не спамит ли пользователь"""
        current_time = time.time()
        
        if user_id not in self._actions:
            self._actions[user_id] = {}
        
        user_actions = self._actions[user_id]
        
        # Если действие уже было - обновляем
        if action_type in user_actions:
            action = user_actions[action_type]
            
            # Если прошло достаточно времени - сбрасываем
            if current_time - action.timestamp > self.window:
                user_actions[action_type] = UserAction(action_type, current_time, 1)
                return True
            
            # Увеличиваем счетчик
            action.count += 1
            
            # Проверяем лимит
            if action.count > self.max_actions:
                logger.warning("Spam detected", user_id, f"action={action_type} count={action.count}")
                return False
        else:
            # Первое действие
            user_actions[action_type] = UserAction(action_type, current_time, 1)
        
        return True
    
    def reset(self, user_id: int, action_type: str = None):
        """Сбрасывает счетчик для пользователя"""
        if user_id not in self._actions:
            return
        
        if action_type:
            self._actions[user_id].pop(action_type, None)
        else:
            self._actions[user_id].clear()
    
    def cleanup_old(self, max_age: int = 300):
        """Очищает старые записи (старше max_age секунд)"""
        current_time = time.time()
        to_remove = []
        
        for user_id, actions in self._actions.items():
            for action_type, action in list(actions.items()):
                if current_time - action.timestamp > max_age:
                    actions.pop(action_type, None)
            
            if not actions:
                to_remove.append(user_id)
        
        for user_id in to_remove:
            self._actions.pop(user_id, None)


class RateLimiter:
    """Ограничение частоты действий для конкретных операций"""
    
    def __init__(self):
        self._cooldowns: Dict[str, Dict[int, float]] = {}  # action -> {user_id -> last_time}
    
    def set_cooldown(self, user_id: int, action: str, seconds: float):
        """Устанавливает кулдаун для пользователя"""
        if action not in self._cooldowns:
            self._cooldowns[action] = {}
        self._cooldowns[action][user_id] = time.time() + seconds
    
    def check_cooldown(self, user_id: int, action: str) -> tuple[bool, float]:
        """Проверяет кулдаун. Возвращает (можно_действовать, оставшееся_время)"""
        if action not in self._cooldowns:
            return True, 0
        
        last_time = self._cooldowns[action].get(user_id, 0)
        remaining = last_time - time.time()
        
        if remaining <= 0:
            return True, 0
        
        return False, remaining
    
    def clear_cooldown(self, user_id: int, action: str = None):
        """Очищает кулдаун"""
        if action:
            if action in self._cooldowns:
                self._cooldowns[action].pop(user_id, None)
        else:
            for action in self._cooldowns:
                self._cooldowns[action].pop(user_id, None)


# Глобальные экземпляры
spam_protection = SpamProtection(window=10, max_actions=5)
rate_limiter = RateLimiter()
