# Команды управления ботом

## Запуск бота

### Режим Polling (для разработки)
```bash
# Запуск с удалением webhook
python manage.py run_bot --remove-webhook

# Принудительный запуск (если бот уже запущен)
python manage.py run_bot --remove-webhook --force

# Быстрый перезапуск
python restart_bot.py
```

### Режим Webhook (для продакшена)
```bash
# Установка webhook
python manage.py set_webhook

# Проверка статуса
python manage.py status
```

## Остановка бота

```bash
# Корректная остановка
python manage.py stop_bot

# Или Ctrl+C в терминале с запущенным ботом
```

## Проверка статуса

```bash
# Проверить PID файл
ls -la /tmp/bot_polling.pid

# Проверить процессы
ps aux | grep python | grep manage.py
```

## Диагностика проблем

### Ошибка 409 "Conflict"
Эта ошибка означает, что уже запущен другой экземпляр бота в режиме polling.

**Решение:**
1. Остановите существующий бот:
   ```bash
   python manage.py stop_bot
   ```

2. Или запустите принудительно:
   ```bash
   python manage.py run_bot --remove-webhook --force
   ```

### Бот не реагирует на сообщения
1. Проверьте, что бот запущен и работает
2. Проверьте логи на ошибки
3. Убедитесь, что используется правильный режим (polling/webhook)
4. Проверьте токен бота в настройках

## Структура проекта

```
bot/
├── management/commands/
│   ├── run_bot.py      # Запуск бота в polling режиме
│   └── stop_bot.py     # Остановка бота
├── handlers/
│   └── tasks.py        # Обработчики команд и сообщений
├── models.py           # Модели базы данных
└── views.py           # Webhook обработчик

restart_bot.py          # Скрипт быстрого перезапуска
test_bot_commands.py    # Тест команд управления
```

## Переменные окружения

Создайте файл `.env` с переменными:
```
BOT_TOKEN=ваш_токен_бота
HOOK=https://ваш-домен.com
OWNER_ID=ваш_telegram_id
```

## Логи

Логи бота сохраняются в файл `ai_log.log` в корне проекта.
