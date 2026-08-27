#!/bin/bash
set -e

echo "=========================================="
echo "🚀 Развертывание бота Дневник (Python)"
echo "=========================================="

# Check if .env exists, if not copy from .env.example
if [ ! -f .env ]; then
    echo "⚠️ Файл .env не найден. Создаем из .env.example..."
    cp .env.example .env

    # Generate random secret key if python3 is available
    if command -v python3 &>/dev/null; then
        SECRET=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || openssl rand -base64 32)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|SECRET_KEY=.*|SECRET_KEY=$SECRET|" .env
        else
            sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET|" .env
        fi
        echo "✅ Сгенерирован уникальный SECRET_KEY для шифрования токенов."
    fi
    echo "❗ Пожалуйста, укажите ваш TELEGRAM_BOT_TOKEN в файле .env перед запуском!"
fi

# Ensure data directory exists
mkdir -p data

echo "📦 Сборка и запуск контейнеров..."
if [ "$1" == "--prod" ]; then
    docker compose -f docker-compose.prod.yml up -d --build
    echo "✅ Запущен в продакшн режиме с Nginx!"
else
    docker compose up -d --build
    echo "✅ Бот успешно запущен!"
fi

echo "📊 Статус контейнеров:"
docker compose ps
