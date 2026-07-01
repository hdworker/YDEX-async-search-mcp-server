# Yandex Search MCP Server (Async Mode)

Доработка оригинального [Yandex Search MCP Server](https://github.com/yandex/yandex-search-mcp-server) с добавлением:

- **Async режим** — отложенные запросы для экономии до 94%
- **SQLite хранение** — автоматическое сохранение operation IDs
- **Отслеживание статуса** — проверка результатов через MCP инструменты

## Экономия

| Режим | Цена за 1000 запросов (НДС) | Экономия |
|-------|----------------------------|----------|
| Синхронный дневной | 488 ₽ | — |
| **Отложенный дневной** | **30,5 ₽** | **94%** |
| Синхронный ночной | 366 ₽ | 25% |
| **Отложенный ночной** | **25,41 ₽** | **95%** |
| Генеративный ответ | 5 080 ₽ | — |

**Ночные часы:** 00:00 — 07:59 UTC+3

## Установка Yandex CLI

### 1. Установите Yandex Cloud CLI

```bash
# Для Linux/macOS
curl https://storage.yandexcloud.net/yandexcloud-yc/install.sh | \
    bash -s -- -i /opt/yc -n

# Добавьте в PATH
export PATH="/opt/yc/bin:$PATH"
```

### 2. Авторизуйтесь в Yandex Cloud

```bash
# Интерактивная авторизация
yc init

# Или с помощью IAM-токена
yc config set token <IAM_TOKEN>
```

### 3. Создайте сервсиный аккаунт

```bash
# Создайте сервсиный аккаунт
yc iam service-account create --name search-sa

# Дайте роль search-api.editor
yc organization-manager service-account add-access-binding \
    --id <service_account_id> \
    --role search-api.editor
```

### 4. Создайте API ключ

```bash
# Создайте API ключ для сервсисного аккаунта
yc iam api-key create \
    --service-account-name search-sa \
    --scopes yc.search-api.execute

# Сохраните API ключ (будет показан только один раз!)
```

## Установка MCP сервера

### Вариант 1: Docker

```bash
# Соберите образ
docker build -t yandex-mcp-server-async:latest .

# Запустите контейнер
docker run -i --rm \
    -e SEARCH_API_KEY=<your_api_key> \
    -e FOLDER_ID=<your_folder_id> \
    -v $(pwd)/data:/app/data \
    yandex-mcp-server-async:latest
```

### Вариант 2: Python

```bash
# Установите зависимости
pip install -r requirements.txt

# Запустите сервер
SEARCH_API_KEY=<your_api_key> \
FOLDER_ID=<your_folder_id> \
python server.py
```

## Конфигурация MCP клиента

### Claude Desktop

```json
{
  "mcpServers": {
    "yandex-search": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
        "-e", "SEARCH_API_KEY=<your_api_key>",
        "-e", "FOLDER_ID=<your_folder_id>",
        "-v", "/path/to/data:/app/data",
        "yandex-mcp-server-async:latest"]
    }
  }
}
```

### Cursor

```json
{
  "mcpServers": {
    "yandex-search": {
      "command": "python",
      "args": ["/path/to/server.py"],
      "env": {
        "SEARCH_API_KEY": "<your_api_key>",
        "FOLDER_ID": "<your_folder_id>"
      }
    }
  }
}
```

## MCP Инструменты

### web_search

Выполняет поиск с поддержкой sync и async режимов.

**Параметры:**
- `query` (string, required) — поисковый запрос
- `search_region` (string, required) — регион: `ru`, `tr`, `en`
- `mode` (string, optional) — `sync` (по умолчанию) или `async`
- `wait` (boolean, optional) — ждать ли результат при async (по умолчанию false)

**Пример sync запроса:**
```json
{
  "body": {
    "query": "кофемашина",
    "search_region": "ru"
  }
}
```

**Пример async запроса:**
```json
{
  "body": {
    "query": "кофемашина",
    "search_region": "ru",
    "mode": "async"
  }
}
```

### get_search_status

Получает статус и результат async запроса.

**Параметры:**
- `operation_id` (string, required) — ID операции из web_search

**Пример:**
```json
{
  "body": {
    "operation_id": "abc123-def456"
  }
}
```

### get_pending_searches

Получает список всех pending запросов.

**Параметры:**
- `limit` (integer, optional) — максимум результатов (по умолчанию 100)

### cleanup_old_searches

Очищает старые запросы из локального хранилища.

**Параметры:**
- `days` (integer, optional) — удалять запросы старше N дней (по умолчанию 7)

## Пример использования

### 1. Отправить async запрос

```python
# Вызов через MCP
result = web_search({
    "query": "кофемашина",
    "search_region": "ru",
    "mode": "async"
})

# Результат:
# {
#   "operation_id": "abc123-def456",
#   "status": "PENDING",
#   "message": "Request queued. Use get_search_status to check result."
# }
```

### 2. Проверить статус

```python
# Вызов через MCP
result = get_search_status({
    "operation_id": "abc123-def456"
})

# Результат:
# {
#   "operation_id": "abc123-def456",
#   "status": "COMPLETED",
#   "created_at": "2025-01-01T12:00:00Z",
#   "completed_at": "2025-01-01T12:00:05Z",
#   "responses": [...]
# }
```

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Client                           │
│                  (Claude, Cursor)                       │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   server.py                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  web_search  │  │get_search_   │  │get_pending_  │  │
│  │              │  │status        │  │searches      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│      detail.py          │  │      storage.py         │
│  ┌─────────────────┐    │  │  ┌─────────────────┐    │
│  │ call_web_search │    │  │  │ SQLite storage  │    │
│  │ call_web_search │    │  │  │ operations.db   │    │
│  │   _async        │    │  │  └─────────────────┘    │
│  │ get_operation   │    │  └─────────────────────────┘
│  └─────────────────┘    │
└─────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│            Yandex Search API v2                         │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │ /v2/web/search  │  │ /v1/operations  │              │
│  │ (sync & async)  │  │ (status check)  │              │
│  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────┘
```

## Стоимость

详见 [Yandex Search API Pricing](https://yandex.cloud/ru/docs/search-api/pricing/)

### Пример расчета

При 1000 запросов в день:
- **Sync:** 488 ₽/день = 14 640 ₽/мес
- **Async:** 30,5 ₽/день = 915 ₽/мес
- **Экономия:** 13 725 ₽/мес (94%)

## Лицензия

Apache License 2.0 — см. [LICENSE](LICENSE)

## Благодарности

Оригинальный сервер: [Yandex LLC](https://github.com/yandex/yandex-search-mcp-server)
