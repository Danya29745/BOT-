"""
Модуль для отправки уведомлений администратору
"""
import logging
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError
from .config import ADMIN_CHAT_ID, ENABLE_ADMIN_NOTIFICATIONS

logger = logging.getLogger(__name__)

class AdminNotifier:
    """Класс для отправки уведомлений администратору"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.admin_chat_id = ADMIN_CHAT_ID
        self.enabled = ENABLE_ADMIN_NOTIFICATIONS and self.admin_chat_id
        
        if not self.enabled:
            logger.warning("Уведомления администратора отключены или не настроен ADMIN_CHAT_ID")
    
    async def send_bug_report(self, user_id: str, user_name: str, report: str):
        """Отправляет отчет об ошибке администратору"""
        if not self.enabled:
            return
            
        try:
            message = f"""
🐛 **НОВЫЙ ОТЧЕТ ОБ ОШИБКЕ**

👤 **Пользователь:** {user_name} (ID: `{user_id}`)
📅 **Время:** {self._get_current_time()}

📝 **Описание проблемы:**
{report}

---
Для ответа пользователю используйте ID: `{user_id}`
            """
            
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Отчет об ошибке от пользователя {user_id} отправлен администратору")
            
        except TelegramError as e:
            logger.error(f"Ошибка при отправке отчета об ошибке администратору: {e}")
    
    async def send_improvement_suggestion(self, user_id: str, user_name: str, suggestion: str):
        """Отправляет предложение по улучшению администратору"""
        if not self.enabled:
            return
            
        try:
            message = f"""
💡 **НОВОЕ ПРЕДЛОЖЕНИЕ ПО УЛУЧШЕНИЮ**

👤 **Пользователь:** {user_name} (ID: `{user_id}`)
📅 **Время:** {self._get_current_time()}

💭 **Предложение:**
{suggestion}

---
Для ответа пользователю используйте ID: `{user_id}`
            """
            
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Предложение от пользователя {user_id} отправлено администратору")
            
        except TelegramError as e:
            logger.error(f"Ошибка при отправке предложения администратору: {e}")
    
    async def send_low_rating_alert(self, user_id: str, user_name: str, rating: int, question: str):
        """Отправляет уведомление о низкой оценке"""
        if not self.enabled or rating >= 3:  # Уведомляем только о низких оценках
            return
            
        try:
            message = f"""
⭐ **НИЗКАЯ ОЦЕНКА ОТВЕТА**

👤 **Пользователь:** {user_name} (ID: `{user_id}`)
⭐ **Оценка:** {rating}/5 {'⭐' * rating}
📅 **Время:** {self._get_current_time()}

❓ **Вопрос:**
{question[:200]}{'...' if len(question) > 200 else ''}

---
Возможно, стоит улучшить ответ на подобные вопросы.
            """
            
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Уведомление о низкой оценке от пользователя {user_id} отправлено")
            
        except TelegramError as e:
            logger.error(f"Ошибка при отправке уведомления о низкой оценке: {e}")
    
    async def send_daily_stats(self, stats: dict):
        """Отправляет ежедневную статистику"""
        if not self.enabled:
            return
            
        try:
            message = f"""
📊 **ЕЖЕДНЕВНАЯ СТАТИСТИКА**

📅 **Дата:** {self._get_current_date()}

📈 **Активность:**
• Всего действий: {stats.get('total_actions', 0)}
• Задано вопросов: {stats.get('ask_question', 0)}
• Проверено документов: {stats.get('check_document', 0)}
• Просмотрено законов: {stats.get('view_law', 0)}

💬 **Обратная связь:**
• Отчеты об ошибках: {stats.get('bug_report', 0)}
• Предложения: {stats.get('improvement_suggestion', 0)}
• Оценки ответов: {stats.get('rate_answer', 0)}

⭐ **Средний рейтинг:** {stats.get('avg_rating', 0):.1f}/5.0
            """
            
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info("Ежедневная статистика отправлена администратору")
            
        except TelegramError as e:
            logger.error(f"Ошибка при отправке статистики: {e}")
    
    async def send_error_alert(self, error_type: str, error_message: str, user_id: str = None):
        """Отправляет уведомление о критической ошибке"""
        if not self.enabled:
            return
            
        try:
            message = f"""
🚨 **КРИТИЧЕСКАЯ ОШИБКА**

⚠️ **Тип:** {error_type}
📅 **Время:** {self._get_current_time()}
👤 **Пользователь:** {user_id or 'Неизвестен'}

🔍 **Детали:**
{error_message}

---
Требуется немедленное внимание!
            """
            
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Уведомление об ошибке {error_type} отправлено администратору")
            
        except TelegramError as e:
            logger.error(f"Ошибка при отправке уведомления об ошибке: {e}")
    
    def _get_current_time(self) -> str:
        """Возвращает текущее время в читаемом формате"""
        from datetime import datetime
        return datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    def _get_current_date(self) -> str:
        """Возвращает текущую дату"""
        from datetime import datetime
        return datetime.now().strftime("%d.%m.%Y")