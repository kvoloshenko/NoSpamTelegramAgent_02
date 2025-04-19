from aiogram import Bot
from agents import tool
import logging

logger = logging.getLogger(__name__)

def create_tools(bot: Bot, target_group_id: str):
    @tool
    async def block_user(user_id: int, chat_id: int):
        """Блокирует пользователя. Параметры: user_id, chat_id"""
        try:
            await bot.ban_chat_member(chat_id, user_id)
            logger.info(f"Blocked user {user_id}")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Block error: {e}")
            return {"status": "error", "details": str(e)}

    @tool
    async def delete_message(chat_id: int, message_id: int):
        """Удаляет сообщение. Параметры: chat_id, message_id"""
        try:
            await bot.delete_message(chat_id, message_id)
            logger.info(f"Deleted message {message_id}")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Delete error: {e}")
            return {"status": "error", "details": str(e)}

    @tool
    async def forward_message(chat_id: int, message_id: int):
        """Пересылает сообщение модераторам. Параметры: chat_id, message_id"""
        try:
            await bot.forward_message(
                chat_id=target_group_id,
                from_chat_id=chat_id,
                message_id=message_id
            )
            logger.info(f"Forwarded message {message_id}")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Forward error: {e}")
            return {"status": "error", "details": str(e)}

    @tool
    async def save_spam(sender_name: str, message_text: str):
        """Сохраняет спам в базу. Параметры: sender_name, message_text"""
        try:
            save_spam_message(sender_name, message_text)
            logger.info("Spam saved")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Save error: {e}")
            return {"status": "error", "details": str(e)}

    return [block_user, delete_message, forward_message, save_spam]