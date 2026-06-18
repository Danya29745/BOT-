"""
Централизованный менеджер Redis подключений
"""
import redis
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RedisManager:
    """Синглтон для управления Redis подключениями"""
    
    _instance = None
    _redis_client = None
    
    def __new__(cls, redis_url: str = None):
        if cls._instance is None:
            cls._instance = super(RedisManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, redis_url: str = None):
        if self._redis_client is None and redis_url:
            try:
                self._redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
                # Проверяем подключение
                self._redis_client.ping()
                logger.info(f"Redis подключен успешно: {redis_url}")
            except Exception as e:
                logger.warning(f"Redis недоступен: {e}")
                self._redis_client = None
    
    @property
    def client(self) -> Optional[redis.Redis]:
        """Возвращает Redis клиент или None если недоступен"""
        return self._redis_client
    
    def is_available(self) -> bool:
        """Проверяет доступность Redis"""
        return self._redis_client is not None
    
    def ping(self) -> bool:
        """Проверяет соединение с Redis"""
        if not self._redis_client:
            return False
        try:
            self._redis_client.ping()
            return True
        except Exception:
            return False