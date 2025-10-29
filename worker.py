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
from io import BytesIO

import aiohttp
import pytz
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetFullChannelRequest, JoinChannelRequest
from telethon.tl.types import Channel, MessageMediaPhoto, MessageMediaDocument
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
        
        # DEBUG: Логируем ВСЕ события
        logger.info(f"🔔 Получено событие: chat_id={event.chat_id}, message_id={message.id}")
        logger.info(f"   Текст: {message.text[:50] if message.text else '(нет текста)'}...")
        
        # Фильтрация: только сообщения с reply (комментарии/ответы)
        if not message.reply_to:
            logger.info("   ❌ Отфильтровано: нет reply_to")
            return
        
        # Определяем ID поста в группе обсуждений
        discussion_post_id = message.reply_to.reply_to_top_id or message.reply_to.reply_to_msg_id
        logger.info(f"   ✅ Это комментарий к посту/сообщению {discussion_post_id} в группе")
        chat_id = event.chat_id
        
        # Получаем информацию о канале из маппинга
        channel_info = self.linked_groups.get(chat_id)
        if not channel_info:
            logger.warning(f"Получено сообщение из неизвестной группы {chat_id}")
            return
        
        channel_username, channel_title = channel_info
        
        # Получаем оригинальное сообщение из группы, чтобы найти ID поста в канале
        channel_post_id = discussion_post_id  # По умолчанию
        try:
            original_message = await self.client.get_messages(
                chat_id, 
                ids=discussion_post_id
            )
            
            if original_message and original_message.fwd_from:
                # Извлекаем ID оригинального поста из канала
                if hasattr(original_message.fwd_from, 'channel_post') and original_message.fwd_from.channel_post:
                    channel_post_id = original_message.fwd_from.channel_post
                    logger.info(f"   ✅ Определен ID поста в канале: {channel_post_id}")
                elif hasattr(original_message.fwd_from, 'saved_from_msg_id') and original_message.fwd_from.saved_from_msg_id:
                    channel_post_id = original_message.fwd_from.saved_from_msg_id
                    logger.info(f"   ✅ Определен ID поста в канале: {channel_post_id}")
            
            if channel_post_id == discussion_post_id:
                logger.warning(f"   ⚠️ Не удалось определить ID поста в канале, используем ID из группы")
                
        except Exception as e:
            logger.error(f"   ❌ Ошибка при получении оригинального сообщения: {e}")
        
        # Получаем информацию об авторе
        sender = await event.get_sender()
        author_first = sender.first_name or ""
        author_last = sender.last_name or ""
        author_name = f"{author_first} {author_last}".strip() or "Неизвестный"
        author_username = f"@{sender.username}" if sender.username else ""
        author_id = sender.id
        
        # Время комментария
        msg_time = message.date
        local_time = msg_time.astimezone(self.tz)
        time_str = local_time.strftime("%H:%M %d.%m.%Y")
        
        # Формируем ссылку на пост
        if channel_username:
            post_link = f"https://t.me/{channel_username}/{channel_post_id}"
        else:
            post_link = str(channel_post_id)
        
        logger.info(
            f"Новый комментарий от {author_name} в {channel_title} к посту {channel_post_id}"
        )
        
        # Формируем базовый caption (без содержимого комментария)
        base_caption = self._format_base_caption(
            channel_title, author_name, author_username, author_id, time_str
        )
        
        # Определяем тип содержимого и отправляем соответствующее уведомление
        if message.text:
            # Текстовое сообщение
            await self._send_text_notification(base_caption, message.text, post_link)
        elif message.media:
            # Медиафайл
            await self._handle_media_message(message, base_caption, post_link)
        else:
            # Пустое сообщение (редкий случай)
            await self._send_fallback_notification(base_caption, post_link)
    
    def _format_base_caption(
        self, 
        channel_title: str, 
        author_name: str, 
        author_username: str, 
        author_id: int, 
        time_str: str
    ) -> str:
        """Формирует базовую часть caption с информацией о комментарии"""
        return (
            f"✈️ <b>TG</b> | {channel_title}\n"
            f"👤 {author_name} {author_username}\n"
            f"🆔 <code>{author_id}</code>\n"
            f"🕐 {time_str}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
    
    async def _send_text_notification(self, base_caption: str, text: str, post_link: str):
        """Отправляет текстовое уведомление с форматированием"""
        notification = (
            f"{base_caption}\n"
            f"<blockquote>{text}</blockquote>\n\n"
            f"<a href=\"{post_link}\">🔗 Открыть пост</a>"
        )
        await self._send_notification(notification)
    
    async def _send_fallback_notification(self, base_caption: str, post_link: str):
        """Отправляет fallback уведомление когда не удалось отправить медиа или контент пустой"""
        notification = (
            f"{base_caption}\n"
            f"<b>Пользователь прислал медиафайл, пожалуйста откройте пост чтобы увидеть содержание</b>\n\n"
            f"<a href=\"{post_link}\">🔗 Открыть пост</a>"
        )
        await self._send_notification(notification)
    
    async def _handle_media_message(self, message, base_caption: str, post_link: str):
        """Обрабатывает сообщения с медиафайлами"""
        media = message.media
        
        # Определяем тип медиа и размер
        if isinstance(media, MessageMediaPhoto):
            # Фото - всегда отправляем
            logger.info("   📷 Обнаружено фото, отправляем...")
            await self._send_photo(message, base_caption, post_link)
        
        elif isinstance(media, MessageMediaDocument):
            doc = media.document
            mime_type = doc.mime_type if hasattr(doc, 'mime_type') else ''
            file_size = doc.size if hasattr(doc, 'size') else 0
            
            logger.info(f"   📎 Обнаружен документ: mime={mime_type}, size={file_size} bytes")
            
            # Проверяем тип документа
            if 'video' in mime_type or any(
                attr for attr in doc.attributes 
                if attr.__class__.__name__ == 'DocumentAttributeVideo'
            ):
                # Видео
                if file_size > 10 * 1024 * 1024:  # 10 МБ
                    logger.info(f"   ⚠️ Видео слишком большое ({file_size} bytes), отправляем fallback")
                    await self._send_fallback_notification(base_caption, post_link)
                else:
                    logger.info("   🎥 Отправляем видео...")
                    await self._send_video(message, base_caption, post_link)
            
            elif any(
                attr for attr in doc.attributes 
                if attr.__class__.__name__ == 'DocumentAttributeSticker'
            ):
                # Стикер
                logger.info("   🖼️ Отправляем стикер...")
                await self._send_document(message, base_caption, post_link)
            
            elif any(
                attr for attr in doc.attributes 
                if attr.__class__.__name__ == 'DocumentAttributeAnimated'
            ) or 'gif' in mime_type:
                # GIF или анимация
                logger.info("   🎬 Отправляем GIF/анимацию...")
                await self._send_document(message, base_caption, post_link)
            
            elif 'audio' in mime_type or any(
                attr for attr in doc.attributes 
                if attr.__class__.__name__ in ['DocumentAttributeAudio']
            ):
                # Голосовое или аудио
                is_voice = any(
                    attr for attr in doc.attributes 
                    if attr.__class__.__name__ == 'DocumentAttributeAudio' 
                    and hasattr(attr, 'voice') and attr.voice
                )
                if is_voice:
                    logger.info("   🎤 Отправляем голосовое сообщение...")
                    await self._send_voice(message, base_caption, post_link)
                else:
                    logger.info("   🎵 Отправляем аудио как документ...")
                    await self._send_document(message, base_caption, post_link)
            else:
                # Другой документ
                logger.info("   📄 Отправляем документ...")
                await self._send_document(message, base_caption, post_link)
        else:
            # Неизвестный тип медиа
            logger.warning(f"   ⚠️ Неизвестный тип медиа: {type(media)}")
            await self._send_fallback_notification(base_caption, post_link)
    
    async def _send_photo(self, message, base_caption: str, post_link: str):
        """Скачивает и отправляет фото с caption"""
        try:
            # Скачиваем фото в память
            photo_bytes = BytesIO()
            await message.download_media(file=photo_bytes)
            photo_bytes.seek(0)
            
            # Отправляем через Bot API
            await self._send_media_to_bot(
                'sendPhoto',
                photo_bytes,
                base_caption,
                'photo.jpg',
                post_link
            )
        except Exception as e:
            logger.error(f"   ❌ Ошибка при отправке фото: {e}")
            await self._send_fallback_notification(base_caption, post_link)
    
    async def _send_video(self, message, base_caption: str, post_link: str):
        """Скачивает и отправляет видео с caption"""
        try:
            # Скачиваем видео в память
            video_bytes = BytesIO()
            await message.download_media(file=video_bytes)
            video_bytes.seek(0)
            
            # Отправляем через Bot API
            await self._send_media_to_bot(
                'sendVideo',
                video_bytes,
                base_caption,
                'video.mp4',
                post_link
            )
        except Exception as e:
            logger.error(f"   ❌ Ошибка при отправке видео: {e}")
            await self._send_fallback_notification(base_caption, post_link)
    
    async def _send_document(self, message, base_caption: str, post_link: str):
        """Скачивает и отправляет документ (стикер/GIF) с caption"""
        try:
            # Скачиваем документ в память
            doc_bytes = BytesIO()
            await message.download_media(file=doc_bytes)
            doc_bytes.seek(0)
            
            # Определяем имя файла
            filename = 'document'
            if hasattr(message.media, 'document'):
                doc = message.media.document
                for attr in doc.attributes:
                    if hasattr(attr, 'file_name'):
                        filename = attr.file_name
                        break
            
            # Отправляем через Bot API
            await self._send_media_to_bot(
                'sendDocument',
                doc_bytes,
                base_caption,
                filename,
                post_link
            )
        except Exception as e:
            logger.error(f"   ❌ Ошибка при отправке документа: {e}")
            await self._send_fallback_notification(base_caption, post_link)
    
    async def _send_voice(self, message, base_caption: str, post_link: str):
        """Скачивает и отправляет голосовое сообщение с caption"""
        try:
            # Скачиваем голосовое в память
            voice_bytes = BytesIO()
            await message.download_media(file=voice_bytes)
            voice_bytes.seek(0)
            
            # Отправляем через Bot API
            await self._send_media_to_bot(
                'sendVoice',
                voice_bytes,
                base_caption,
                'voice.ogg',
                post_link
            )
        except Exception as e:
            logger.error(f"   ❌ Ошибка при отправке голосового: {e}")
            await self._send_fallback_notification(base_caption, post_link)
    
    async def _send_media_to_bot(
        self, 
        method: str, 
        media_bytes: BytesIO, 
        caption: str,
        filename: str,
        post_link: str
    ):
        """Отправляет медиафайл через Bot API с caption"""
        url = f"https://api.telegram.org/bot{self.config.bot_token}/{method}"
        
        # Добавляем ссылку на пост в caption
        full_caption = f"{caption}\n\n<a href=\"{post_link}\">🔗 Открыть пост</a>"
        
        # Определяем имя поля для разных типов медиа
        field_name_map = {
            'sendPhoto': 'photo',
            'sendVideo': 'video',
            'sendDocument': 'document',
            'sendVoice': 'voice'
        }
        field_name = field_name_map.get(method, 'document')
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                # Создаем form data
                data = aiohttp.FormData()
                data.add_field('chat_id', str(self.config.alert_chat_id))
                data.add_field('caption', full_caption)
                data.add_field('parse_mode', 'HTML')
                
                # Добавляем файл
                media_bytes.seek(0)  # Возвращаемся в начало
                data.add_field(
                    field_name,
                    media_bytes,
                    filename=filename,
                    content_type='application/octet-stream'
                )
                
                async with self.http_session.post(url, data=data) as response:
                    if response.status == 200:
                        logger.info(f"   ✅ Медиафайл успешно отправлен ({method})")
                        return
                    else:
                        error_text = await response.text()
                        logger.warning(
                            f"   Попытка {attempt}/{max_retries}: "
                            f"Ошибка отправки медиа (status {response.status}): {error_text}"
                        )
            except Exception as e:
                logger.warning(f"   Попытка {attempt}/{max_retries}: Ошибка отправки медиа: {e}")
            
            if attempt < max_retries:
                delay = 2 ** (attempt - 1)
                await asyncio.sleep(delay)
        
        # Если не удалось отправить медиа, выбрасываем исключение
        raise Exception(f"Не удалось отправить медиа после {max_retries} попыток")
    
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


