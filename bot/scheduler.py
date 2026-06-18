"""
Модуль для планировщика задач
"""
import schedule
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Optional
import redis

logger = logging.getLogger(__name__)

# Импортируем admin_notifier для отправки статистики
admin_notifier = None

class BotScheduler:
    """Планировщик для выполнения периодических задач"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.running = False
        self.thread = None
        
    def start(self):
        """Запускает планировщик"""
        if self.running:
            return
            
        self.running = True
        
        # Настраиваем задачи
        schedule.every().day.at("00:00").do(self._cleanup_old_data)
        schedule.every().hour.do(self._update_statistics)
        schedule.every(30).minutes.do(self._health_check)
        
        # Запускаем в отдельном потоке
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        
        logger.info("Планировщик задач запущен")
    
    def stop(self):
        """Останавливает планировщик"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Планировщик задач остановлен")
    
    def _run_scheduler(self):
        """Основной цикл планировщика"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Проверяем каждую минуту
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
                time.sleep(60)
    
    def _cleanup_old_data(self):
        """Очищает старые данные"""
        if not self.redis_client:
            return
            
        try:
            # Удаляем аналитику старше 30 дней
            cutoff_date = datetime.now() - timedelta(days=30)
            
            # Получаем все ключи аналитики
            keys = self.redis_client.keys("analytics:*")
            deleted_count = 0
            
            for key in keys:
                try:
                    # Извлекаем дату из ключа
                    if isinstance(key, bytes):
                        key = key.decode()
                    
                    # Проверяем TTL, если он не установлен - устанавливаем
                    ttl = self.redis_client.ttl(key)
                    if ttl == -1:  # Ключ без TTL
                        self.redis_client.expire(key, 30 * 24 * 3600)  # 30 дней
                        
                except Exception as e:
                    logger.error(f"Ошибка при обработке ключа {key}: {e}")
            
            logger.info(f"Очистка данных завершена. Обработано ключей: {len(keys)}")
            
        except Exception as e:
            logger.error(f"Ошибка при очистке старых данных: {e}")
    
    def _update_statistics(self):
        """Обновляет статистику"""
        global admin_notifier
        
        if not self.redis_client:
            return
            
        try:
            # Подсчитываем активных пользователей за последний час
            current_hour = datetime.now().strftime("%Y-%m-%d-%H")
            active_users_key = f"active_users:{current_hour}"
            
            # Отправляем ежедневную статистику в полночь
            if datetime.now().hour == 0 and admin_notifier:
                from .analytics import BotAnalytics
                analytics = BotAnalytics(self.redis_client)
                today = datetime.now().strftime("%Y-%m-%d")
                daily_stats = analytics.get_daily_stats(today)
                daily_stats['avg_rating'] = analytics.get_average_rating()
                
                # Отправляем статистику администратору
                import asyncio
                asyncio.create_task(admin_notifier.send_daily_stats(daily_stats))
            
            logger.info("Статистика обновлена")
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении статистики: {e}")
    
    def _health_check(self):
        """Проверка здоровья системы"""
        try:
            if self.redis_client:
                # Проверяем подключение к Redis
                self.redis_client.ping()
            
            logger.info("Проверка здоровья системы пройдена")
            
        except Exception as e:
            logger.error(f"Проблемы со здоровьем системы: {e}")

# Глобальный экземпляр планировщика
scheduler = BotScheduler()