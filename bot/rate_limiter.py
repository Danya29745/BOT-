"""
Модуль для ограничения частоты запросов (rate limiting)
"""
import time
import logging
from typing import Dict, Optional
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class RateLimiter:
    """Класс для ограничения частоты запросов пользователей"""
    
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        """
        Args:
            max_requests: Максимальное количество запросов
            time_window: Временное окно в секундах
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.user_requests: Dict[str, deque] = defaultdict(deque)
    
    def is_allowed(self, user_id: str) -> bool:
        """Проверяет, разрешен ли запрос для пользователя"""
        current_time = time.time()
        user_queue = self.user_requests[user_id]
        
        # Удаляем старые запросы
        while user_queue and current_time - user_queue[0] > self.time_window:
            user_queue.popleft()
        
        # Проверяем лимит
        if len(user_queue) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return False
        
        # Добавляем текущий запрос
        user_queue.append(current_time)
        return True
    
    def get_remaining_requests(self, user_id: str) -> int:
        """Возвращает количество оставшихся запросов"""
        current_time = time.time()
        user_queue = self.user_requests[user_id]
        
        # Удаляем старые запросы
        while user_queue and current_time - user_queue[0] > self.time_window:
            user_queue.popleft()
        
        return max(0, self.max_requests - len(user_queue))
    
    def get_reset_time(self, user_id: str) -> Optional[float]:
        """Возвращает время до сброса лимита"""
        user_queue = self.user_requests[user_id]
        if not user_queue:
            return None
        
        return user_queue[0] + self.time_window - time.time()

# Глобальный экземпляр rate limiter
rate_limiter = RateLimiter(max_requests=15, time_window=60)  # 15 запросов в минуту