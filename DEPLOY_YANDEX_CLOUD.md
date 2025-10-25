# Деплой на Yandex Cloud

Полная инструкция по развертыванию Telegram Comment Monitor на виртуальной машине Yandex Cloud.

## Преимущества Yandex Cloud

✅ **Бесплатный Free Tier** - b1.nano входит в бесплатное использование  
✅ **Работает 24/7** - никогда не засыпает  
✅ **Полный контроль** - прямой доступ к серверу  
✅ **Быстрое соединение** - из России быстрее, чем зарубежные облака  
✅ **Простое обновление** - git pull + restart  

## Стоимость

При использовании **Free Tier**:
- b1.nano (1 vCPU, 1 GB RAM) - 20% машины бесплатно
- 32 GB HDD - бесплатно
- Публичный IP - ~80₽/месяц
- Исходящий трафик - первые 100 GB бесплатно

**Итого:** ~80₽/месяц за публичный IP

## Требования

- Аккаунт в Yandex Cloud (с привязанной картой для Free Tier)
- SSH-клиент (встроен в Windows 10+, macOS, Linux)
- Базовые знания терминала Linux (или просто следуйте инструкции)

---

## Быстрая установка (рекомендуется)

Используйте автоматический скрипт установки для упрощения процесса.

### Шаг 1: Создание виртуальной машины

1. Зайдите в [Yandex Cloud Console](https://console.cloud.yandex.ru/)
2. Выберите ваш каталог (folder) или создайте новый
3. Перейдите в **Compute Cloud** → **Виртуальные машины**
4. Нажмите **"Создать ВМ"**

**Настройки виртуальной машины:**

```
Имя: telegram-monitor
Зона доступности: ru-central1-a

Образ/загрузочный диск:
  - ОС: Ubuntu 22.04 LTS
  - Размер: 20 GB (достаточно для проекта)

Вычислительные ресурсы:
  - Платформа: Intel Ice Lake
  - Гарантированная доля vCPU: 20%
  - vCPU: 2
  - RAM: 1 GB
  - Конфигурация: b1.nano ← ВАЖНО для Free Tier!

Сетевые настройки:
  - Сеть: default
  - Публичный адрес: Автоматически
  - Внутренний IPv4: Автоматически

Доступ:
  - Логин: ubuntu
  - SSH-ключ: [Вставьте ваш публичный SSH-ключ]
```

**Как получить SSH-ключ (если у вас его нет):**

Windows PowerShell / macOS / Linux:
```bash
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
```

Ваш публичный ключ находится в:
- Windows: `C:\Users\ваш_user\.ssh\id_rsa.pub`
- macOS/Linux: `~/.ssh/id_rsa.pub`

Скопируйте содержимое и вставьте в поле SSH-ключ.

5. Нажмите **"Создать ВМ"**
6. Дождитесь создания (1-2 минуты)
7. **Скопируйте публичный IP-адрес** виртуальной машины

### Шаг 2: Подключение к серверу

```bash
# Подключитесь по SSH (замените IP на ваш)
ssh ubuntu@<ваш-публичный-IP>

# Например:
ssh ubuntu@51.250.12.34
```

При первом подключении появится вопрос о добавлении хоста - введите `yes`.

### Шаг 3: Автоматическая установка

На сервере выполните:

```bash
# Скачайте скрипт установки
wget https://raw.githubusercontent.com/PashaTai/monitorshik/main/deploy/setup.sh

# Или если wget не работает:
curl -O https://raw.githubusercontent.com/PashaTai/monitorshik/main/deploy/setup.sh

# Сделайте скрипт исполняемым
chmod +x setup.sh

# Запустите установку
bash setup.sh
```

Скрипт автоматически:
- ✅ Обновит систему
- ✅ Установит Python 3.11
- ✅ Клонирует репозиторий
- ✅ Создаст виртуальное окружение
- ✅ Установит зависимости
- ✅ Попросит ввести ENV переменные
- ✅ Создаст systemd service
- ✅ Настроит автозапуск

**Вам нужно будет ввести:**
- `TG_API_ID` - ваш API ID
- `TG_API_HASH` - ваш API Hash
- `TG_STRING_SESSION` - ваш StringSession
- `BOT_TOKEN` - токен бота
- `ALERT_CHAT_ID` - ID группы для уведомлений
- `CHANNELS` - список каналов через запятую
- `TZ` - timezone (по умолчанию Europe/Moscow)

### Шаг 4: Запуск и проверка

После установки запустите сервис:

```bash
sudo systemctl start telegram-monitor
```

Проверьте статус:

```bash
sudo systemctl status telegram-monitor
```

Должно быть: `Active: active (running)`

Просмотрите логи:

```bash
sudo journalctl -u telegram-monitor -f
```

Вы должны увидеть:
```
Telegram Comment Monitor v1.0
Конфигурация загружена
Telegram клиент подключен
✓ Канал настроен...
Мониторинг запущен
Ожидание новых комментариев...
```

Для выхода из просмотра логов: `Ctrl+C`

---

## Ручная установка (если скрипт не работает)

### 1. Подготовка сервера

```bash
# Подключитесь к серверу
ssh ubuntu@<ваш-IP>

# Обновите систему
sudo apt update && sudo apt upgrade -y

# Установите необходимые пакеты
sudo apt install -y python3.11 python3.11-venv python3-pip git
```

### 2. Клонирование проекта

```bash
# Клонируйте репозиторий
cd ~
git clone https://github.com/PashaTai/monitorshik.git
cd monitorshik
```

### 3. Настройка Python окружения

```bash
# Создайте виртуальное окружение
python3.11 -m venv venv

# Активируйте его
source venv/bin/activate

# Установите зависимости
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

```bash
# Создайте файл .env
nano .env
```

Вставьте ваши данные:

```env
TG_API_ID=12345678
TG_API_HASH=ваш_api_hash
TG_STRING_SESSION=ваш_длинный_string_session
BOT_TOKEN=ваш_токен_бота
ALERT_CHAT_ID=-1001234567890
CHANNELS=durov,telegram
TZ=Europe/Moscow
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

Установите правильные права:
```bash
chmod 600 .env
```

### 5. Тестовый запуск

```bash
# Активируйте окружение (если не активировано)
source ~/monitorshik/venv/bin/activate

# Запустите воркер
python worker.py
```

Проверьте что всё работает. Для остановки: `Ctrl+C`

### 6. Создание systemd service

```bash
# Создайте service файл
sudo nano /etc/systemd/system/telegram-monitor.service
```

Вставьте (замените `ubuntu` на ваш username, если отличается):

```ini
[Unit]
Description=Telegram Comment Monitor
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/monitorshik
EnvironmentFile=/home/ubuntu/monitorshik/.env
ExecStart=/home/ubuntu/monitorshik/venv/bin/python /home/ubuntu/monitorshik/worker.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

### 7. Активация сервиса

```bash
# Перезагрузите systemd
sudo systemctl daemon-reload

# Включите автозапуск
sudo systemctl enable telegram-monitor

# Запустите сервис
sudo systemctl start telegram-monitor

# Проверьте статус
sudo systemctl status telegram-monitor
```

---

## Управление сервисом

### Основные команды

```bash
# Запуск
sudo systemctl start telegram-monitor

# Остановка
sudo systemctl stop telegram-monitor

# Перезапуск
sudo systemctl restart telegram-monitor

# Статус (проверка работает ли)
sudo systemctl status telegram-monitor

# Отключить автозапуск
sudo systemctl disable telegram-monitor

# Включить автозапуск
sudo systemctl enable telegram-monitor
```

### Просмотр логов

```bash
# Логи в реальном времени
sudo journalctl -u telegram-monitor -f

# Последние 100 строк
sudo journalctl -u telegram-monitor -n 100

# Логи за сегодня
sudo journalctl -u telegram-monitor --since today

# Логи с определенного времени
sudo journalctl -u telegram-monitor --since "2024-10-25 10:00:00"

# Экспорт логов в файл
sudo journalctl -u telegram-monitor > logs.txt
```

---

## Обновление кода

Когда вы вносите изменения в код и делаете `git push`:

```bash
# 1. Подключитесь к серверу
ssh ubuntu@<ваш-IP>

# 2. Перейдите в директорию проекта
cd ~/monitorshik

# 3. Остановите сервис
sudo systemctl stop telegram-monitor

# 4. Получите обновления из Git
git pull

# 5. Обновите зависимости (если изменились)
source venv/bin/activate
pip install -r requirements.txt

# 6. Запустите сервис
sudo systemctl start telegram-monitor

# 7. Проверьте логи
sudo journalctl -u telegram-monitor -f
```

**Быстрая команда для обновления:**
```bash
cd ~/monitorshik && sudo systemctl stop telegram-monitor && git pull && sudo systemctl start telegram-monitor && sudo journalctl -u telegram-monitor -f
```

---

## Безопасность

### Изменение SSH порта (рекомендуется)

```bash
# Откройте конфигурацию SSH
sudo nano /etc/ssh/sshd_config

# Найдите строку #Port 22 и измените на:
Port 2222  # или другой порт

# Перезапустите SSH
sudo systemctl restart sshd
```

Теперь подключаться нужно так:
```bash
ssh -p 2222 ubuntu@<ваш-IP>
```

### Настройка firewall (UFW)

```bash
# Включите UFW
sudo ufw enable

# Разрешите SSH (используйте ваш порт!)
sudo ufw allow 2222/tcp

# Проверьте статус
sudo ufw status
```

### Автоматические обновления безопасности

```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## Мониторинг и алерты

### Проверка использования ресурсов

```bash
# Использование CPU и памяти
htop

# Если htop не установлен:
sudo apt install htop

# Использование диска
df -h

# Размер папки проекта
du -sh ~/monitorshik
```

### Настройка алертов при падении сервиса

Можно настроить отправку уведомлений в Telegram при падении сервиса через systemd или использовать мониторинг Yandex Cloud.

---

## Резервное копирование

### Бэкап конфигурации

```bash
# Сделайте резервную копию .env
cp ~/monitorshik/.env ~/monitorshik/.env.backup

# Или скачайте на локальный компьютер
scp ubuntu@<ваш-IP>:~/monitorshik/.env ./env.backup
```

### Snapshot диска в Yandex Cloud

1. Зайдите в Yandex Cloud Console
2. Compute Cloud → Диски
3. Выберите диск вашей VM
4. Нажмите "Создать снимок"
5. Снимок можно использовать для восстановления

---

## Решение проблем

### Сервис не запускается

```bash
# Проверьте логи systemd
sudo journalctl -u telegram-monitor -n 50 --no-pager

# Проверьте синтаксис service файла
sudo systemctl status telegram-monitor

# Попробуйте запустить вручную для отладки
cd ~/monitorshik
source venv/bin/activate
python worker.py
```

### Ошибки подключения к Telegram

```bash
# Проверьте .env файл
cat ~/monitorshik/.env

# Убедитесь что StringSession правильный
# Проверьте интернет соединение
ping telegram.org
```

### Закончилось место на диске

```bash
# Проверьте использование
df -h

# Очистите логи
sudo journalctl --vacuum-time=7d

# Очистите кэш apt
sudo apt clean
```

### VM не отвечает

В Yandex Cloud Console:
1. Найдите вашу VM
2. Используйте Serial Console для доступа
3. Или перезагрузите VM через консоль

---

## Удаление / Деинсталляция

Если нужно полностью удалить:

```bash
# Остановите и отключите сервис
sudo systemctl stop telegram-monitor
sudo systemctl disable telegram-monitor

# Удалите service файл
sudo rm /etc/systemd/system/telegram-monitor.service

# Перезагрузите systemd
sudo systemctl daemon-reload

# Удалите проект
rm -rf ~/monitorshik

# Удалите Python (опционально)
sudo apt remove python3.11 python3.11-venv
sudo apt autoremove
```

Чтобы удалить саму VM:
1. Yandex Cloud Console → Compute Cloud
2. Выберите VM
3. Нажмите "Удалить"
4. Подтвердите удаление

---

## FAQ

**Q: Могу ли я использовать несколько воркеров на одной VM?**  
A: Да, можно создать несколько service файлов с разными конфигурациями.

**Q: Можно ли использовать другую ОС?**  
A: Да, но инструкция написана для Ubuntu. На CentOS/Fedora нужно использовать `dnf/yum`.

**Q: Сколько каналов можно мониторить?**  
A: На b1.nano комфортно 5-10 каналов. Больше - может потребоваться больше RAM.

**Q: Нужен ли публичный IP?**  
A: Да, для подключения к Telegram API нужен доступ в интернет.

**Q: Можно ли остановить VM и не платить?**  
A: Если остановить VM, вы не платите за вычисления, но продолжаете платить за диск (~80₽/месяц за 20GB) и IP (~80₽/месяц).

**Q: Как сменить регион/зону?**  
A: При создании VM выберите другую зону (ru-central1-b, ru-central1-c).

---

## Дополнительные ресурсы

- [Документация Yandex Cloud](https://cloud.yandex.ru/docs)
- [Free Tier Yandex Cloud](https://cloud.yandex.ru/docs/free-tier)
- [Документация Telethon](https://docs.telethon.dev/)
- [Основной README проекта](README.md)

---

## Поддержка

Если возникли проблемы:
1. Проверьте логи: `sudo journalctl -u telegram-monitor -f`
2. Проверьте статус: `sudo systemctl status telegram-monitor`
3. Проверьте интернет на VM: `ping google.com`
4. Проверьте .env файл: `cat ~/monitorshik/.env`

---

**Готово! Ваш Telegram Comment Monitor работает 24/7 на Yandex Cloud!** 🎉

