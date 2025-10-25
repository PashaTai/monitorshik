#!/bin/bash
#
# Скрипт автоматической установки Telegram Comment Monitor на Yandex Cloud
# Запустите: bash setup.sh
#

set -e

echo "=========================================="
echo "Telegram Comment Monitor - Установка"
echo "=========================================="
echo ""

# Проверка ОС
if [ ! -f /etc/os-release ]; then
    echo "❌ Не удалось определить операционную систему"
    exit 1
fi

source /etc/os-release
if [[ "$ID" != "ubuntu" ]] && [[ "$ID" != "debian" ]]; then
    echo "⚠️  Скрипт тестировался на Ubuntu/Debian. Продолжить? (y/n)"
    read -r response
    if [[ "$response" != "y" ]]; then
        exit 1
    fi
fi

# Обновление системы
echo "📦 Обновление системы..."
sudo apt update
sudo apt upgrade -y

# Установка необходимых пакетов
echo "📦 Установка Python 3.11 и зависимостей..."
sudo apt install -y python3.11 python3.11-venv python3-pip git

# Проверка установки Python
if ! command -v python3.11 &> /dev/null; then
    echo "❌ Python 3.11 не установлен"
    exit 1
fi

echo "✅ Python $(python3.11 --version) установлен"

# Определение директории проекта
# Если скрипт запущен из deploy/, поднимаемся на уровень выше
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [[ "$SCRIPT_DIR" == */deploy ]]; then
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    echo "✅ Скрипт запущен из deploy/, используется директория проекта: $PROJECT_DIR"
else
    PROJECT_DIR="$SCRIPT_DIR"
    echo "✅ Используется директория проекта: $PROJECT_DIR"
fi

# Проверка наличия необходимых файлов проекта
if [ ! -f "$PROJECT_DIR/worker.py" ] || [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "❌ Ошибка: файлы проекта не найдены"
    echo "Убедитесь, что вы:"
    echo "  1. Клонировали репозиторий: git clone <ваш-репозиторий>"
    echo "  2. Перешли в директорию проекта: cd monitorshik-latest"
    echo "  3. Запустили скрипт: bash deploy/setup.sh"
    exit 1
fi

cd "$PROJECT_DIR"

# Создание виртуального окружения
echo "🐍 Создание виртуального окружения..."
python3.11 -m venv venv

# Активация виртуального окружения и установка зависимостей
echo "📦 Установка зависимостей Python..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Создание файла .env
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo ""
    echo "⚙️  Настройка переменных окружения..."
    echo "Сейчас вам нужно будет ввести данные для подключения."
    echo ""
    echo "💡 Подсказка: см. env.example для примеров значений"
    echo ""
    
    read -p "TG_API_ID: " TG_API_ID
    read -p "TG_API_HASH: " TG_API_HASH
    read -p "TG_STRING_SESSION: " TG_STRING_SESSION
    read -p "BOT_TOKEN: " BOT_TOKEN
    
    echo ""
    echo "📌 ALERT_CHAT_ID - ID группы для уведомлений"
    echo "   Формат: -100XXXXXXXXXX (отрицательное число с префиксом -100)"
    echo "   Получить: добавьте @userinfobot в вашу группу"
    read -p "ALERT_CHAT_ID: " ALERT_CHAT_ID
    
    read -p "CHANNELS (через запятую БЕЗ @, например: durov,telegram): " CHANNELS
    read -p "TZ (по умолчанию: Europe/Moscow): " TZ
    TZ=${TZ:-Europe/Moscow}
    
    cat > "$PROJECT_DIR/.env" << EOF
TG_API_ID=$TG_API_ID
TG_API_HASH=$TG_API_HASH
TG_STRING_SESSION=$TG_STRING_SESSION
BOT_TOKEN=$BOT_TOKEN
ALERT_CHAT_ID=$ALERT_CHAT_ID
CHANNELS=$CHANNELS
TZ=$TZ
EOF
    
    chmod 600 "$PROJECT_DIR/.env"
    echo "✅ Файл .env создан"
else
    echo "✅ Файл .env уже существует"
fi

# Создание systemd service
echo ""
echo "🔧 Создание systemd service..."

sudo tee /etc/systemd/system/telegram-monitor.service > /dev/null << EOF
[Unit]
Description=Telegram Comment Monitor
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/worker.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable telegram-monitor

echo ""
echo "=========================================="
echo "✅ Установка завершена!"
echo "=========================================="
echo ""
echo "🚀 Команды управления сервисом:"
echo ""
echo "  Запуск:       sudo systemctl start telegram-monitor"
echo "  Остановка:    sudo systemctl stop telegram-monitor"
echo "  Перезапуск:   sudo systemctl restart telegram-monitor"
echo "  Статус:       sudo systemctl status telegram-monitor"
echo "  Логи:         sudo journalctl -u telegram-monitor -f"
echo ""
echo "📝 Хотите запустить сервис сейчас? (y/n)"
read -r response

if [[ "$response" == "y" ]]; then
    sudo systemctl start telegram-monitor
    sleep 2
    sudo systemctl status telegram-monitor --no-pager
    echo ""
    echo "✅ Сервис запущен! Проверьте логи:"
    echo "   sudo journalctl -u telegram-monitor -f"
fi

echo ""
echo "🎉 Готово!"

