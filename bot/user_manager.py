"""
Модуль для управления пользователями и их настройками
"""
import json
import logging
from datetime import datetime
from typing import Dict, Optional
import redis

logger = logging.getLogger(__name__)

class UserManager:
    """Класс для управления пользователями и их настройками"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        
    def get_user_settings(self, user_id: str) -> Dict:
        """Получает настройки пользователя"""
        if not self.redis_client:
            return self._default_settings()
            
        try:
            settings_json = self.redis_client.get(f"user_settings:{user_id}")
            if settings_json:
                return json.loads(settings_json)
            else:
                # Создаем настройки по умолчанию
                default_settings = self._default_settings()
                self.save_user_settings(user_id, default_settings)
                return default_settings
        except Exception as e:
            logger.error(f"Ошибка при получении настроек пользователя {user_id}: {e}")
            return self._default_settings()
    
    def save_user_settings(self, user_id: str, settings: Dict):
        """Сохраняет настройки пользователя"""
        if not self.redis_client:
            return
            
        try:
            self.redis_client.set(f"user_settings:{user_id}", json.dumps(settings))
            logger.info(f"Настройки пользователя {user_id} сохранены")
        except Exception as e:
            logger.error(f"Ошибка при сохранении настроек пользователя {user_id}: {e}")
    
    def _default_settings(self) -> Dict:
        """Возвращает настройки по умолчанию"""
        return {
            'notifications': True,
            'language': 'ru',
            'created_at': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat()
        }
    
    def update_last_activity(self, user_id: str):
        """Обновляет время последней активности пользователя"""
        if not self.redis_client:
            return
            
        try:
            settings = self.get_user_settings(user_id)
            settings['last_active'] = datetime.now().isoformat()
            self.save_user_settings(user_id, settings)
        except Exception as e:
            logger.error(f"Ошибка при обновлении активности пользователя {user_id}: {e}")
    
    def get_user_profile(self, user_id: str, user_data: Dict = None) -> Dict:
        """Получает профиль пользователя"""
        settings = self.get_user_settings(user_id)
        
        profile = {
            'user_id': user_id,
            'settings': settings,
            'registration_date': settings.get('created_at'),
            'last_active': settings.get('last_active')
        }
        
        if user_data:
            profile.update({
                'first_name': user_data.get('first_name'),
                'username': user_data.get('username'),
                'language_code': user_data.get('language_code')
            })
        
        return profile
    
    def export_user_history(self, user_id: str) -> Optional[str]:
        """Экспортирует историю пользователя в JSON"""
        if not self.redis_client:
            return None
            
        try:
            # Получаем историю чата
            history_key = f"message_history:{user_id}"
            history_data = self.redis_client.lrange(history_key, 0, -1)
            
            # Получаем настройки
            settings = self.get_user_settings(user_id)
            
            export_data = {
                'user_id': user_id,
                'export_date': datetime.now().isoformat(),
                'settings': settings,
                'chat_history': [json.loads(msg) for msg in history_data if msg]
            }
            
            return json.dumps(export_data, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Ошибка при экспорте истории пользователя {user_id}: {e}")
            return None