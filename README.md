# Yandex Search MCP Server (Async Mode)

Доработка оригинального [Yandex Search MCP Server](https://github.com/yandex/yandex-search-mcp-server) с добавлением:

- **Async режим по умолчанию** - отложенные запросы для экономии до 94%
- **SQLite хранение** - автоматическое сохранение operation IDs
- **Отслеживание статуса** - проверка результатов через MCP инструменты

## Экономия

| Режим | Цена за 1000 запросов (НДС) | Экономия |
|-------|----------------------------|----------|
| Синхронный дневной | 488 руб. | - |
| **Отложенный дневной** | **30,5 руб.** | **94%** |
| Синхронный ночной | 366 руб. | 25% |
| **Отложенный ночной** | **25,41 руб.** | **95%** |
| Генеративный ответ | 5 080 руб. | - |

**Ночные часы:** 00:00 - 07:59 UTC+3

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

### opencode

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "yandex-search": {
      "type": "local",
      "command": ["python3", "/path/to/server.py"],
      "env": {
        "SEARCH_API_KEY": "{env:SEARCH_API_KEY}",
        "FOLDER_ID": "{env:FOLDER_ID}"
      }
    }
  }
}
```

## MCP Инструменты

### web_search

Выполняет поиск с поддержкой sync и async режимов. **По умолчанию используется async режим.**

**Параметры:**
- `query` (string, required) - поисковый запрос
- `search_region` (string, required) - регион: `ru`, `tr`, `en`
- `mode` (string, optional) - `async` (по умолчанию) или `sync`
- `wait` (boolean, optional) - ждать ли результат при async (по умолчанию false)

**Пример async запроса (по умолчанию):**
```json
{
  "body": {
    "query": "кофемашина",
    "search_region": "ru"
  }
}
```

**Пример sync запроса:**
```json
{
  "body": {
    "query": "кофемашина",
    "search_region": "ru",
    "mode": "sync"
  }
}
```

### get_search_status

Получает статус и результат async запроса.

**Параметры:**
- `operation_id` (string, required) - ID операции из web_search

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
- `limit` (integer, optional) - максимум результатов (по умолчанию 100)

### cleanup_old_searches

Очищает старые запросы из локального хранилища.

**Параметры:**
- `days` (integer, optional) - удалять запросы старше N дней (по умолчанию 7)

## Подключение к AI-агенту

### Пример интеграции с Python

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import json

async def search_with_yandex():
    # Настройка сервера
    server_params = StdioServerParameters(
        command="python3",
        args=["/path/to/server.py"],
        env={
            "SEARCH_API_KEY": "your_api_key",
            "FOLDER_ID": "your_folder_id"
        }
    )
    
    # Подключение к серверу
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Вызов поиска (async по умолчанию)
            result = await session.call_tool(
                "web_search",
                arguments={
                    "body": {
                        "query": "кофемашина",
                        "search_region": "ru"
                    }
                }
            )
            
            # Парсинг результата
            response = json.loads(result.content[0].text)
            print(f"Operation ID: {response['operation_id']}")
            print(f"Status: {response['status']}")
            
            # Проверка статуса
            status_result = await session.call_tool(
                "get_search_status",
                arguments={
                    "body": {
                        "operation_id": response['operation_id']
                    }
                }
            )
            
            status = json.loads(status_result.content[0].text)
            print(f"Final status: {status['status']}")
            
            if status['status'] == 'COMPLETED':
                for item in status.get('responses', []):
                    print(f"Found: {item['data'][:100]}...")
                    print(f"Source: {item['source']}")

# Запуск
asyncio.run(search_with_yandex())
```

### Пример использования в Claude Desktop

1. Добавьте конфигурацию MCP сервера в `claude_desktop_config.json`
2. Перезапустите Claude Desktop
3. Используйте инструмент `web_search` для поиска

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

Подробнее: [Yandex Search API Pricing](https://yandex.cloud/ru/docs/search-api/pricing/)

### Пример расчета

При 1000 запросов в день:
- **Sync:** 488 руб./день = 14 640 руб./мес
- **Async:** 30,5 руб./день = 915 руб./мес
- **Экономия:** 13 725 руб./мес (94%)

## Лицензия

Apache License 2.0 - см. [LICENSE](LICENSE)

## Благодарности

Оригинальный сервер: [Yandex LLC](https://github.com/yandex/yandex-search-mcp-server)
