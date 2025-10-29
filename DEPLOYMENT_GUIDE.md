# 🚀 Инструкция по применению изменений на ВМ

## Подготовка

### 1. Закоммитьте изменения в Git (если еще не сделали)

```bash
# На локальной машине в папке проекта
git add worker.py CHANGES.md DEPLOYMENT_GUIDE.md
git commit -m "Добавлена поддержка медиафайлов и обновлен формат уведомлений"
git push origin main
```

## Применение на ВМ

### Вариант 1: Через Git Pull (Рекомендуется)

```bash
# 1. Подключаемся к ВМ
ssh ваш-пользователь@IP-адрес-ВМ

# 2. Переходим в директорию проекта
cd ~/monitorshik  # или путь где у вас проект

# 3. Создаем резервную копию
cp worker.py worker.py.backup.$(date +%Y%m%d_%H%M%S)

# 4. Останавливаем сервис
sudo systemctl stop telegram-monitor

# 5. Скачиваем изменения из Git
git pull origin main

# 6. Проверяем что файл обновился
ls -lh worker.py

# 7. Запускаем сервис
sudo systemctl start telegram-monitor

# 8. Проверяем статус
sudo systemctl status telegram-monitor

# 9. Смотрим логи в реальном времени
sudo journalctl -u telegram-monitor -f
```

### Вариант 2: Ручное копирование (если Git недоступен)

```bash
# 1. На ЛОКАЛЬНОЙ машине - скопируйте содержимое файла
cat worker.py

# 2. Подключитесь к ВМ
ssh ваш-пользователь@IP-адрес-ВМ

# 3. Переходим в директорию проекта
cd ~/monitorshik

# 4. Создаем резервную копию
cp worker.py worker.py.backup.$(date +%Y%m%d_%H%M%S)

# 5. Останавливаем сервис
sudo systemctl stop telegram-monitor

# 6. Открываем редактор
nano worker.py
# или
vim worker.py

# 7. Удаляем все содержимое и вставляем новое
# В nano: Ctrl+K много раз для удаления, затем вставка из буфера
# В vim: ggdG для удаления всего, затем i и вставка, затем :wq

# 8. Запускаем сервис
sudo systemctl start telegram-monitor

# 9. Проверяем статус
sudo systemctl status telegram-monitor

# 10. Смотрим логи
sudo journalctl -u telegram-monitor -f
```

## Проверка работоспособности

### 1. Проверьте что сервис запустился

```bash
sudo systemctl status telegram-monitor
```

Должно быть: `Active: active (running)`

### 2. Проверьте логи

```bash
sudo journalctl -u telegram-monitor -n 50
```

Вы должны увидеть:
```
Telegram Comment Monitor v1.0
Конфигурация загружена:
  - Timezone: ...
  - Каналов для мониторинга: ...
Telegram клиент подключен
Мониторинг запущен для X дискуссионных групп
Ожидание новых комментариев...
```

### 3. Протестируйте функционал

Напишите тестовые комментарии в отслеживаемых каналах:

1. **Текстовый комментарий** 
   - Должен прийти в новом формате с blockquote

2. **Комментарий с фото**
   - Должно прийти фото с caption в новом формате

3. **Комментарий со стикером**
   - Должен прийти стикер с caption

4. **Комментарий с коротким видео**
   - Должно прийти видео (если < 10 МБ)

## Что делать если что-то пошло не так

### Сервис не запускается

```bash
# Смотрим подробные логи ошибок
sudo journalctl -u telegram-monitor -n 100 --no-pager

# Если видим ошибку Python - откатываемся
sudo systemctl stop telegram-monitor
cp worker.py.backup.TIMESTAMP worker.py  # замените TIMESTAMP на реальный
sudo systemctl start telegram-monitor
```

### Уведомления не приходят

```bash
# Проверяем логи на наличие ошибок отправки
sudo journalctl -u telegram-monitor -f | grep -i error

# Проверяем что бот имеет права в группе
# Проверяем что ALERT_CHAT_ID корректный
```

### Медиафайлы не отправляются

Смотрите логи - там будет указано:
- Тип медиа который был обнаружен
- Размер файла
- Попытки отправки
- Ошибки если были

Если медиафайл не отправился, должно прийти fallback уведомление.

## Откат к старой версии

```bash
# 1. Остановить сервис
sudo systemctl stop telegram-monitor

# 2. Восстановить из бекапа
# Посмотрите доступные бекапы:
ls -lh worker.py.backup*

# Восстановите нужный:
cp worker.py.backup.20251029_143000 worker.py

# 3. Запустить сервис
sudo systemctl start telegram-monitor

# 4. Проверить
sudo systemctl status telegram-monitor
```

## Полезные команды

```bash
# Перезапустить сервис
sudo systemctl restart telegram-monitor

# Остановить сервис
sudo systemctl stop telegram-monitor

# Запустить сервис
sudo systemctl start telegram-monitor

# Статус сервиса
sudo systemctl status telegram-monitor

# Логи в реальном времени
sudo journalctl -u telegram-monitor -f

# Последние 100 строк логов
sudo journalctl -u telegram-monitor -n 100

# Логи за последний час
sudo journalctl -u telegram-monitor --since "1 hour ago"

# Очистить логи (если они сильно разрослись)
sudo journalctl --vacuum-time=7d
```

## Мониторинг

После применения изменений рекомендую следить за:

1. **Использование памяти** - медиафайлы скачиваются в RAM
   ```bash
   free -h
   top -p $(pgrep -f worker.py)
   ```

2. **Размер логов**
   ```bash
   sudo journalctl --disk-usage
   ```

3. **Работоспособность** - первые несколько часов
   ```bash
   sudo journalctl -u telegram-monitor -f
   ```

## Поддержка

Если возникли проблемы:

1. Проверьте логи: `sudo journalctl -u telegram-monitor -n 200`
2. Убедитесь что зависимости установлены: `pip list | grep -E "(telethon|aiohttp|pytz)"`
3. Проверьте переменные окружения в файле сервиса
4. Откатитесь на старую версию и сообщите об ошибке

---

**Удачного деплоя! 🚀**

