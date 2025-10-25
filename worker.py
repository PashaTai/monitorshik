#!/usr/bin/env python3
"""
Telegram Comment Monitor
Мониторинг комментариев в дискуссионных группах Telegram-каналов
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, Optional, Tuple
import logging

import aiohttp
import pytz
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetFullChannelRequest, JoinChannelRequest
from telethon.tl.types import Channel
from telethon.errors import (
    ChannelPrivateError,
    InviteHashExpiredError,
    FloodWaitError,
    UserAlreadyParticipantError,
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class Config:
    """Конфигурация приложения из переменных окружения"""
    
    def __init__(self):
        self.api_id = self._get_env_int("TG_API_ID")
        self.api_hash = self._get_env("TG_API_HASH")
        self.string_session = self._get_env("TG_STRING_SESSION")
        self.bot_token = self._get_env("BOT_TOKEN")
        self.alert_chat_id = self._get_env_int("ALERT_CHAT_ID")
        self.channels = self._parse_channels(self._get_env("CHANNELS"))
        self.timezone = os.getenv("TZ", "UTC")
    
    @staticmethod
    def _get_env(key: str) -> str:
        """Получить обязательную переменную окружения"""
        value = os.getenv(key)
        if not value:
            logger.error(f"Переменная окружения {key} не установлена")
            sys.exit(1)
        return value
    
    @staticmethod
    def _get_env_int(key: str) -> int:
        """Получить числовую переменную окружения"""
        value = Config._get_env(key)
        try:
            return int(value)
        except ValueError:
            logger.error(f"Переменная окружения {key} должна быть числом")
            sys.exit(1)
    
    @staticmethod
    def _parse_channels(channels_str: str) -> list[str]:
        """Парсинг списка каналов из строки"""
        channels = [ch.strip() for ch in channels_str.split(",") if ch.strip()]
        if not channels:
            logger.error("Список каналов CHANNELS пуст")
            sys.exit(1)
        return channels


class CommentMonitor:
    """Основной класс мониторинга комментариев"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = TelegramClient(
            StringSession(config.string_session),
            config.api_id,
            config.api_hash
        )
        # Маппинг: linked_chat_id -> (channel_username, channel_title)
        self.linked_groups: Dict[int, Tuple[Optional[str], str]] = {}
        # Список entity объектов групп для подписки на события
        self.group_entities = []
        self.http_session: Optional[aiohttp.ClientSession] = None
        
        try:
            self.tz = pytz.timezone(config.timezone)
        except pytz.UnknownTimeZoneError:
            logger.warning(f"Неизвестная timezone {config.timezone}, используется UTC")
            self.tz = pytz.UTC
    
    async def setup(self):
        """Настройка: резолв каналов, join, подписка на события"""
        logger.info("Запуск настройки мониторинга...")
        
        await self.client.start()
        logger.info("Telegram клиент подключен")
        
        # Создаем HTTP сессию для Bot API
        self.http_session = aiohttp.ClientSession()
        
        # Обрабатываем каждый канал
        for channel_username in self.config.channels:
            await self._setup_channel(channel_username)
        
        if not self.linked_groups:
            logger.error("Не удалось подключиться ни к одной дискуссионной группе")
            sys.exit(1)
        
        # Подписываемся на события в linked-группах используя entity объекты
        @self.client.on(events.NewMessage(chats=self.group_entities))
        async def handle_comment(event):
            await self._handle_new_message(event)
        
        logger.info(f"Мониторинг запущен для {len(self.linked_groups)} дискуссионных групп")
        logger.info("Ожидание новых комментариев...")
    
    async def _setup_channel(self, channel_username: str):
        """Настройка одного канала: резолв, join, получение linked группы"""
        try:
            # Резолв канала
            logger.info(f"Обработка канала: {channel_username}")
            entity = await self.client.get_entity(channel_username)
            
            if not isinstance(entity, Channel):
                logger.warning(f"{channel_username} не является каналом, пропускаем")
                return
            
            # Пытаемся вступить в канал
            try:
                await self.client(JoinChannelRequest(entity))
                logger.info(f"Вступили в канал {channel_username}")
            except UserAlreadyParticipantError:
                logger.info(f"Уже подписаны на канал {channel_username}")
            except (ChannelPrivateError, InviteHashExpiredError):
                logger.warning(f"Канал {channel_username} приватный/недоступен, пропускаем")
                return
            except Exception as e:
                logger.warning(f"Ошибка при вступлении в канал {channel_username}: {e}")
            
            # Получаем полную информацию о канале
            full_channel = await self.client(GetFullChannelRequest(entity))
            linked_chat_id = full_channel.full_chat.linked_chat_id
            
            if not linked_chat_id:
                logger.info(f"Канал {channel_username} не имеет привязанной группы обсуждений, пропускаем")
                return
            
            # Получаем информацию о linked группе
            linked_entity = await self.client.get_entity(linked_chat_id)
            
            # Пытаемся вступить в группу обсуждений
            try:
                await self.client(JoinChannelRequest(linked_entity))
                logger.info(f"Вступили в группу обсуждений канала {channel_username}")
            except UserAlreadyParticipantError:
                logger.info(f"Уже состоим в группе обсуждений канала {channel_username}")
            except (ChannelPrivateError, InviteHashExpiredError):
                logger.warning(
                    f"Группа обсуждений канала {channel_username} приватная/недоступна, пропускаем"
                )
                return
            except Exception as e:
                logger.warning(
                    f"Ошибка при вступлении в группу обсуждений {channel_username}: {e}"
                )
            
            # Конвертируем положительный ID в отрицательный формат для супергрупп
            if linked_chat_id > 0:
                linked_chat_id = -int(f"100{linked_chat_id}")
                logger.info(f"Конвертирован ID группы в формат супергруппы: {linked_chat_id}")
            
            # Сохраняем маппинг и entity объект для подписки на события
            channel_title = entity.title
            channel_user = entity.username
            self.linked_groups[linked_chat_id] = (channel_user, channel_title)
            self.group_entities.append(linked_entity)
            logger.info(f"Добавлен entity группы для мониторинга")
            
            logger.info(
                f"✓ Канал {channel_username} настроен. "
                f"Группа: {linked_chat_id}, Название: {channel_title}"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при обработке канала {channel_username}: {e}")
    
    async def _handle_new_message(self, event):
        """Обработчик новых сообщений в дискуссионных группах"""
        message = event.message
        
        # Фильтрация: только комментарии к постам
        if not message.reply_to or not message.reply_to.reply_to_top_id:
            return
        
        post_id = message.reply_to.reply_to_top_id
        chat_id = event.chat_id
        
        # Получаем информацию о канале из маппинга
        channel_info = self.linked_groups.get(chat_id)
        if not channel_info:
            logger.warning(f"Получено сообщение из неизвестной группы {chat_id}")
            return
        
        channel_username, channel_title = channel_info
        
        # Получаем информацию об авторе
        sender = await event.get_sender()
        author_first = sender.first_name or ""
        author_last = sender.last_name or ""
        author_name = f"{author_first} {author_last}".strip() or "Неизвестный"
        author_username = f"@{sender.username}" if sender.username else ""
        author_id = sender.id
        
        # Текст комментария
        comment_text = message.text or "(без текста)"
        
        # Время комментария
        msg_time = message.date
        local_time = msg_time.astimezone(self.tz)
        time_str = local_time.strftime("%H:%M %d.%m.%Y")
        
        # Формируем ссылку на пост
        if channel_username:
            post_link = f"https://t.me/{channel_username}/{post_id}"
        else:
            post_link = str(post_id)
        
        # Формируем уведомление
        notification = (
            f"Новый комментарий в <b>{channel_title}</b>\n"
            f"Пост: {post_link}\n"
            f"Автор: {author_name} {author_username} (tg://user?id={author_id})\n"
            f"Время: {time_str}\n\n"
            f"{comment_text}"
        )
        
        logger.info(
            f"Новый комментарий от {author_name} в {channel_title} к посту {post_id}"
        )
        
        # Отправляем уведомление через Bot API
        await self._send_notification(notification)
    
    async def _send_notification(self, text: str):
        """Отправка уведомления через Bot API с ретраями"""
        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        payload = {
            "chat_id": self.config.alert_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                async with self.http_session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info("Уведомление успешно отправлено")
                        return
                    else:
                        error_text = await response.text()
                        logger.warning(
                            f"Попытка {attempt}/{max_retries}: "
                            f"Ошибка отправки (status {response.status}): {error_text}"
                        )
            except Exception as e:
                logger.warning(f"Попытка {attempt}/{max_retries}: Ошибка отправки: {e}")
            
            # Если это не последняя попытка, ждем с экспоненциальной задержкой
            if attempt < max_retries:
                delay = 2 ** (attempt - 1)  # 1s, 2s, 4s, 8s, 16s
                logger.info(f"Повтор через {delay} секунд...")
                await asyncio.sleep(delay)
        
        logger.error(
            f"Не удалось отправить уведомление после {max_retries} попыток"
        )
    
    async def run(self):
        """Запуск мониторинга"""
        try:
            await self.setup()
            await self.client.run_until_disconnected()
        finally:
            if self.http_session:
                await self.http_session.close()


async def main():
    """Главная функция"""
    logger.info("=" * 50)
    logger.info("Telegram Comment Monitor v1.0")
    logger.info("=" * 50)
    
    # Загружаем конфигурацию
    config = Config()
    logger.info(f"Конфигурация загружена:")
    logger.info(f"  - Timezone: {config.timezone}")
    logger.info(f"  - Каналов для мониторинга: {len(config.channels)}")
    logger.info(f"  - Каналы: {', '.join(config.channels)}")
    
    # Создаем и запускаем монитор
    monitor = CommentMonitor(config)
    await monitor.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка по Ctrl+C")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

