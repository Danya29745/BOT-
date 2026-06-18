"""
Модуль для аналитики и статистики использования бота
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import redis
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)

class BotAnalytics:
    """Класс для сбора и анализа статистики использования бота"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        
    def log_user_action(self, user_id: str, action: str, metadata: Dict = None):
        """Логирует действие пользователя"""
        if not self.redis_client:
            return
            
        try:
            timestamp = datetime.now().isoformat()
            event = {
                'user_id': user_id,
                'action': action,
                'timestamp': timestamp,
                'metadata': metadata or {}
            }
            
            # Сохраняем в Redis с TTL 30 дней
            key = f"analytics:user:{user_id}:{timestamp}"
            self.redis_client.setex(key, 30 * 24 * 3600, json.dumps(event))
            
            # Обновляем счетчики
            self._update_counters(user_id, action)
            
        except Exception as e:
            logger.error(f"Ошибка при логировании действия: {e}")
    
    def log_token_usage(self, user_id: str, prompt_tokens: int, completion_tokens: int, total_tokens: int, model: str = "gpt-4o-mini"):
        """Логирует использование токенов OpenAI"""
        if not self.redis_client:
            return
            
        try:
            timestamp = datetime.now().isoformat()
            today = datetime.now().strftime("%Y-%m-%d")
            
            token_data = {
                'user_id': user_id,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total_tokens,
                'model': model,
                'timestamp': timestamp
            }
            
            # Сохраняем детальную информацию
            key = f"tokens:detail:{user_id}:{timestamp}"
            self.redis_client.setex(key, 30 * 24 * 3600, json.dumps(token_data))
            
            # Обновляем дневные счетчики
            self.redis_client.hincrby(f"tokens:daily:{today}", "prompt_tokens", prompt_tokens)
            self.redis_client.hincrby(f"tokens:daily:{today}", "completion_tokens", completion_tokens)
            self.redis_client.hincrby(f"tokens:daily:{today}", "total_tokens", total_tokens)
            self.redis_client.hincrby(f"tokens:daily:{today}", "requests_count", 1)
            
            # Обновляем пользовательские счетчики
            self.redis_client.hincrby(f"tokens:user:{user_id}", "prompt_tokens", prompt_tokens)
            self.redis_client.hincrby(f"tokens:user:{user_id}", "completion_tokens", completion_tokens)
            self.redis_client.hincrby(f"tokens:user:{user_id}", "total_tokens", total_tokens)
            self.redis_client.hincrby(f"tokens:user:{user_id}", "requests_count", 1)
            
            # Обновляем общие счетчики
            self.redis_client.hincrby("tokens:total", "prompt_tokens", prompt_tokens)
            self.redis_client.hincrby("tokens:total", "completion_tokens", completion_tokens)
            self.redis_client.hincrby("tokens:total", "total_tokens", total_tokens)
            self.redis_client.hincrby("tokens:total", "requests_count", 1)
            
            logger.debug(f"Токены записаны: {total_tokens} для пользователя {user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при логировании токенов: {e}")
    
    def get_token_stats(self, period: str = "today") -> Dict:
        """Получает статистику использования токенов"""
        if not self.redis_client:
            return {}
            
        try:
            if period == "today":
                today = datetime.now().strftime("%Y-%m-%d")
                stats = self.redis_client.hgetall(f"tokens:daily:{today}")
            elif period == "total":
                stats = self.redis_client.hgetall("tokens:total")
            else:
                # Для других периодов можно добавить логику
                stats = {}
            
            # Конвертируем в int
            result = {}
            for key, value in stats.items():
                if isinstance(key, bytes):
                    key = key.decode()
                if isinstance(value, bytes):
                    value = value.decode()
                result[key] = int(value) if value.isdigit() else 0
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики токенов: {e}")
            return {}
    
    def get_user_token_stats(self, user_id: str) -> Dict:
        """Получает статистику токенов для конкретного пользователя"""
        if not self.redis_client:
            return {}
            
        try:
            stats = self.redis_client.hgetall(f"tokens:user:{user_id}")
            result = {}
            for key, value in stats.items():
                if isinstance(key, bytes):
                    key = key.decode()
                if isinstance(value, bytes):
                    value = value.decode()
                result[key] = int(value) if value.isdigit() else 0
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении токенов пользователя {user_id}: {e}")
            return {}
    
    def calculate_token_cost(self, prompt_tokens: int, completion_tokens: int, model: str = "gpt-4o-mini") -> float:
        """Рассчитывает стоимость токенов в USD"""
        # Цены OpenAI на декабрь 2024 (за 1M токенов)
        pricing = {
            "gpt-4o-mini": {
                "input": 0.15,   # $0.15 за 1M input токенов
                "output": 0.60   # $0.60 за 1M output токенов
            },
            "gpt-4o": {
                "input": 2.50,
                "output": 10.00
            },
            "gpt-4": {
                "input": 30.00,
                "output": 60.00
            }
        }
        
        if model not in pricing:
            model = "gpt-4o-mini"  # По умолчанию
        
        input_cost = (prompt_tokens / 1_000_000) * pricing[model]["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing[model]["output"]
        
        return input_cost + output_cost
    
    def get_token_cost_stats(self, period: str = "today") -> Dict:
        """Получает статистику стоимости токенов"""
        token_stats = self.get_token_stats(period)
        
        if not token_stats:
            return {"total_cost_usd": 0.0, "requests_count": 0}
        
        prompt_tokens = token_stats.get("prompt_tokens", 0)
        completion_tokens = token_stats.get("completion_tokens", 0)
        requests_count = token_stats.get("requests_count", 0)
        
        total_cost = self.calculate_token_cost(prompt_tokens, completion_tokens)
        
        return {
            "total_cost_usd": round(total_cost, 4),
            "requests_count": requests_count,
            "avg_cost_per_request": round(total_cost / max(requests_count, 1), 4)
        }

    def _update_counters(self, user_id: str, action: str):
        """Обновляет счетчики действий"""
        try:
            # Общий счетчик действий пользователя
            self.redis_client.hincrby(f"user_stats:{user_id}", action, 1)
            self.redis_client.hincrby(f"user_stats:{user_id}", "total_actions", 1)
            
            # Глобальные счетчики
            today = datetime.now().strftime("%Y-%m-%d")
            self.redis_client.hincrby(f"daily_stats:{today}", action, 1)
            self.redis_client.hincrby(f"daily_stats:{today}", "total_actions", 1)
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении счетчиков: {e}")
    
    def get_user_stats(self, user_id: str) -> Dict:
        """Получает статистику пользователя"""
        if not self.redis_client:
            return {}
            
        try:
            stats = self.redis_client.hgetall(f"user_stats:{user_id}")
            return {k.decode() if isinstance(k, bytes) else k: 
                   int(v.decode() if isinstance(v, bytes) else v) 
                   for k, v in stats.items()}
        except Exception as e:
            logger.error(f"Ошибка при получении статистики пользователя: {e}")
            return {}
    
    def get_daily_stats(self, date: str = None) -> Dict:
        """Получает статистику за день"""
        if not self.redis_client:
            return {}
            
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
            
        try:
            stats = self.redis_client.hgetall(f"daily_stats:{date}")
            return {k.decode() if isinstance(k, bytes) else k: 
                   int(v.decode() if isinstance(v, bytes) else v) 
                   for k, v in stats.items()}
        except Exception as e:
            logger.error(f"Ошибка при получении дневной статистики: {e}")
            return {}
    
    def log_question_rating(self, user_id: str, question: str, rating: int):
        """Логирует оценку ответа на вопрос"""
        if not self.redis_client:
            return
            
        try:
            rating_data = {
                'user_id': user_id,
                'question': question[:200],  # Ограничиваем длину
                'rating': rating,
                'timestamp': datetime.now().isoformat()
            }
            
            key = f"ratings:{user_id}:{datetime.now().timestamp()}"
            self.redis_client.setex(key, 30 * 24 * 3600, json.dumps(rating_data))
            
            # Обновляем средний рейтинг
            self._update_average_rating(rating)

            # Обновляем распределение рейтингов (глобально и за сегодня)
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                self.redis_client.hincrby("ratings:distribution", str(rating), 1)
                self.redis_client.hincrby(f"ratings:daily:{today}:distribution", str(rating), 1)
            except Exception:
                pass
            
        except Exception as e:
            logger.error(f"Ошибка при логировании оценки: {e}")

    def get_ratings_distribution(self, period: str = "total") -> Dict:
        """Возвращает распределение оценок 1..5 за период"""
        if not self.redis_client:
            return {}
        try:
            if period == "today":
                today = datetime.now().strftime("%Y-%m-%d")
                data = self.redis_client.hgetall(f"ratings:daily:{today}:distribution")
            else:
                data = self.redis_client.hgetall("ratings:distribution")
            dist = {}
            for k, v in data.items():
                key = k.decode() if isinstance(k, bytes) else k
                val = v.decode() if isinstance(v, bytes) else v
                dist[int(key)] = int(val) if str(val).isdigit() else 0
            # Гарантируем ключи 1..5
            return {i: dist.get(i, 0) for i in range(1, 6)}
        except Exception as e:
            logger.error(f"Ошибка при получении распределения рейтингов: {e}")
            return {}

    def log_helpfulness(self, user_id: str, question: str, helpful: bool):
        """Логирует нажатие 'полезно/не помогло'"""
        if not self.redis_client:
            return
        try:
            payload = {
                'user_id': user_id,
                'question': (question or '')[:200],
                'helpful': bool(helpful),
                'timestamp': datetime.now().isoformat()
            }
            key = f"helpfulness:{user_id}:{datetime.now().timestamp()}"
            self.redis_client.setex(key, 30 * 24 * 3600, json.dumps(payload))

            today = datetime.now().strftime("%Y-%m-%d")
            field = 'helpful_yes' if helpful else 'helpful_no'
            self.redis_client.hincrby(f"helpfulness:daily:{today}", field, 1)
            self.redis_client.hincrby("helpfulness:total", field, 1)
        except Exception as e:
            logger.error(f"Ошибка при логировании helpfulness: {e}")

    def get_helpfulness_stats(self, period: str = "today") -> Dict:
        """Возвращает статистику полезности (yes/no и доля)"""
        if not self.redis_client:
            return {"helpful_yes": 0, "helpful_no": 0, "helpful_share": 0.0}
        try:
            if period == "today":
                today = datetime.now().strftime("%Y-%m-%d")
                data = self.redis_client.hgetall(f"helpfulness:daily:{today}")
            else:
                data = self.redis_client.hgetall("helpfulness:total")
            def _to_int(x):
                return int(x.decode() if isinstance(x, bytes) else x) if x else 0
            yes = _to_int(data.get('helpful_yes', 0))
            no = _to_int(data.get('helpful_no', 0))
            total = max(yes + no, 1)
            return {
                "helpful_yes": yes,
                "helpful_no": no,
                "helpful_share": round(yes / total, 3)
            }
        except Exception as e:
            logger.error(f"Ошибка при получении helpfulness: {e}")
            return {"helpful_yes": 0, "helpful_no": 0, "helpful_share": 0.0}
    
    def _update_average_rating(self, rating: int):
        """Обновляет средний рейтинг"""
        try:
            # Используем скользящее среднее
            current_avg = float(self.redis_client.get("avg_rating") or 0)
            current_count = int(self.redis_client.get("rating_count") or 0)
            
            new_count = current_count + 1
            new_avg = (current_avg * current_count + rating) / new_count
            
            self.redis_client.set("avg_rating", new_avg)
            self.redis_client.set("rating_count", new_count)
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении среднего рейтинга: {e}")
    
    def get_average_rating(self) -> float:
        """Получает средний рейтинг"""
        if not self.redis_client:
            return 0.0
            
        try:
            return float(self.redis_client.get("avg_rating") or 0)
        except Exception as e:
            logger.error(f"Ошибка при получении среднего рейтинга: {e}")
            return 0.0