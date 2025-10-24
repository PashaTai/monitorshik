import asyncio
import logging
from telethon import TelegramClient, events
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
import os

# Загружаем переменные из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Настройки Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Настройки Telegram API
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
PHONE = os.getenv('PHONE')

# Каналы и группы для мониторинга
MONITORED_CHANNELS = [
    {
        "id": "1711569914",
        "name": "Парфенчиков | Карелия"
    }
]

NOTIFICATION_GROUPS = [
    {
        "id": "4906053803",
        "name": "Test-Group"
    }
]

USER_ID = "0507a4f8-45da-45e7-ad70-206504d89619"

async def log_to_database(log_type: str, message: str, details: dict = None):
    """Логирование событий в базу данных"""
    try:
        supabase.table("bot_logs").insert({
            "user_id": USER_ID,
            "log_type": log_type,
            "message": message,
            "details": details
        }).execute()
    except Exception as e:
        logger.error(f"Failed to log to database: {e}")

async def save_comment(channel_id: str, post_id: int, comment_id: int, 
                       comment_text: str, author_id: int, author_name: str):
    """Сохранение комментария в базу данных"""
    try:
        supabase.table("comment_logs").insert({
            "user_id": USER_ID,
            "channel_id": str(channel_id),
            "post_id": str(post_id),
            "comment_id": str(comment_id),
            "comment_text": comment_text,
            "author_id": str(author_id),
            "author_name": author_name
        }).execute()
        logger.info(f"Saved comment {comment_id} from {author_name}")
    except Exception as e:
        logger.error(f"Failed to save comment: {e}")

async def send_notification(bot_client, comment_text: str, channel_name: str, 
                           author_name: str, post_id: int):
    """Отправка уведомлений в группы"""
    message = f"""
🔔 New Comment Alert

Channel: {channel_name}
Post ID: {post_id}
Author: {author_name}

Comment:
{comment_text}
"""
    
    for group in NOTIFICATION_GROUPS:
        try:
            await bot_client.send_message(int(group["id"]), message)
            logger.info(f"Notification sent to {group['name']}")
        except Exception as e:
            logger.error(f"Failed to send to {group['name']}: {e}")

async def main():
    # Инициализация клиентов
    client = TelegramClient('session', API_ID, API_HASH)
    bot_client = TelegramClient('bot_session', API_ID, API_HASH)
    
    await client.start(phone=PHONE)
    await bot_client.start(bot_token=BOT_TOKEN)
    
    await log_to_database("info", "Bot started successfully")
    logger.info("Bot started successfully")
    
    @client.on(events.NewMessage)
    async def handler(event):
        """Обработка новых сообщений (включая комментарии)"""
        try:
            # Проверяем, если сообщение от отслеживаемого канала
            chat = await event.get_chat()
            chat_id = str(chat.id)
            
            channel_info = next(
                (ch for ch in MONITORED_CHANNELS if ch["id"] == chat_id), 
                None
            )
            
            if not channel_info:
                return
                
            # Проверяем, если это ответ (комментарий)
            if event.reply_to_msg_id:
                sender = await event.get_sender()
                
                await save_comment(
                    channel_id=chat_id,
                    post_id=event.reply_to_msg_id,
                    comment_id=event.id,
                    comment_text=event.text or "",
                    author_id=sender.id,
                    author_name=f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                )
                
                await send_notification(
                    bot_client,
                    event.text or "",
                    channel_info["name"],
                    f"{sender.first_name or ''} {sender.last_name or ''}".strip(),
                    event.reply_to_msg_id
                )
                
                await log_to_database(
                    "success",
                    f"Processed comment in {channel_info['name']}"
                )
        
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await log_to_database("error", f"Error handling message: {str(e)}")
    
    logger.info("Monitoring channels for comments...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
