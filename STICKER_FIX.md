# 🐛 Исправление: Стикер как файл → Стикер как стикер

## Проблема
Стикер отправлялся как файл `.webp` и нужно было его скачивать, а не отображался как обычный стикер в Telegram.

## Причина
Использовался метод Bot API `sendDocument` вместо `sendSticker`.

## Решение
Изменено 2 строки в методе `_send_document`:
- **Строка 465:** `sendDocument` → `sendSticker`
- **Строка 468:** поле `document` → `sticker`

## Было:
```python
url = f"https://api.telegram.org/bot{self.config.bot_token}/sendDocument"
data = aiohttp.FormData()
data.add_field('chat_id', str(self.config.alert_chat_id))
data.add_field('document', doc_bytes, filename='sticker.webp')
```

## Стало:
```python
url = f"https://api.telegram.org/bot{self.config.bot_token}/sendSticker"
data = aiohttp.FormData()
data.add_field('chat_id', str(self.config.alert_chat_id))
data.add_field('sticker', doc_bytes, filename='sticker.webp')
```

## Как работает теперь
1. **Первое сообщение** - текст с информацией:
   ```
   ✈️ TG | Парфенчиков|Карелия
   👤 Олег Ремской @olegosrem
   🆔 1776913410
   🕐 01:29 30.10.2025
   ━━━━━━━━━━━━━━━━━━
   
   📩 Пользователь отправил стикер
   
   🔗 Открыть пост
   ```

2. **Второе сообщение** - стикер (отображается как стикер, не как файл)

## Применение на ВМ

```bash
# На локальной машине
git add worker.py STICKER_FIX.md
git commit -m "fix: стикер теперь отображается корректно, а не как файл"
git push origin main

# На ВМ
sudo systemctl stop telegram-monitor
cd ~/monitorshik
git pull origin main
sudo systemctl start telegram-monitor
sudo journalctl -u telegram-monitor -f
```

## Тестирование
Отправьте стикер в комментарий → должно прийти 2 сообщения:
1. Информация (текст)
2. Стикер (отображается как стикер)

**Статус:** ✅ Готово
**Версия:** 1.1.2

